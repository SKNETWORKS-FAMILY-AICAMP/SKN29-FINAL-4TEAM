"""3모델 RAG Runtime + Reliability Harness 공동 E2E Gate.

이 테스트는 3모델 Runtime이 실제로 활성화된 뒤 실행한다.

사전 조건:
* Backend official Evidence 53건 적재 완료 (15 / 19 / 19)
* Chunk / Embedding / Crosswalk / readonly View 53건 일치
* 3모델 index manifest 생성 및 Runtime 반영
* retrieval_policy.yaml 3모델 Active 승격
* Harness Runtime approval 3모델 승격

기본 테스트 실행에서는 외부 DB/LLM 의존성을 만들지 않도록 skip한다.
실제 공동 E2E 시 ``AI_THREE_MODEL_E2E=1``을 설정한다.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from ai.app.orchestration.harness.product_registry import (
    is_runtime_approved_model_code,
    resolve_product_generation,
)
from ai.app.orchestration.harness.verification_result import HarnessDecision
from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.retrieval.models.retrieval_query import RetrievalQuery
from ai.app.retrieval.runtime_profile import (
    RagRuntimeProfile,
    resolve_rag_runtime_profile,
)


THREE_MODEL_CASES = (
    (
        "WPUJAC104DWH",
        "정수기에서 물이 잘 나오지 않을 때 확인할 사항을 알려주세요.",
    ),
    (
        "WPUIAC425SNW",
        "얼음 정수기 사용 중 확인해야 할 기본 조작 방법을 알려주세요.",
    ),
    (
        "WPUIAC606SNW",
        "제품을 정상적으로 사용하는 방법을 공식 근거로 안내해주세요.",
    ),
)


def _require_three_model_e2e() -> None:
    if os.getenv("AI_THREE_MODEL_E2E") != "1":
        pytest.skip(
            "3모델 Runtime 활성화 후 AI_THREE_MODEL_E2E=1로 공동 E2E를 실행합니다."
        )


def _selected_three_model_profile() -> RagRuntimeProfile:
    """Require the explicit integration-only profile for this gated suite."""

    _require_three_model_e2e()
    profile = resolve_rag_runtime_profile()
    if profile.name != "three_model_integration":
        pytest.fail(
            "3모델 E2E에는 "
            "AI_RAG_RUNTIME_PROFILE=three_model_integration이 필요합니다."
        )
    if profile.activation_scope != "INTEGRATION_VERIFICATION_ONLY":
        pytest.fail(
            "3모델 E2E Profile의 통합검증 전용 계약이 유지되지 않았습니다."
        )
    return profile


def _runtime_router() -> PipelineRouter:
    _selected_three_model_profile()
    router = PipelineRouter()
    if router.retrieval_configuration_error is not None:
        pytest.fail("3모델 E2E용 Retrieval Runtime 설정이 유효하지 않습니다.")
    if router.search_service is None:
        pytest.fail("3모델 E2E에는 실제 pgvector Search Service가 필요합니다.")
    return router


def _run_pipeline(
    router: PipelineRouter,
    *,
    model_code: str,
    raw_symptom: str,
):
    return router.run_pipeline(
        inquiry_id=uuid4(),
        correlation_id=uuid4(),
        ai_request_id=f"three-model-e2e-{model_code}-{uuid4().hex[:8]}",
        state_version=1,
        raw_symptom=raw_symptom,
        model_code=model_code,
        runtime_name=os.getenv("AI_PIPELINE_RUNTIME", "single_rag"),
    )


def test_three_model_runtime_approval_is_active() -> None:
    """Selected integration profile must approve all three exact sales codes."""

    profile = _selected_three_model_profile()

    assert profile.approved_model_codes == frozenset(
        model_code for model_code, _query in THREE_MODEL_CASES
    )

    for model_code, _query in THREE_MODEL_CASES:
        assert is_runtime_approved_model_code(
            model_code,
            runtime_approved_model_codes=profile.approved_model_codes,
        ) is True


@pytest.mark.parametrize(("model_code", "query_text"), THREE_MODEL_CASES)
def test_exact_model_retrieval_never_returns_cross_product_evidence(
    model_code: str,
    query_text: str,
) -> None:
    """Pre-score exact sales-code 필터가 실제 pgvector 결과에도 적용되는지 검증."""

    router = _runtime_router()
    search_service = router.search_service
    assert search_service is not None

    results = search_service.search(
        RetrievalQuery(
            query_text=query_text,
            model_code=model_code,
            product_generation=resolve_product_generation(model_code),
            top_k=5,
        )
    )

    assert results, f"{model_code}의 공식 Evidence가 검색되지 않았습니다."
    assert all(result.model_code == model_code for result in results)
    assert all(result.verification_status == "official_verified" for result in results)
    assert all(result.allowed_use for result in results)


@pytest.mark.parametrize(("model_code", "raw_symptom"), THREE_MODEL_CASES)
def test_three_model_pipeline_reaches_harness_without_cross_product_contamination(
    model_code: str,
    raw_symptom: str,
) -> None:
    """실제 Pipeline -> Retrieval -> Generation -> Harness 경로의 3모델 정상 케이스."""

    router = _runtime_router()
    result = _run_pipeline(
        router,
        model_code=model_code,
        raw_symptom=raw_symptom,
    )

    assert result.context.model_code == model_code
    assert result.reliability_runtime is not None

    reliability = result.reliability_runtime
    runtime = reliability.harness_runtime

    # 정상 근거가 존재하는 표준 E2E 입력에서는 다른 모델 Evidence가
    # Guard에 의해 차단되는 일이 없어야 한다.
    assert reliability.blocked_evidence_chunk_ids == []
    assert runtime.harness.decision == HarnessDecision.PASS
    assert runtime.handoff is None
    assert runtime.human_review is None
    assert result.context.evidence_references


def test_cross_product_fallback_is_not_used_when_target_model_has_no_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """한 모델의 검색 실패를 다른 모델 Evidence로 메우는 fallback을 금지한다.

    실제 운영 데이터에서 '검색 결과 없음'을 인위적으로 만들기 어렵기 때문에
    Search Service 결과만 최소한으로 제어한다. Pipeline/Harness Runtime은 실제
    구현을 그대로 사용한다.
    """

    router = _runtime_router()
    delegate = router.search_service
    assert delegate is not None

    target_model = "WPUIAC425SNW"
    other_model = "WPUIAC606SNW"

    other_results = delegate.search(
        RetrievalQuery(
            query_text="제품 정상 사용 방법",
            model_code=other_model,
            product_generation=resolve_product_generation(other_model),
            top_k=5,
        )
    )
    assert other_results

    original_search = delegate.search

    def contaminated_search(query, *, cancellation_token=None):
        if query.model_code == target_model:
            # 장애 상황을 가정해 다른 제품 결과만 반환한다.
            return other_results
        return original_search(query, cancellation_token=cancellation_token)

    monkeypatch.setattr(delegate, "search", contaminated_search)

    result = _run_pipeline(
        router,
        model_code=target_model,
        raw_symptom="제품 사용 방법을 알려주세요.",
    )

