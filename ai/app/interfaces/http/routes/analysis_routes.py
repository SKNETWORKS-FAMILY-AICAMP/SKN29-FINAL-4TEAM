"""증상 분석 API 라우터 모듈."""

from fastapi import APIRouter, Query
from ..request_models import SymptomAnalysisApiRequest
from ....orchestration.pipeline_router import PipelineRouter
from ....schemas.common import RiskLevel, UsageGuidanceStatus
from ....schemas.guidance import UsageGuidance
from ....schemas.pipeline import SymptomAnalysisResult
from ....schemas.safety import SafetyAssessment
from ....schemas.symptom import StructuredSymptom

router = APIRouter(prefix="/api/v1/ai", tags=["Analysis"])


@router.post("/analyze", response_model=SymptomAnalysisResult, summary="증상 분석 및 사용 안내 통합 API")
async def analyze_symptom(
    req: SymptomAnalysisApiRequest,
    mode: str = Query("local", description="실행 모드 (mock: 고정 예시 데이터, local: 단일 RAG 오케스트레이터 가동)")
):
    """백엔드에서 호출하는 증상 분석·안전평가·RAG근거·사용안내 API"""

    # 1. Mock 모드 (연동 테스트용)
    if mode == "mock":
        return SymptomAnalysisResult(
            inquiry_id=req.inquiry_id,
            correlation_id=req.correlation_id,
            structured_symptom=StructuredSymptom(
                symptom_type="출수량 저하",
                occurrence_time="3일 전",
                target_water_type="냉수",
                occurrence_condition="버튼 누를 때 졸졸 나옴",
                accompanying_symptoms=req.selected_symptoms or ["출수 속도 저하"],
                actions_taken=[ans.answer_text for ans in req.previous_answers] or ["전원 재부팅"]
            ),
            missing_fields=[],
            followup_questions=[],
            safety_assessment=SafetyAssessment(
                risk_level=RiskLevel.CAUTION,
                priority="consultation_recommended",
                requires_consultation=False,
                detected_risks=["출수량 저하 소음"],
                safety_reason="일반 출수 미흡 감지"
            ),
            usage_guidance=UsageGuidance(
                guidance_status=UsageGuidanceStatus.PARTIAL_STOP,
                message="냉수 출수량이 미흡합니다. 필터 상태 및 자가 점검을 수행해 주세요.",
                restricted_functions=["냉수 출수량 점검 필요"],
                next_actions=["필터 교체 주기 확인", "원수 밸브 열림 확인"]
            ),
            evidence_references=[],
        )

    # 2. Local 모드 (단일 RAG LangGraph/파이프라인 오케스트레이터 가동)
    router_instance = PipelineRouter()
    previous_answers_list = [{"question_id": ans.question_id, "answer_text": ans.answer_text} for ans in req.previous_answers]

    pipeline_result = router_instance.run_pipeline(
        inquiry_id=req.inquiry_id,
        correlation_id=req.correlation_id,
        raw_symptom=req.raw_symptom,
        model_code=req.model_code,
        selected_symptoms=req.selected_symptoms,
        previous_answers=previous_answers_list
    )

    return pipeline_result.to_analysis_result()
