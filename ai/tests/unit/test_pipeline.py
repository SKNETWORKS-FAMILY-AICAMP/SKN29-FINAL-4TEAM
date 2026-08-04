"""단일 RAG 파이프라인 및 오케스트레이터 단위 테스트."""

import os
import yaml
import pytest
from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.retrieval import (
    IndexManifest,
    RetrievalConfigurationError,
    RetrievalExecutionError,
    RetrievalOutcome,
    RetrievedChunk,
)
from ai.app.schemas.common import RiskLevel, UsageGuidanceStatus


class EmptySearchService:
    def search(self, *args, **kwargs):
        return []


class FailingSearchService:
    def __init__(self):
        self.calls = 0

    def search(self, *args, **kwargs):
        self.calls += 1
        raise ConnectionError("test-only vector failure")


class NonRetryableFailingSearchService:
    def __init__(self):
        self.calls = 0

    def search(self, *args, **kwargs):
        self.calls += 1
        raise ValueError("test-only invalid provider result")


class EvidenceSearchService:
    def search(self, *args, **kwargs):
        return [
            RetrievedChunk(
                chunk_id="RAG-WPUJAC104DWH-COLD-TEST",
                document_title="WPU-JAC104D 사용설명서",
                document_version="REV.00",
                page=37,
                page_refs=[37],
                manual_model="WPUJAC104DWH",
                model_code="WPUJAC104DWH",
                product_generation="D",
                content="냉수 온도가 높으면 잠시 기다린 뒤 다시 확인합니다.",
                similarity_score=0.91,
                official_url="https://example.invalid/official-manual",
                verification_status="official_verified",
                allowed_use=True,
            )
        ]


class FlakySearchService:
    def __init__(self):
        self.calls = 0

    def search(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise ConnectionError("test-only transient vector failure")
        return EvidenceSearchService().search(*args, **kwargs)


def test_single_rag_pipeline_execution():
    """단일 RAG 오케스트레이터 전체 Stage(1~5) 구동 테스트"""
    router = PipelineRouter()

    # 1. 누수 위험 시나리오 실행
    result = router.run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b305",
        correlation_id="corr-pipeline-test",
        ai_request_id="ai-req-pipeline-test",
        state_version=1,
        raw_symptom="정수기 밑 바닥에 물이 새서 누수가 심합니다.",
        model_code="WPUJAC104DWH",
        selected_symptoms=["누수"],
        previous_answers=[]
    )

    assert result.success is True
    analysis_res = result.to_analysis_result()

    # Stage 1: 구조화 확인
    assert analysis_res.structured_symptom.symptom_type == "누수"

    # Stage 2: 명시적 위험 감지 확인
    assert analysis_res.safety_assessment.risk_level == RiskLevel.DANGER
    assert analysis_res.safety_assessment.requires_consultation is True

    # 위험 입력은 일반 검색·생성 경로보다 먼저 분기한다.
    assert analysis_res.evidence_references == []

    # Stage 4: 사용 안내 상태 TOTAL_STOP 확인
    assert analysis_res.usage_guidance.guidance_status == UsageGuidanceStatus.TOTAL_STOP

    # 내부 처리 트레이스는 공개 DTO가 아니라 내부 Context에만 남는다.
    assert [trace.stage for trace in result.context.processing_traces] == [
        "STRUCTURING", "SAFETY_CHECK", "GENERATING", "VALIDATING"
    ]
    assert not hasattr(analysis_res, "processing_traces")


