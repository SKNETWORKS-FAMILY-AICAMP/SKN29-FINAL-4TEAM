"""실제 OpenAI·팀 pgvector Local Pipeline의 Runtime Identity를 검증한다."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Any

from ai.app.generation.customer_guidance.prompt_identity import PROMPT_VERSION
from ai.app.orchestration.pipeline_router import (
    PipelineRouter,
    warmup_configured_search_service,
)
from ai.app.retrieval.runtime_profile import (
    RagRuntimeProfile,
    resolve_rag_runtime_profile,
)


EXPECTED_MODEL = "gpt-4.1-mini"
EXPECTED_TABLE = "backend_ai_rag_chunks_v1"
EXPECTED_EMBEDDING_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
EXPECTED_PYTHON_VERSION = "3.13.13"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
EXPECTED_MULTI_AGENT_HANDOFFS = (
    ("SUPERVISOR", "SYMPTOM_ANALYSIS", "START_ANALYSIS"),
    ("SYMPTOM_ANALYSIS", "EVIDENCE_ANALYSIS", "RETRIEVAL_REQUIRED"),
    ("EVIDENCE_ANALYSIS", "CARE_DECISION", "EVIDENCE_READY"),
    ("CARE_DECISION", "SUPERVISOR", "CARE_DECISION_READY"),
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MVP_IDENTITY_PATH = REPOSITORY_ROOT / "ai/configs/canonical_evidence_identity.json"
THREE_MODEL_IDENTITY_PATH = (
    REPOSITORY_ROOT / "ai/configs/canonical_evidence_identity_3model.json"
)
THREE_MODEL_CASES_PATH = (
    REPOSITORY_ROOT / "data/config/rag/three_model_evaluation_cases.json"
)


@dataclass(frozen=True, slots=True)
class RuntimeScenario:
    model_code: str
    raw_symptom: str
    inquiry_id: str
    correlation_id: str
    ai_request_id: str


class LocalRuntimeFailure(RuntimeError):
    """실제 Local Runtime Gate 실패."""


def _required_environment(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise LocalRuntimeFailure(f"필수 환경변수가 없습니다: {name}")
    return value


def _git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _git_identity() -> dict[str, object]:
    branch = _git_output("branch", "--show-current") or "DETACHED"
    return {
        "branch": branch,
        "git_sha": _git_output("rev-parse", "HEAD"),
        "git_dirty": bool(_git_output("status", "--porcelain")),
    }


def _validated_environment_id(value: str | None) -> str:
    if value is None:
        raise LocalRuntimeFailure(
            "비밀이 아닌 Evidence environment ID를 명시해야 합니다."
        )
    normalized = value.strip()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_.-]{2,99}", normalized):
        raise LocalRuntimeFailure(
            "Evidence environment ID는 3~100자의 영문 대문자·숫자·._-만 허용합니다."
        )
    return normalized


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _runtime_execution_evidence(
    result: Any,
    *,
    expected_runtime: str,
    scenario: RuntimeScenario,
    response: Any,
) -> dict[str, object]:
    runtime_name = str(getattr(result, "runtime_name", ""))
    if runtime_name != expected_runtime:
        raise LocalRuntimeFailure("실제 Pipeline Runtime이 요청한 Runtime과 다릅니다.")

    metadata = getattr(result, "multi_agent_metadata", None)
    if expected_runtime == "single_rag":
        if metadata is not None:
            raise LocalRuntimeFailure("Single RAG 결과에 Multi-Agent Metadata가 포함됐습니다.")
        return {
            "runtime_name": runtime_name,
            "hop_count": 0,
            "handoff_reason_codes": [],
            "awaiting_customer_input": False,
        }

    if metadata is None or _enum_value(getattr(metadata, "runtime_name", "")) != "multi_agent":
        raise LocalRuntimeFailure("Multi-Agent 실행 Metadata가 없습니다.")
    handoffs = list(getattr(metadata, "handoffs", []) or [])
    observed_handoffs = [
        (
            _enum_value(getattr(handoff, "from_agent", "")),
            _enum_value(getattr(handoff, "to_agent", "")),
            _enum_value(getattr(handoff, "reason_code", "")),
        )
        for handoff in handoffs
    ]
    hop_count = int(getattr(metadata, "hop_count", -1))
    if hop_count != len(handoffs) or hop_count <= 0:
        raise LocalRuntimeFailure("Multi-Agent Hop 증거가 Handoff 기록과 일치하지 않습니다.")
    if bool(getattr(metadata, "awaiting_customer_input", False)):
        raise LocalRuntimeFailure("Provider 대표 Case가 고객 입력 대기 상태로 종료됐습니다.")
    if tuple(observed_handoffs) != EXPECTED_MULTI_AGENT_HANDOFFS:
        raise LocalRuntimeFailure("Multi-Agent 필수 Handoff Sequence 증거가 없습니다.")

    expected_trace = {
        "inquiry_id": scenario.inquiry_id,
        "correlation_id": scenario.correlation_id,
        "ai_request_id": scenario.ai_request_id,
        "state_version": "1",
    }
    for expected_hop, handoff in enumerate(handoffs, start=1):
        if int(getattr(handoff, "hop_count", -1)) != expected_hop:
            raise LocalRuntimeFailure("Multi-Agent Handoff Hop 순서가 연속적이지 않습니다.")
        for field_name, expected_value in expected_trace.items():
            if str(getattr(handoff, field_name, "")) != expected_value:
                raise LocalRuntimeFailure("Multi-Agent Handoff Trace Identity가 다릅니다.")
        retry_count = int(getattr(handoff, "retry_count", -1))
        if retry_count not in {0, 1}:
            raise LocalRuntimeFailure("Multi-Agent Handoff Retry Count가 계약 범위를 벗어났습니다.")

    public_retry_count = int(getattr(response, "retry_count", -1))
    if public_retry_count not in {0, 1}:
        raise LocalRuntimeFailure("공개 Retry Count 증거가 계약 범위를 벗어났습니다.")
    return {
        "runtime_name": runtime_name,
        "hop_count": hop_count,
        "handoff_reason_codes": [item[2] for item in observed_handoffs],
        "awaiting_customer_input": False,
        "public_retry_count": public_retry_count,
    }


def _validate_response_identity(response: Any, scenario: RuntimeScenario) -> None:
    expected = {
        "inquiry_id": scenario.inquiry_id,
        "correlation_id": scenario.correlation_id,
        "ai_request_id": scenario.ai_request_id,
        "state_version": "1",
        "model_code": scenario.model_code,
    }
    for field_name, expected_value in expected.items():
        if str(getattr(response, field_name, "")) != expected_value:
            raise LocalRuntimeFailure("요청·응답 Trace 또는 제품 Identity가 다릅니다.")


def _identifier_set_sha256(values: list[str]) -> str:
    return _canonical_json_sha256(sorted(set(values)))


def _canonical_json_sha256(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest().upper()


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LocalRuntimeFailure("Runtime Identity 입력을 읽지 못했습니다.") from exc
    if not isinstance(value, dict):
        raise LocalRuntimeFailure("Runtime Identity 입력 형식이 올바르지 않습니다.")
    return value


def _identity_by_model(
    profile: RagRuntimeProfile,
) -> dict[str, frozenset[str]]:
    identity_path = (
        THREE_MODEL_IDENTITY_PATH
        if profile.name == "three_model_integration"
        else MVP_IDENTITY_PATH
    )
    identity = _load_json_object(identity_path)
    chunks = identity.get("chunks")
    if not isinstance(chunks, list):
        raise LocalRuntimeFailure("Canonical Child Identity가 없습니다.")
    expected_count = profile.expected_chunk_count
    if len(chunks) != expected_count:
        raise LocalRuntimeFailure("Canonical Child Identity 수가 Profile과 다릅니다.")
    if identity.get("index_version") != profile.expected_index_version:
        raise LocalRuntimeFailure("Canonical Identity의 Index Version이 다릅니다.")
    if str(identity.get("chunk_set_sha256", "")).casefold() != (
        profile.expected_chunk_set_sha256.casefold()
    ):
        raise LocalRuntimeFailure("Canonical Identity의 Chunk Set Hash가 다릅니다.")

    grouped: dict[str, set[str]] = {
        model_code: set() for model_code in profile.approved_model_codes
    }
    for chunk in chunks:
        if not isinstance(chunk, dict):
            raise LocalRuntimeFailure("Canonical Child Identity 행이 올바르지 않습니다.")
        model_code = chunk.get("model_code")
        chunk_id = chunk.get("chunk_id")
        if model_code not in grouped or not isinstance(chunk_id, str):
            raise LocalRuntimeFailure("Canonical Child Identity 제품 범위가 다릅니다.")
        grouped[model_code].add(chunk_id)
    if sum(len(values) for values in grouped.values()) != expected_count:
        raise LocalRuntimeFailure("Canonical Child Identity ID가 중복되었습니다.")
    if any(not values for values in grouped.values()):
        raise LocalRuntimeFailure("제품별 Canonical Child Identity가 비어 있습니다.")
    return {key: frozenset(value) for key, value in grouped.items()}


def _runtime_scenarios(profile: RagRuntimeProfile) -> list[RuntimeScenario]:
    if profile.name == "mvp":
        return [
            RuntimeScenario(
                model_code="WPUJAC104DWH",
                raw_symptom="냉수 출수량이 줄었습니다.",
                inquiry_id="018f2f9b-7c30-7981-b541-1a987c88f101",
                correlation_id="018f2f9b-7c30-7981-b541-1a987c88f102",
                ai_request_id="ai-local-runtime-gate-mvp-001",
            )
        ]

    evaluation = _load_json_object(THREE_MODEL_CASES_PATH)
    cases = evaluation.get("cases")
    if not isinstance(cases, list):
        raise LocalRuntimeFailure("3모델 평가 Case가 없습니다.")
    positive_by_model: dict[str, dict[str, Any]] = {}
    for case in cases:
        if not isinstance(case, dict) or case.get("case_type") != "POSITIVE":
            continue
        model_code = case.get("exact_sales_code")
        if model_code in profile.approved_model_codes:
            positive_by_model.setdefault(str(model_code), case)
    if set(positive_by_model) != set(profile.approved_model_codes):
        raise LocalRuntimeFailure("3모델 Provider 대표 Case 구성이 완전하지 않습니다.")

    trace_values = {
        "WPUJAC104DWH": (
            "018f2f9b-7c30-7981-b541-1a987c88f201",
            "018f2f9b-7c30-7981-b541-1a987c88f202",
            "ai-local-runtime-gate-jac104-001",
        ),
        "WPUIAC425SNW": (
            "018f2f9b-7c30-7981-b541-1a987c88f301",
            "018f2f9b-7c30-7981-b541-1a987c88f302",
            "ai-local-runtime-gate-iac425-001",
        ),
        "WPUIAC606SNW": (
            "018f2f9b-7c30-7981-b541-1a987c88f401",
            "018f2f9b-7c30-7981-b541-1a987c88f402",
            "ai-local-runtime-gate-iac606-001",
        ),
    }
    return [
        RuntimeScenario(
            model_code=model_code,
            raw_symptom=str(positive_by_model[model_code]["query"]),
            inquiry_id=trace_values[model_code][0],
            correlation_id=trace_values[model_code][1],
            ai_request_id=trace_values[model_code][2],
        )
        for model_code in sorted(profile.approved_model_codes)
    ]


def verify_local_runtime(
    router: Any | None = None,
    *,
    environment_id: str | None,
) -> dict[str, Any]:
    """검증 Profile의 Canonical Identity·Retriever·Provider를 함께 확인한다."""

    evidence_environment_id = _validated_environment_id(environment_id)
    source_identity = _git_identity()
    if source_identity["git_dirty"]:
        raise LocalRuntimeFailure("Runtime Evidence는 Clean Worktree에서만 생성할 수 있습니다.")
    python_version = platform.python_version()
    if python_version != EXPECTED_PYTHON_VERSION:
        raise LocalRuntimeFailure("Runtime Evidence의 Python Version이 승인값과 다릅니다.")

    _required_environment("OPENAI_API_KEY")
    _required_environment("AI_VECTOR_DSN")
    configured_embedding_revision = _required_environment("AI_EMBEDDING_REVISION")
    configured_table = _required_environment("AI_VECTOR_TABLE_NAME")
    configured_model = _required_environment("AI_LLM_MODEL")
    configured_runtime = _required_environment("AI_PIPELINE_RUNTIME").strip().lower()
    configured_transport = _required_environment("AI_RETRIEVAL_TRANSPORT").strip().lower()
    configured_profile = _required_environment("AI_RAG_RUNTIME_PROFILE").strip()
    configured_provider_base_url = os.getenv(
        "OPENAI_BASE_URL",
        DEFAULT_OPENAI_BASE_URL,
    ).rstrip("/")
    if configured_table != EXPECTED_TABLE:
        raise LocalRuntimeFailure("팀 Runtime 대상이 승인된 읽기 전용 View가 아닙니다.")
    if configured_model != EXPECTED_MODEL:
        raise LocalRuntimeFailure("LLM 모델이 승인된 Runtime Identity와 일치하지 않습니다.")
    if configured_embedding_revision != EXPECTED_EMBEDDING_REVISION:
        raise LocalRuntimeFailure("Embedding Revision이 승인된 Runtime Identity와 다릅니다.")
    if configured_provider_base_url != DEFAULT_OPENAI_BASE_URL:
        raise LocalRuntimeFailure("공식 OpenAI Provider Endpoint가 아닌 설정은 이 Gate에서 검증하지 않습니다.")
    if configured_runtime not in {"single_rag", "multi_agent"}:
        raise LocalRuntimeFailure("증거 대상 Pipeline Runtime이 올바르지 않습니다.")
    if configured_transport not in {"direct", "mcp"}:
        raise LocalRuntimeFailure("증거 대상 Retrieval Transport가 올바르지 않습니다.")

    profile = resolve_rag_runtime_profile()
    if configured_profile != profile.name:
        raise LocalRuntimeFailure("명시한 RAG Profile과 실제 Runtime Profile이 다릅니다.")
    approved_ids_by_model = _identity_by_model(profile)
    if router is None:
        if not warmup_configured_search_service():
            raise LocalRuntimeFailure("팀 pgvector 검색 서비스를 Warmup하지 못했습니다.")
        router = PipelineRouter()

    verified_models: list[str] = []
    evidence_ids: list[str] = []
    provider_models: set[str] = set()
    runtime_executions: list[dict[str, object]] = []
    total_tokens = 0
    for scenario in _runtime_scenarios(profile):
        result = router.run_pipeline(
            inquiry_id=scenario.inquiry_id,
            correlation_id=scenario.correlation_id,
            ai_request_id=scenario.ai_request_id,
            state_version=1,
            raw_symptom=scenario.raw_symptom,
            model_code=scenario.model_code,
            selected_symptoms=[],
            previous_answers=[],
        )
        response = result.to_analysis_result()
        _validate_response_identity(response, scenario)
        if response.status.value != "SUCCEEDED" or response.failure_stage is not None:
            raise LocalRuntimeFailure("Local Pipeline이 SUCCEEDED로 완료되지 않았습니다.")
        if not response.evidence_references:
            raise LocalRuntimeFailure("공식 Canonical Child Evidence를 확인하지 못했습니다.")

        allowed_ids = approved_ids_by_model[scenario.model_code]
        scenario_ids = [item.chunk_id for item in response.evidence_references]
        if any(chunk_id not in allowed_ids for chunk_id in scenario_ids):
            raise LocalRuntimeFailure("요청 모델과 다른 Canonical Child가 반환되었습니다.")
        if any(
            item.verification_status.value != "official_verified"
            for item in response.evidence_references
        ):
            raise LocalRuntimeFailure("공식 검증되지 않은 Evidence가 반환되었습니다.")

        metadata = result.context.model_metadata
        actual_model = metadata.model_name
        if actual_model != configured_model and not actual_model.startswith(
            f"{configured_model}-"
        ):
            raise LocalRuntimeFailure("실제 Provider 모델이 승인된 모델 계열과 다릅니다.")
        if metadata.prompt_version != PROMPT_VERSION:
            raise LocalRuntimeFailure("실제 Prompt Version이 Runtime Identity와 다릅니다.")
        if metadata.tokens_used is None or metadata.tokens_used <= 0:
            raise LocalRuntimeFailure("실제 LLM Token 사용 증거가 없습니다.")

        verified_models.append(scenario.model_code)
        evidence_ids.extend(scenario_ids)
        provider_models.add(actual_model)
        total_tokens += metadata.tokens_used
        runtime_executions.append(
            {
                "model_code": scenario.model_code,
                **_runtime_execution_evidence(
                    result,
                    expected_runtime=configured_runtime,
                    scenario=scenario,
                    response=response,
                ),
            }
        )

    evidence = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS",
        "evidence_scope": "LOCAL_RETRIEVER_PROVIDER_RUNTIME",
        "environment_id": evidence_environment_id,
        "source": source_identity,
        "python_version": python_version,
        "pipeline_runtime": configured_runtime,
        "retrieval_transport": configured_transport,
        "database_relation": configured_table,
        "database_query_status": "VERIFIED_BY_RETURNED_CANONICAL_EVIDENCE",
        "database_row_count": None,
        "database_row_count_status": "NOT_VERIFIED_BY_THIS_GATE",
        "database_readonly_permission_status": "NOT_VERIFIED_BY_THIS_GATE",
        "runtime_profile": profile.name,
        "activation_scope": profile.activation_scope,
        "public_runtime_activation": (
            "HOLD" if profile.name == "three_model_integration" else "ACTIVE_MVP"
        ),
        "public_runtime_activation_source": "RAG_PROFILE_POLICY",
        "public_deployment_status": "NOT_VERIFIED_BY_THIS_GATE",
        "identity_chunk_count": sum(
            len(values) for values in approved_ids_by_model.values()
        ),
        "identity_chunk_count_source": "CANONICAL_IDENTITY_FILE_EXPECTATION",
        "verified_model_codes": sorted(verified_models),
        "embedding_revision": configured_embedding_revision,
        "provider_adapter": "OPENAI_RESPONSES",
        "provider_endpoint_class": "OPENAI_PUBLIC_API",
        "provider_models": sorted(provider_models),
        "prompt_version": PROMPT_VERSION,
        "tokens_used": total_tokens,
        "evidence_count": len(evidence_ids),
        "evidence_unique_count": len(set(evidence_ids)),
        "evidence_id_set_sha256": _identifier_set_sha256(evidence_ids),
        "runtime_executions": runtime_executions,
        "owner_evidence_boundaries": {
            "harness_hitl_consultation_handoff": "OWNER_EVIDENCE_REQUIRED",
            "backend_same_inquiry_persistence": "NOT_VERIFIED_BY_THIS_GATE",
            "web_mobile_projection": "NOT_VERIFIED_BY_THIS_GATE",
        },
    }
    evidence["integrity"] = {
        "algorithm": "SHA-256",
        "canonicalization": "UTF8_JSON_SORT_KEYS_COMPACT_EXCLUDING_INTEGRITY",
        "payload_sha256": _canonical_json_sha256(evidence),
    }
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(
        description="실제 Retriever·Provider Runtime의 정제된 증거를 생성합니다."
    )
    parser.add_argument(
        "--environment-id",
        default=os.getenv("AI_EVIDENCE_ENVIRONMENT_ID"),
        help="Secret이 아닌 실행 환경 식별자(영문 대문자·숫자·._-)",
    )
    args = parser.parse_args()
    try:
        result = verify_local_runtime(
            environment_id=args.environment_id,
        )
    except LocalRuntimeFailure as exc:
        print(json.dumps({"result": "FAIL", "message": str(exc)}, ensure_ascii=True))
        return 1
    except Exception:
        print(
            json.dumps(
                {"result": "FAIL", "message": "Local Runtime 실행에 실패했습니다."},
                ensure_ascii=True,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
