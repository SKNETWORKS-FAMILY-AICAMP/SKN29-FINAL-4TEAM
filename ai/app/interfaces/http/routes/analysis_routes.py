"""증상 분석 API 라우터 모듈."""

import asyncio
import os
import time
from threading import BoundedSemaphore

from fastapi import APIRouter, Header, Query, Request, Response
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


def _worker_limit() -> int:
    raw = os.getenv("AI_MAX_IN_FLIGHT_WORKERS", "2")
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("AI_MAX_IN_FLIGHT_WORKERS는 정수여야 합니다.") from exc
    if not 1 <= value <= 32:
        raise RuntimeError("AI_MAX_IN_FLIGHT_WORKERS는 1~32 범위여야 합니다.")
    return value


_WORKER_SLOTS = BoundedSemaphore(_worker_limit())


def _release_worker_slot(task: asyncio.Task, slots: BoundedSemaphore) -> None:
    """HTTP Timeout 뒤에도 실행 중인 Thread가 끝날 때까지 Slot을 유지한다."""
    try:
        if not task.cancelled():
            task.exception()
    finally:
        slots.release()


@router.post("/analyze", response_model=SymptomAnalysisResult, summary="증상 분석 및 사용 안내 통합 API")
async def analyze_symptom(
    req: SymptomAnalysisApiRequest,
    request: Request,
    response: Response,
    mode: str = Query("local", pattern="^(mock|local)$", description="실행 모드"),
    x_correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
):
    """백엔드에서 호출하는 증상 분석·안전평가·RAG근거·사용안내 API"""

    request.state.inquiry_id = req.inquiry_id
    request.state.correlation_id = req.correlation_id
    request.state.ai_request_id = req.ai_request_id
    request.state.state_version = req.state_version
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
    request.state.analysis_started_at = started_at
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
    worker_slots = _WORKER_SLOTS
    if not worker_slots.acquire(blocking=False):
        raise AiServiceError(
            code="AI-FAILED-01",
            http_status=503,
            message="AI 분석 작업이 포화 상태입니다. 잠시 후 다시 시도해 주세요.",
            retryable=True,
            failure_stage=AiStage.FAILED,
            correlation_id=req.correlation_id,
            inquiry_id=req.inquiry_id,
            ai_request_id=req.ai_request_id,
            state_version=req.state_version,
        )
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
        worker.add_done_callback(lambda task: _release_worker_slot(task, worker_slots))
        pipeline_result = await asyncio.wait_for(
            asyncio.shield(worker), timeout=policy.overall_timeout_seconds
        )
    except asyncio.TimeoutError as exc:
        cancellation_token.cancel()
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
        if "worker" not in locals():
            worker_slots.release()
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
    except BaseException:
        if "worker" not in locals():
            worker_slots.release()
        raise

    result = pipeline_result.to_analysis_result()
    log_analysis_event(
        "analysis_completed",
        stage=AiStage.COMPLETED.value,
        status=result.status.value,
        latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
        **log_fields,
    )
    return result
