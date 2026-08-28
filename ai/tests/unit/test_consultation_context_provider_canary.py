"""Protected Consultation Context Provider Canary runner tests."""

from __future__ import annotations

from copy import deepcopy
import json
from uuid import UUID

from pydantic import ValidationError
import pytest

from ai.app.generation.consultation_summary.context_models import (
    ConsultationContextSynthesisCandidate,
    ContextSourceKind,
)
from ai.app.integrations.backend.handoff_client import (
    HandoffPublishResult,
    HandoffPublishStatus,
)
from ai.app.integrations.llm import (
    ConsultationContextLLMResponse,
    LLMProviderTimeoutError,
    LLMUsage,
)
from ai.scripts.run_consultation_context_provider_canary import (
    ConsultationContextProviderCanaryInput,
    execute_canary,
    input_hashes,
    inspect_canary,
    main,
)
from ai.app.orchestration.hitl import build_hitl_thread_id


INQUIRY_ID = UUID("018f2f9b-7c30-7981-b541-1a987c88b321")
CORRELATION_ID = UUID("018f2f9b-7c30-7981-b541-1a987c88b421")
GIT_IDENTITY = {
    "branch": "dongyoon",
    "git_sha": "1" * 40,
    "origin_main_sha": "2" * 40,
    "git_dirty": False,
}


def canary_payload() -> dict:
    """Return a non-real placeholder fixture that satisfies the runner contract."""

    ai_request_id = "TEST_ONLY_AI_REQUEST"
    state_version = 7
    return {
        "schema_version": "1.0.0",
        "environment_id": "LOCAL_CANARY_TEST",
        "data_classification": "synthetic",
        "inquiry_id": str(INQUIRY_ID),
        "correlation_id": str(CORRELATION_ID),
        "ai_request_id": ai_request_id,
        "state_version": state_version,
        "backend_review_id": "018f2f9b-7c30-7981-b541-1a987c88b521",
        "backend_review_state_version_after_reject": 2,
        "checkpoint_thread_id": build_hitl_thread_id(
            inquiry_id=INQUIRY_ID,
            ai_request_id=ai_request_id,
            state_version=state_version,
        ),
        "model_code": "WPUJAC104DWH",
        "product_family": "DIRECT_WATER_PURIFIER",
        "runtime_product_approved": True,
        "structured_symptom": {
            "symptom_type": "출수량 저하",
            "target_water_type": "정수",
            "actions_taken": [],
        },
        "previous_answers": [],
        "safety_assessment": {
            "risk_level": "caution",
            "priority": "consultation_recommended",
            "requires_consultation": True,
            "matched_safety_rule_ids": [],
            "detected_risks": ["TEST_ONLY_CAUTION"],
            "safety_reason": "TEST_ONLY_SAFETY_REASON",
        },
        "guidance": {
            "guidance_status": "PARTIAL_STOP",
            "message": "TEST_ONLY_GUIDANCE",
            "restricted_functions": ["purified_water"],
            "next_actions": ["TEST_ONLY_NEXT_ACTION"],
        },
        "evidence": [
            {
                "chunk_id": "TEST-ONLY-EVIDENCE-001",
                "document_title": "TEST_ONLY_DOCUMENT",
                "page": 1,
                "model_code": "WPUJAC104DWH",
                "content": "TEST_ONLY_EVIDENCE_CONTENT",
                "summary": "TEST_ONLY_EVIDENCE_SUMMARY",
                "source_hash": "a" * 64,
                "similarity_score": 0.95,
                "verification_status": "official_verified",
                "allowed_use": True,
                "runtime_eligible": True,
            }
        ],
    }


def canary_input() -> ConsultationContextProviderCanaryInput:
    return ConsultationContextProviderCanaryInput.model_validate(canary_payload())


