"""실제 OpenAI·팀 pgvector Local Pipeline의 내부 Runtime Identity를 검증한다."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from ai.app.generation.customer_guidance.prompt_identity import PROMPT_VERSION
from ai.app.orchestration.pipeline_router import (
    PipelineRouter,
    warmup_configured_search_service,
)


INQUIRY_ID = "018f2f9b-7c30-7981-b541-1a987c88f101"
CORRELATION_ID = "018f2f9b-7c30-7981-b541-1a987c88f102"
AI_REQUEST_ID = "ai-local-runtime-gate-20260813-001"
EXPECTED_MODEL = "gpt-4.1-mini"
EXPECTED_TABLE = "backend_ai_rag_chunks_v1"
EXPECTED_EVIDENCE_ID = "RAG-WPUJAC104DWH-LOW-FLOW-001"


class LocalRuntimeFailure(RuntimeError):
    """실제 Local Runtime Gate 실패."""


def _required_environment(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise LocalRuntimeFailure(f"필수 환경변수가 없습니다: {name}")
    return value


def verify_local_runtime(router: Any | None = None) -> dict[str, Any]:
    """실제 Provider·Retriever 호출 결과와 내부 감사 Identity를 함께 검증한다."""

    _required_environment("OPENAI_API_KEY")
    _required_environment("AI_VECTOR_DSN")
    _required_environment("AI_EMBEDDING_REVISION")
    configured_table = _required_environment("AI_VECTOR_TABLE_NAME")
    configured_model = _required_environment("AI_LLM_MODEL")
    if configured_table != EXPECTED_TABLE:
        raise LocalRuntimeFailure("팀 Runtime 대상이 승인된 읽기 전용 View가 아닙니다.")
    if configured_model != EXPECTED_MODEL:
        raise LocalRuntimeFailure("LLM 모델이 승인된 Runtime Identity와 일치하지 않습니다.")

    if router is None:
        if not warmup_configured_search_service():
            raise LocalRuntimeFailure("팀 pgvector 검색 서비스를 Warmup하지 못했습니다.")
        router = PipelineRouter()
    result = router.run_pipeline(
        inquiry_id=INQUIRY_ID,
        correlation_id=CORRELATION_ID,
        ai_request_id=AI_REQUEST_ID,
        state_version=1,
        raw_symptom="냉수 출수량이 줄었습니다.",
        model_code="WPUJAC104DWH",
        selected_symptoms=["출수량 저하"],
        previous_answers=[],
    )
    response = result.to_analysis_result()
    if response.status.value != "SUCCEEDED" or response.failure_stage is not None:
        raise LocalRuntimeFailure("Local Pipeline이 SUCCEEDED로 완료되지 않았습니다.")

    evidence = next(
        (
            reference
            for reference in response.evidence_references
            if reference.chunk_id == EXPECTED_EVIDENCE_ID
        ),
        None,
    )
    if evidence is None or evidence.verification_status.value != "official_verified":
        raise LocalRuntimeFailure("승인된 Low-flow Evidence를 확인하지 못했습니다.")
    if response.usage_guidance.message != evidence.summary:
        raise LocalRuntimeFailure("LLM 안내가 승인 Evidence 추출 문장과 일치하지 않습니다.")

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

    return {
        "result": "PASS",
        "analysis_status": response.status.value,
        "failure_stage": None,
        "model_name": actual_model,
        "prompt_version": metadata.prompt_version,
        "tokens_used": metadata.tokens_used,
        "evidence_id": evidence.chunk_id,
        "correlation_id": str(response.correlation_id),
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
