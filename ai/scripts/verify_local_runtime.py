"""실제 OpenAI·팀 pgvector Local Pipeline의 Runtime Identity를 검증한다."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
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


def verify_local_runtime(router: Any | None = None) -> dict[str, Any]:
    """검증 Profile의 Canonical Identity·Retriever·Provider를 함께 확인한다."""

    _required_environment("OPENAI_API_KEY")
    _required_environment("AI_VECTOR_DSN")
    _required_environment("AI_EMBEDDING_REVISION")
    configured_table = _required_environment("AI_VECTOR_TABLE_NAME")
    configured_model = _required_environment("AI_LLM_MODEL")
    if configured_table != EXPECTED_TABLE:
        raise LocalRuntimeFailure("팀 Runtime 대상이 승인된 읽기 전용 View가 아닙니다.")
    if configured_model != EXPECTED_MODEL:
        raise LocalRuntimeFailure("LLM 모델이 승인된 Runtime Identity와 일치하지 않습니다.")

    profile = resolve_rag_runtime_profile()
    approved_ids_by_model = _identity_by_model(profile)
    if router is None:
        if not warmup_configured_search_service():
            raise LocalRuntimeFailure("팀 pgvector 검색 서비스를 Warmup하지 못했습니다.")
        router = PipelineRouter()

    verified_models: list[str] = []
    evidence_ids: list[str] = []
    provider_models: set[str] = set()
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

    return {
        "result": "PASS",
        "runtime_profile": profile.name,
        "activation_scope": profile.activation_scope,
        "public_runtime_activation": (
            "HOLD" if profile.name == "three_model_integration" else "ACTIVE_MVP"
        ),
        "identity_chunk_count": sum(
            len(values) for values in approved_ids_by_model.values()
        ),
        "verified_model_codes": sorted(verified_models),
        "provider_models": sorted(provider_models),
        "prompt_version": PROMPT_VERSION,
        "tokens_used": total_tokens,
        "evidence_count": len(evidence_ids),
        "evidence_ids": sorted(set(evidence_ids)),
    }


def main() -> int:
    try:
        result = verify_local_runtime()
    except LocalRuntimeFailure as exc:
        print(json.dumps({"result": "FAIL", "message": str(exc)}, ensure_ascii=False))
        return 1
    except Exception:
        print(
            json.dumps(
                {"result": "FAIL", "message": "Local Runtime 실행에 실패했습니다."},
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
