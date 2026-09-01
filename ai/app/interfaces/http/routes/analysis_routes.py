"""증상 분석 API 라우터 모듈."""

import asyncio
import os
import time
from threading import BoundedSemaphore
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Header,
    Query,
    Request,
    Response,
)
from ..request_models import SymptomAnalysisApiRequest
from ..errors import AiServiceError
from ..runtime_policy import get_runtime_policy
from ....orchestration.pipeline_router import PipelineRouter
from ....integrations.backend.handoff_client import (
    handoff_delivery_enabled,
    publish_consultation_handoff,
)
from ....generation.customer_guidance.guidance_generator import (
    GuidanceGenerationExecutionError,
)
from ....retrieval import RetrievalConfigurationError, RetrievalExecutionError
from ....common.timeout import CancellationToken, PipelineStageTimeoutError
from ....schemas.common import AiStage, RiskLevel, UsageGuidanceStatus
from ....schemas.consultation_cause_ledger import (
    AnalysisConsultationEnvelope,
    ConsultationCauseLedgerBuildError,
    build_analysis_consultation_envelope,
)
from ....schemas.guidance import UsageGuidance
from ....schemas.pipeline import SymptomAnalysisResult
from ....schemas.safety import SafetyAssessment
from ....schemas.symptom import StructuredSymptom
from ..structured_logging import log_analysis_event

router = APIRouter(prefix="/api/v1/ai", tags=["Analysis"])


def _deliver_handoff_background(handoff) -> None:
    """Publish after the analysis response without surfacing transport failure."""

    result = publish_consultation_handoff(handoff)
    log_analysis_event(
        "handoff_delivery",
        inquiry_id=handoff.inquiry_id,
        correlation_id=handoff.correlation_id,
        ai_request_id=handoff.ai_request_id,
        stage="HANDOFF",
        status=result.status.value,
        retry_count=max(result.attempts - 1, 0),
        error_code=(
            result.failure_kind.value
            if result.failure_kind is not None
            else None
        ),
    )


def _schedule_handoff_delivery(background_tasks, pipeline_result) -> bool:
    """Queue only an internal sanitized HandoffResult, never the public DTO."""

    reliability = getattr(pipeline_result, "reliability_runtime", None)
    harness_runtime = getattr(reliability, "harness_runtime", None)
    handoff = getattr(harness_runtime, "handoff", None)
    if handoff is None or not handoff_delivery_enabled():
        return False

    # Starlette executes BackgroundTasks after sending the response. Backend
    # can therefore terminalize AIRun before its internal Handoff API checks it.
    background_tasks.add_task(_deliver_handoff_background, handoff)
    return True