def valid_candidate(request) -> ConsultationContextSynthesisCandidate:
    by_kind = {
        kind: [source.source_id for source in request.sources if source.kind == kind]
        for kind in ContextSourceKind
    }
    customer_ids = (
        by_kind[ContextSourceKind.CUSTOMER_REPORTED]
        + by_kind[ContextSourceKind.QUESTIONNAIRE]
    )
    issue_ids = customer_ids[:2] or by_kind[ContextSourceKind.ESCALATION][:1]
    return ConsultationContextSynthesisCandidate(
        issue_summary_source_ids=issue_ids,
        customer_reported_fact_ids=customer_ids,
        attempted_action_ids=by_kind[ContextSourceKind.ATTEMPTED_ACTION],
        unresolved_question_ids=by_kind[ContextSourceKind.UNRESOLVED],
        safety_constraint_ids=by_kind[ContextSourceKind.SAFETY],
        evidence_finding_source_groups=[],
        consultant_priority_check_ids=by_kind[ContextSourceKind.PRIORITY],
        uncertainty_source_groups=[],
    )


class FakeProvider:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    def synthesize_context(self, request, *, timeout_seconds):
        self.calls += 1
        assert timeout_seconds > 0
        if self.error is not None:
            raise self.error
        return ConsultationContextLLMResponse(
            output=valid_candidate(request),
            model_name="TEST_ONLY_PROVIDER_MODEL",
            usage=LLMUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            latency_ms=1.0,
        )


def test_inspect_proves_initial_review_does_not_call_context_agent_or_provider():
    report = inspect_canary(canary_input(), git_identity=GIT_IDENTITY)

    assert report.overall_status == "INSPECTED"
    assert report.harness_decision == "PASS"
    assert report.routing_disposition == "PRE_SEND_HUMAN_REVIEW"
    assert report.initial_review_status == "WAITING_FOR_REVIEW"
    assert report.initial_context_agent_calls == 0
    assert report.initial_provider_calls == 0
    assert report.initial_handoff_present is False
    assert report.accepted_evidence_chunk_ids == ["TEST-ONLY-EVIDENCE-001"]


def test_cli_inspect_writes_sanitized_report_outside_repository(tmp_path, capsys):
    input_path = tmp_path / "input.json"
    report_path = tmp_path / "report.json"
    input_path.write_text(
        json.dumps(canary_payload(), ensure_ascii=False),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--mode",
            "inspect",
            "--input",
            str(input_path),
            "--report",
            str(report_path),
        ]
    )

    assert exit_code == 0
    report_text = report_path.read_text(encoding="utf-8")
    assert json.loads(report_text)["overall_status"] == "INSPECTED"
    assert "TEST_ONLY_EVIDENCE_CONTENT" not in report_text
    assert "TEST_ONLY_EVIDENCE_SUMMARY" not in report_text
    assert "TEST_ONLY_GUIDANCE" not in report_text
    assert "TEST_ONLY_EVIDENCE_CONTENT" not in capsys.readouterr().out


def test_execute_calls_provider_once_only_after_reject_and_builds_v2_handoff():
    provider = FakeProvider()

    report = execute_canary(
        canary_input(),
        provider_client=provider,
        git_identity=GIT_IDENTITY,
        provider_input_explicitly_allowed=True,
    )

    assert report.overall_status == "AI_COMPONENT_PASS"
    assert report.failure_code is None
    assert report.review_decision == "reject"
    assert report.resolved_review_status == "COMPLETED"
    assert report.initial_provider_calls == 0
    assert report.context_agent_calls == 1
    assert report.provider_calls == 1
    assert provider.calls == 1
    assert report.context_synthesis_status == "SUCCEEDED"
    assert report.context_synthesis_fallback_reason is None
    assert report.provider_called is True
    assert report.handoff_schema_version == "2.0.0"
    assert report.handoff_source_chunk_ids == ["TEST-ONLY-EVIDENCE-001"]
    assert report.context_evidence_chunk_ids == ["TEST-ONLY-EVIDENCE-001"]
    assert report.handoff_delivery.requested is False


