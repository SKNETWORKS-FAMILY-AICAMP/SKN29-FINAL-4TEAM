"""Evaluation-only 45-case runner, isolated from Runtime and Prompt inputs."""

from collections import Counter
from dataclasses import fields, is_dataclass
from hashlib import sha256
import json
from uuid import uuid4

from jsonschema import Draft202012Validator
from pydantic import BaseModel

from ai.app.common.timeout import CancellationToken
from ai.app.interfaces.http.runtime_policy import get_runtime_policy
from ai.app.retrieval.runtime_profile import REPOSITORY_ROOT
from ai.evaluation.release_evidence import json_sha256, text_file_sha256


DATASET = REPOSITORY_ROOT / "data/reference_cases/three_model_reference_scenarios_v1.json"
SCHEMA = REPOSITORY_ROOT / "data/schemas/reference_cases/three_model_reference_scenarios_v1.schema.json"


def _payload(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return {field.name: _payload(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {key: _payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_payload(item) for item in value]
    return value


def load_reference_catalog() -> tuple[list[dict], dict]:
    catalog = json.loads(DATASET.read_text(encoding="utf-8"))
    Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(catalog)
    cases = catalog["scenarios"]
    counts = Counter((case["exact_model_code"], case["risk_level"]) for case in cases)
    if len({case["scenario_id"] for case in cases}) != 45 or len(counts) != 9 or set(counts.values()) != {5}:
        raise ValueError("Reference catalog identity/distribution mismatch")
    return cases, {
        "dataset_sha256": text_file_sha256(DATASET), "schema_sha256": text_file_sha256(SCHEMA),
        "case_count": len(cases), "curation_status": catalog["curation_status"],
        "input_protocol": "FIRST_TURN_CUSTOMER_UTTERANCE_ONLY",
        "context_facts_policy": "ANNOTATION_ONLY_NOT_SENT_TO_RUNTIME",
        "model_risk_counts": {f"{model}:{risk}": count for (model, risk), count in sorted(counts.items())},
    }


def runtime_request(case: dict) -> dict:
    """Only actual customer text and exact product identity enter the pipeline.

    Expected risk/route, topic, source IDs, outlines and context annotations are
    never supplied as answers, selected symptoms, prompts or retrieved evidence.
    """
    return {
        "inquiry_id": str(uuid4()), "correlation_id": str(uuid4()),
        "ai_request_id": f"reference-eval-{uuid4()}", "state_version": 1,
        "raw_symptom": case["customer_utterance"], "model_code": case["exact_model_code"],
        "selected_symptoms": [], "previous_answers": [],
    }


class AuditedProvider:
    """Record identifiers/hashes, never raw Provider requests or responses."""

    def __init__(self, client, task: str, events: list):
        self.client, self.task, self.events = client, task, events

    def __getattr__(self, name):
        method = getattr(self.client, name)
        if name not in {"structure_symptom", "generate_followup_wording", "generate_guidance"}:
            return method

        def invoke(request, **kwargs):
            event = {"task": self.task, "configured_model": self.client.model_name,
                     "prompt_version": getattr(self.client, "prompt_version", "customer_guidance/v3"),
                     "request_sha256": json_sha256(_payload(request))}
            self.events.append(event)
            try:
                result = method(request, **kwargs)
            except Exception as exc:
                event.update(status="ERROR", error_type=type(exc).__name__)
                raise
            event.update(status="RETURNED", model_name=result.model_name,
                         output_sha256=json_sha256(_payload(result)),
                         total_tokens=result.usage.total_tokens, latency_ms=result.latency_ms)
            return result
        return invoke


def evaluate_cases(cases: list[dict], router, *, runtime: str, provider_events: list) -> dict:
    results = []
    canonical = json.loads((REPOSITORY_ROOT / "ai/configs/canonical_evidence_topics_3model.json").read_text(encoding="utf-8"))
    evidence_identity = {row["chunk_id"]: row for row in canonical["chunks"]}
    routes = {"AI_GUIDANCE": "AUTO_GUIDANCE", "HUMAN_REVIEW": "PRE_SEND_HUMAN_REVIEW",
              "EMERGENCY_ESCALATION": "DANGER_HANDOFF"}
    for case in cases:
        event_start = len(provider_events)
        request = runtime_request(case)
        row = {"scenario_id": case["scenario_id"], "input_sha256": json_sha256({
            "customer_utterance": case["customer_utterance"], "exact_model_code": case["exact_model_code"],
        })}
        try:
            token = CancellationToken()
            with token.deadline_scope(get_runtime_policy().overall_timeout_seconds, "FAILED"):
                pipeline = router.run_pipeline(**request, runtime_name=runtime, cancellation_token=token)
                response = pipeline.to_analysis_result()
            actual = response.safety_assessment
            route = pipeline.routing_disposition.value
            auto = route == "AUTO_GUIDANCE"
            evidence_rows = [evidence_identity.get(ref.chunk_id) for ref in response.evidence_references]
            evidence_model_matches = bool(evidence_rows) and all(
                row is not None and row["model_code"] == case["exact_model_code"] for row in evidence_rows
            )
            expected_group_hit = bool(set(case.get("evidence_group_ids", ())).intersection(
                row["evidence_group_id"] for row in evidence_rows if row is not None
            ))
            auto_evidence_valid = evidence_model_matches and expected_group_hit
            danger_miss = case["risk_level"] == "danger" and actual.risk_level.value != "danger"
            inappropriate_auto = auto and (
                case["risk_level"] != "general" or case["expected_requires_consultation"]
                or case["expected_publication_gate"] != "AUTO_GUIDANCE_ELIGIBLE"
                or actual.risk_level.value != "general" or actual.requires_consultation
                or bool(actual.matched_safety_rule_ids)
                or not auto_evidence_valid
            )
            checks = {
                "risk_matches": actual.risk_level.value == case["risk_level"],
                "consultation_matches": actual.requires_consultation == case["expected_requires_consultation"],
                "route_matches": route == routes[case["expected_route"]],
                "usage_status_matches": response.usage_guidance.guidance_status.value == case["expected_usage_guidance_status"],
                "danger_rules_present": actual.risk_level.value != "danger" or bool(actual.matched_safety_rule_ids),
                "auto_guidance_has_expected_verified_evidence": not auto or auto_evidence_valid,
            }
            row.update(
                status="COMPLETED", passed=all(checks.values()), checks=checks,
                actual_risk=actual.risk_level.value, actual_requires_consultation=actual.requires_consultation,
                actual_route=route, response_status=response.status.value,
                fallback_reason_code=response.fallback_reason_code.value if response.fallback_reason_code else None,
                actual_usage_status=response.usage_guidance.guidance_status.value,
                matched_safety_rule_ids=list(actual.matched_safety_rule_ids),
                danger_miss=danger_miss, inappropriate_auto_guidance=inappropriate_auto,
                caution_auto_route=auto and (case["risk_level"] == "caution" or actual.risk_level.value == "caution"),
                response_sha256=json_sha256(response.model_dump(mode="json")),
                evidence=[{"chunk_id": ref.chunk_id, "summary_sha256": sha256(ref.summary.encode("utf-8")).hexdigest(),
                           "source_file_sha256": row["source_file_sha256"] if row else None,
                           "index_version": canonical["index_version"], "chunk_set_sha256": canonical["chunk_set_sha256"]}
                          for ref, row in zip(response.evidence_references, evidence_rows, strict=True)],
                evidence_selection_reasons=pipeline.context.evidence_selection_reasons,
                followup_fields=[q.target_field for q in response.followup_questions],
            )
        except Exception as exc:
            row.update(status="ERROR", passed=False, error_type=type(exc).__name__,
                       danger_miss=None, inappropriate_auto_guidance=None, caution_auto_route=None)
        row["provider_calls"] = provider_events[event_start:]
        row["result_sha256"] = json_sha256(row)
        results.append(row)
    incomplete = any(row["status"] != "COMPLETED" for row in results)
    return {
        "status": "CANDIDATE_PASS" if all(row["passed"] for row in results) else "CANDIDATE_FAIL",
        "executed_case_count": len(results), "passed_count": sum(row["passed"] for row in results),
        "error_count": sum(row["status"] == "ERROR" for row in results),
        "danger_miss_count": None if incomplete else sum(row["danger_miss"] for row in results),
        "inappropriate_auto_guidance_count": None if incomplete else sum(row["inappropriate_auto_guidance"] for row in results),
        "caution_auto_route_count": None if incomplete else sum(row["caution_auto_route"] for row in results),
        "backend_customer_publication_check": "NOT_RUN", "case_results": results,
    }