def test_prompt_registry_and_templates_exist():
    """프롬프트 Registry 및 템플릿 파일 존재 검증"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    prompts_dir = os.path.join(base_dir, "prompts")

    registry_path = os.path.join(prompts_dir, "prompt_registry.yaml")
    assert os.path.exists(registry_path)

    with open(registry_path, "r", encoding="utf-8") as f:
        registry = yaml.safe_load(f)

    assert "tasks" in registry
    assert "symptom_structuring" in registry["tasks"]

    # 템플릿 원문 존재 확인
    sys_txt = os.path.join(prompts_dir, "symptom_structuring", "v1", "system.txt")
    user_txt = os.path.join(prompts_dir, "symptom_structuring", "v1", "user_template.txt")
    assert os.path.exists(sys_txt)
    assert os.path.exists(user_txt)


def test_no_evidence_uses_pending_consultation_branch():
    """정상 검색 결과 0건이면 자가조치를 만들지 않고 상담으로 전환한다."""
    result = PipelineRouter(search_service=EmptySearchService()).run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b306",
        correlation_id="corr-no-evidence",
        ai_request_id="ai-req-no-evidence",
        state_version=2,
        raw_symptom="처음 보는 알 수 없는 표시가 나타났습니다.",
        model_code="WPUJAC104DWH",
    )
    response = result.to_analysis_result()
    assert response.evidence_references == []
    assert response.usage_guidance.guidance_status == UsageGuidanceStatus.PENDING_CONSULTATION
    assert response.safety_assessment.risk_level != RiskLevel.DANGER
    assert response.status.value == "FALLBACK"
    assert response.failure_stage.value == "RETRIEVING"
    assert result.context.retrieval_outcome == RetrievalOutcome.NO_MATCH


def test_vector_store_not_configured_is_not_reported_as_no_match():
    with pytest.raises(RetrievalConfigurationError, match="설정되지 않아"):
        PipelineRouter(search_service=None).run_pipeline(
            inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b307",
            correlation_id="corr-vector-not-configured",
            ai_request_id="ai-req-vector-not-configured",
            state_version=1,
            raw_symptom="냉수가 미지근합니다.",
            model_code="WPUJAC104DWH",
        )


def test_configured_search_failure_is_typed_separately_from_no_match():
    service = FailingSearchService()
    with pytest.raises(RetrievalExecutionError, match="검색 실행에 실패") as raised:
        PipelineRouter(search_service=service).run_pipeline(
            inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b308",
            correlation_id="corr-vector-failed",
            ai_request_id="ai-req-vector-failed",
            state_version=1,
            raw_symptom="냉수가 미지근합니다.",
            model_code="WPUJAC104DWH",
        )
    assert service.calls == 2
    assert raised.value.retry_count == 1
    assert raised.value.retryable is True


def test_transient_search_failure_retries_once_then_succeeds():
    service = FlakySearchService()
    result = PipelineRouter(search_service=service).run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b315",
        correlation_id="corr-vector-retry-success",
        ai_request_id="ai-req-vector-retry-success",
        state_version=1,
        raw_symptom="냉수가 미지근합니다.",
        model_code="WPUJAC104DWH",
    )

    response = result.to_analysis_result()
    retrieval_trace = next(
        trace for trace in result.context.processing_traces
        if trace.stage.value == "RETRIEVING"
    )
    assert service.calls == 2
    assert response.status.value == "SUCCEEDED"
    assert response.retry_count == 1
    assert retrieval_trace.retry_count == 1


def test_non_transient_search_failure_is_not_retried():
    service = NonRetryableFailingSearchService()
    with pytest.raises(RetrievalExecutionError) as raised:
        PipelineRouter(search_service=service).run_pipeline(
            inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b316",
            correlation_id="corr-vector-non-retryable",
            ai_request_id="ai-req-vector-non-retryable",
            state_version=1,
            raw_symptom="냉수가 미지근합니다.",
            model_code="WPUJAC104DWH",
        )

    assert service.calls == 1
    assert raised.value.retry_count == 0
    assert raised.value.retryable is False


def test_configured_search_with_evidence_is_available():
    result = PipelineRouter(search_service=EvidenceSearchService()).run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b310",
        correlation_id="corr-vector-available",
        ai_request_id="ai-req-vector-available",
        state_version=1,
        raw_symptom="냉수가 미지근합니다.",
        model_code="WPUJAC104DWH",
    )

    response = result.to_analysis_result()
    assert response.status.value == "SUCCEEDED"
    assert len(response.evidence_references) == 1
    assert result.context.retrieval_outcome == RetrievalOutcome.AVAILABLE


def test_danger_path_does_not_require_vector_store():
    result = PipelineRouter(search_service=None).run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b309",
        correlation_id="corr-danger-no-vector",
        ai_request_id="ai-req-danger-no-vector",
        state_version=1,
        raw_symptom="정수기 전원선 주변에 심한 누수가 발생했습니다.",
        model_code="WPUJAC104DWH",
        selected_symptoms=["누수"],
    )

    response = result.to_analysis_result()
    assert response.usage_guidance.guidance_status == UsageGuidanceStatus.TOTAL_STOP
    assert result.context.retrieval_outcome == RetrievalOutcome.NOT_RUN


def test_vector_dsn_requires_pinned_embedding_revision(monkeypatch):
    monkeypatch.setenv("AI_VECTOR_DSN", "postgresql://configured-but-not-connected")
    monkeypatch.delenv("AI_EMBEDDING_REVISION", raising=False)
    router = PipelineRouter()
    with pytest.raises(RetrievalConfigurationError, match="AI_EMBEDDING_REVISION"):
        router.run_pipeline(
            inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b311",
            correlation_id="corr-missing-revision",
            ai_request_id="ai-req-missing-revision",
            state_version=1,
            raw_symptom="냉수가 미지근합니다.",
        )


def test_vector_dsn_requires_index_manifest(monkeypatch):
    monkeypatch.setenv("AI_VECTOR_DSN", "postgresql://configured-but-not-connected")
    monkeypatch.setenv("AI_EMBEDDING_REVISION", "a" * 40)
    monkeypatch.setattr(IndexManifest, "load_manifest", staticmethod(lambda path: None))
    router = PipelineRouter()
    with pytest.raises(RetrievalConfigurationError, match="Index Manifest"):
        router.run_pipeline(
            inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b312",
            correlation_id="corr-missing-manifest",
            ai_request_id="ai-req-missing-manifest",
            state_version=1,
            raw_symptom="냉수가 미지근합니다.",
        )


def test_vector_manifest_revision_mismatch_is_configuration_error(monkeypatch):
    monkeypatch.setenv("AI_VECTOR_DSN", "postgresql://configured-but-not-connected")
    monkeypatch.setenv("AI_EMBEDDING_REVISION", "a" * 40)
    monkeypatch.setattr(
        IndexManifest,
        "load_manifest",
        staticmethod(lambda path: IndexManifest(
            model_revision="b" * 40,
            chunk_set_sha256="c" * 64,
        )),
    )
    router = PipelineRouter()
    with pytest.raises(RetrievalConfigurationError, match="Manifest와 일치하지"):
        router.run_pipeline(
            inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b313",
            correlation_id="corr-manifest-mismatch",
            ai_request_id="ai-req-manifest-mismatch",
            state_version=1,
            raw_symptom="냉수가 미지근합니다.",
        )


def test_danger_path_skips_partial_vector_configuration_error(monkeypatch):
    monkeypatch.setenv("AI_VECTOR_DSN", "postgresql://configured-but-not-connected")
    monkeypatch.delenv("AI_EMBEDDING_REVISION", raising=False)
    result = PipelineRouter().run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b314",
        correlation_id="corr-danger-partial-config",
        ai_request_id="ai-req-danger-partial-config",
        state_version=1,
        raw_symptom="전원선 주변에 누수가 발생했습니다.",
        selected_symptoms=["누수"],
    )

    assert result.to_analysis_result().usage_guidance.guidance_status == UsageGuidanceStatus.TOTAL_STOP
    assert result.context.retrieval_outcome == RetrievalOutcome.NOT_RUN