def _optional_environment(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _build_runtime_envelope(
    result: SymptomAnalysisResult,
    pipeline_result,
) -> AnalysisConsultationEnvelope:
    """Bind the public 4.0.0 result to deterministic internal Ledger v1."""

    reliability = getattr(pipeline_result, "reliability_runtime", None)
    harness_runtime = getattr(reliability, "harness_runtime", None)
    harness = getattr(harness_runtime, "harness", None)
    verification = getattr(harness, "verification", None)
    issues = getattr(verification, "issues", []) or []
    issue_codes = [
        getattr(getattr(issue, "code", None), "value", "")
        for issue in issues
    ]
    context = getattr(pipeline_result, "context", None)
    metadata = getattr(context, "model_metadata", None)
    return build_analysis_consultation_envelope(
        result,
        runtime_name=pipeline_result.runtime_name,
        harness_issue_codes=issue_codes,
        execution_commit_sha=_optional_environment("RELEASE_SHA"),
        model_provider=_optional_environment("AI_MODEL_PROVIDER"),
        model_name=(
            _optional_environment("AI_MODEL_NAME")
            or getattr(metadata, "model_name", None)
        ),
        prompt_version=(
            _optional_environment("AI_PROMPT_VERSION")
            or getattr(metadata, "prompt_version", None)
        ),
        prompt_sha256=_optional_environment("AI_PROMPT_SHA256"),
    )


def _ledger_build_error(
    req: SymptomAnalysisApiRequest,
) -> AiServiceError:
    return AiServiceError(
        code="AI-FAILED-01",
        http_status=503,
        message="AI 내부 분석 Envelope를 안전하게 생성하지 못했습니다.",
        retryable=False,
        failure_stage=AiStage.VALIDATING,
        correlation_id=req.correlation_id,
        inquiry_id=req.inquiry_id,
        ai_request_id=req.ai_request_id,
        state_version=req.state_version,
        retry_count=0,
    )


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


@router.post(
    "/analyze",
    response_model=AnalysisConsultationEnvelope | SymptomAnalysisResult,
    summary="증상 분석 및 사용 안내 통합 API",
)
async def analyze_symptom(
    req: SymptomAnalysisApiRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    mode: str = Query("local", pattern="^(mock|local)$", description="실행 모드"),
    x_correlation_id: UUID | None = Header(None, alias="X-Correlation-ID"),
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
    response.headers["X-Correlation-ID"] = str(req.correlation_id)
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
            model_code=req.model_code,
            fallback_reason_code=None,
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
                matched_safety_rule_ids=[],
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
        # Mock remains the unchanged public 4.0.0 contract fixture. The actual
        # local Runtime below returns the internal 1.0.0 Envelope.
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
            retry_count=cancellation_token.retry_count,
        ) from exc
    except PipelineStageTimeoutError as exc:
        cancellation_token.cancel()
        try:
            failure_stage = AiStage(exc.stage)
        except ValueError:
            failure_stage = AiStage.CANCELLED
        raise AiServiceError(
            code="AI-TIMEOUT-01",
            http_status=504,
            message="AI 서비스 단계 처리 시간이 초과되었습니다.",
            retryable=True,
            failure_stage=failure_stage,
            correlation_id=req.correlation_id,
            inquiry_id=req.inquiry_id,
            ai_request_id=req.ai_request_id,
            state_version=req.state_version,
            retry_count=cancellation_token.retry_count,
        ) from exc
    except RetrievalConfigurationError as exc:
        raise AiServiceError(
            code="AI-FAILED-01",
            http_status=503,
            message="AI 검색 구성이 완료되지 않아 근거 검색을 시작할 수 없습니다.",
            retryable=False,
            failure_stage=AiStage.RETRIEVING,
            correlation_id=req.correlation_id,
            inquiry_id=req.inquiry_id,
            ai_request_id=req.ai_request_id,
            state_version=req.state_version,
            retry_count=0,
        ) from exc
    except RetrievalExecutionError as exc:
        raise AiServiceError(
            code="AI-FAILED-01",
            http_status=503,
            message="AI 근거 검색을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.",
            retryable=exc.retryable,
            failure_stage=AiStage.RETRIEVING,
            correlation_id=req.correlation_id,
            inquiry_id=req.inquiry_id,
            ai_request_id=req.ai_request_id,
            state_version=req.state_version,
            retry_count=exc.retry_count,
        ) from exc
    except GuidanceGenerationExecutionError as exc:
        raise AiServiceError(
            code="AI-TIMEOUT-01" if exc.timed_out else "AI-FAILED-01",
            http_status=504 if exc.timed_out else 503,
            message=(
                "AI 안내 생성 시간이 초과되었습니다."
                if exc.timed_out
                else "AI 안내 생성을 완료하지 못했습니다."
            ),
            retryable=exc.retryable,
            failure_stage=AiStage.GENERATING,
            correlation_id=req.correlation_id,
            inquiry_id=req.inquiry_id,
            ai_request_id=req.ai_request_id,
            state_version=req.state_version,
            retry_count=exc.retry_count,
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
    try:
        envelope = _build_runtime_envelope(result, pipeline_result)
    except ConsultationCauseLedgerBuildError as exc:
        raise _ledger_build_error(req) from exc
    _schedule_handoff_delivery(background_tasks, pipeline_result)
    log_fields["retry_count"] = result.retry_count
    log_analysis_event(
        "analysis_completed",
        stage=AiStage.COMPLETED.value,
        status=result.status.value,
        latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
        **log_fields,
    )
    return envelope
