"""단일 RAG 파이프라인 및 오케스트레이터 단위 테스트."""

import os
import yaml
import pytest
from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.schemas.common import RiskLevel, UsageGuidanceStatus


def test_single_rag_pipeline_execution():
    """단일 RAG 오케스트레이터 전체 Stage(1~5) 구동 테스트"""
    router = PipelineRouter()

    # 1. 누수 위험 시나리오 실행
    result = router.run_pipeline(
        inquiry_id="DEMO-INQ-005",
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
    """Vector Store 미설정 시 일반 자가조치를 만들지 않고 상담으로 전환한다."""
    result = PipelineRouter(search_service=None).run_pipeline(
        inquiry_id="DEMO-INQ-NO-EVIDENCE",
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


def test_vector_dsn_requires_pinned_embedding_revision(monkeypatch):
    monkeypatch.setenv("AI_VECTOR_DSN", "postgresql://configured-but-not-connected")
    monkeypatch.delenv("AI_EMBEDDING_REVISION", raising=False)
    with pytest.raises(RuntimeError, match="AI_EMBEDDING_REVISION"):
        PipelineRouter()
