"""증상 분석 API 라우터 모듈."""

import asyncio
import time

from fastapi import APIRouter, Header, Query, Response
from ..request_models import SymptomAnalysisApiRequest
from ..errors import AiServiceError
from ..runtime_policy import get_runtime_policy
from ....orchestration.pipeline_router import PipelineRouter
from ....common.timeout import CancellationToken
from ....schemas.common import AiStage, RiskLevel, UsageGuidanceStatus
from ....schemas.guidance import UsageGuidance
from ....schemas.pipeline import SymptomAnalysisResult
from ....schemas.safety import SafetyAssessment
from ....schemas.symptom import StructuredSymptom
from ..structured_logging import log_analysis_event

router = APIRouter(prefix="/api/v1/ai", tags=["Analysis"])


@router.post("/analyze", response_model=SymptomAnalysisResult, summary="증상 분석 및 사용 안내 통합 API")
async def analyze_symptom(
    req: SymptomAnalysisApiRequest,
    response: Response,
    mode: str = Query("local", pattern="^(mock|local)$", description="실행 모드"),
    x_correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
):
    """백엔드에서 호출하는 증상 분석·안전평가·RAG근거·사용안내 API"""

    if x_correlation_id is not None and x_correlation_id != req.correlation_id:
        raise AiServiceError(
            code="AI-VALIDATION-01",
            http_status=400,
            message="X-Correlation-ID Header와 Body의 correlation_id가 일치하지 않습니다.",
            retryable=False,
            failure_stage=AiStage.STRUCTURING,
            correlation_id=req.correlation_id,
            inquiry_id=req.inquiry_id,
            ai_request_id=req.ai_request_id,
            state_version=req.state_version,
        )
    response.headers["X-Correlation-ID"] = req.correlation_id
    started_at = time.perf_counter()
    log_fields = {
        "inquiry_id": req.inquiry_id,
        "correlation_id": req.correlation_id,
        "ai_request_id": req.ai_request_id,
        "state_version": req.state_version,
        "retry_count": 0,
    }
    log_analysis_event("analysis_started", stage=AiStage.STRUCTURING.value, status="STARTED", **log_fields)

    # 1. Mock 모드 (계약 연동 테스트 전용)
    if mode == "mock":
        result = SymptomAnalysisResult(
            inquiry_id=req.inquiry_id,
            correlation_id=req.correlation_id,
            ai_request_id=req.ai_request_id,
            state_version=req.state_version,
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
        log_analysis_event(
            "analysis_completed",
            stage=AiStage.COMPLETED.value,
            status="SUCCEEDED",
            latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            **log_fields,
        )
        return result

    # 2. Local 모드 (단일 RAG LangGraph/파이프라인 오케스트레이터 가동)
    router_instance = PipelineRouter()
    previous_answers_list = [{"question_id": ans.question_id, "answer_text": ans.answer_text} for ans in req.previous_answers]

    policy = get_runtime_policy()
    cancellation_token = CancellationToken()
    try:
        worker = asyncio.create_task(
            asyncio.to_thread(
                router_instance.run_pipeline,
                inquiry_id=req.inquiry_id,
                correlation_id=req.correlation_id,
                ai_request_id=req.ai_request_id,
                state_version=req.state_version,
                raw_symptom=req.raw_symptom,
                model_code=req.model_code,
                selected_symptoms=req.selected_symptoms,
                previous_answers=previous_answers_list,
                cancellation_token=cancellation_token,
            )
        )
        pipeline_result = await asyncio.wait_for(
            asyncio.shield(worker), timeout=policy.overall_timeout_seconds
        )
    except asyncio.TimeoutError as exc:
        cancellation_token.cancel()
        worker.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)
        log_analysis_event(
            "analysis_failed",
            stage=AiStage.CANCELLED.value,
            status="TIMEOUT",
            latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            error_code="AI-TIMEOUT-01",
            **log_fields,
        )
        raise AiServiceError(
            code="AI-TIMEOUT-01",
            http_status=504,
            message="AI 서비스 처리 시간이 초과되었습니다.",
            retryable=True,
            failure_stage=AiStage.CANCELLED,
            correlation_id=req.correlation_id,
            inquiry_id=req.inquiry_id,
            ai_request_id=req.ai_request_id,
            state_version=req.state_version,
            retry_count=0,
        ) from exc
    except Exception as exc:
        log_analysis_event(
            "analysis_failed",
            stage=AiStage.FAILED.value,
            status="FAILED",
            latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            error_code="AI-FAILED-01",
            **log_fields,
        )
        raise AiServiceError(
            code="AI-FAILED-01",
            http_status=503,
            message="AI 분석을 완료하지 못했습니다.",
            retryable=True,
            failure_stage=AiStage.FAILED,
            correlation_id=req.correlation_id,
            inquiry_id=req.inquiry_id,
            ai_request_id=req.ai_request_id,
            state_version=req.state_version,
            retry_count=0,
        ) from exc

    result = pipeline_result.to_analysis_result()
    log_analysis_event(
        "analysis_completed",
        stage=AiStage.COMPLETED.value,
        status=result.status.value,
        latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
        **log_fields,
    )
    return result