def test_execute_refuses_provider_without_explicit_input_authorization():
    provider = FakeProvider()

    report = execute_canary(
        canary_input(),
        provider_client=provider,
        git_identity=GIT_IDENTITY,
        provider_input_explicitly_allowed=False,
    )

    assert report.overall_status == "FAIL"
    assert report.failure_stage == "ARGUMENTS"
    assert report.failure_code == "PROVIDER_INPUT_NOT_EXPLICITLY_ALLOWED"
    assert report.provider_input_explicitly_allowed is False
    assert provider.calls == 0


def test_execute_stops_before_delivery_when_provider_falls_back():
    provider = FakeProvider(error=LLMProviderTimeoutError("TEST_ONLY_TIMEOUT"))
    published = []

    report = execute_canary(
        canary_input(),
        provider_client=provider,
        git_identity=GIT_IDENTITY,
        provider_input_explicitly_allowed=True,
        send_handoff=True,
        publisher=lambda handoff: published.append(handoff),
    )

    assert report.overall_status == "FAIL"
    assert report.failure_stage == "PROVIDER"
    assert report.failure_code == "CONTEXT_SYNTHESIS_NOT_SUCCEEDED"
    assert report.context_synthesis_status == "FALLBACK"
    assert report.context_synthesis_fallback_reason == "PROVIDER_TIMEOUT"
    assert report.provider_called is True
    assert report.provider_calls == 1
    assert published == []


def test_execute_sends_same_handoff_for_replay_without_second_provider_call():
    provider = FakeProvider()
    published = []

    def publisher(handoff):
        published.append(handoff)
        return HandoffPublishResult(
            status=HandoffPublishStatus.DELIVERED,
            attempts=1,
            status_code=201 if len(published) == 1 else 200,
        )

    report = execute_canary(
        canary_input(),
        provider_client=provider,
        git_identity=GIT_IDENTITY,
        provider_input_explicitly_allowed=True,
        send_handoff=True,
        verify_replay=True,
        publisher=publisher,
    )

    assert report.overall_status == "PASS"
    assert provider.calls == 1
    assert len(published) == 2
    assert published[0] is published[1]
    assert report.handoff_delivery.first.status == "DELIVERED"
    assert report.handoff_delivery.first.status_code == 201
    assert report.handoff_delivery.replay.status == "DELIVERED"
    assert report.handoff_delivery.replay.status_code == 200


def test_evidence_binding_hash_changes_when_evidence_body_changes():
    original = canary_input()
    changed_payload = deepcopy(canary_payload())
    changed_payload["evidence"][0]["summary"] = "TEST_ONLY_CHANGED_SUMMARY"
    changed = ConsultationContextProviderCanaryInput.model_validate(changed_payload)

    original_input_hash, original_evidence_hash = input_hashes(original)
    changed_input_hash, changed_evidence_hash = input_hashes(changed)

    assert original_input_hash != changed_input_hash
    assert original_evidence_hash != changed_evidence_hash


def test_input_contract_rejects_wrong_product_and_duplicate_evidence():
    wrong_product = canary_payload()
    wrong_product["model_code"] = "WPUIAC425SNW"
    with pytest.raises(ValidationError):
        ConsultationContextProviderCanaryInput.model_validate(wrong_product)

    duplicate_evidence = canary_payload()
    duplicate_evidence["evidence"].append(deepcopy(duplicate_evidence["evidence"][0]))
    with pytest.raises(ValidationError):
        ConsultationContextProviderCanaryInput.model_validate(duplicate_evidence)

    mismatched_checkpoint = canary_payload()
    mismatched_checkpoint["checkpoint_thread_id"] = f"hitl-{'0' * 32}"
    with pytest.raises(ValidationError):
        ConsultationContextProviderCanaryInput.model_validate(mismatched_checkpoint)
