"""근거 적용 조건 확인 전 고객 답변을 기다리는 공용 Stage."""

import time

from ...schemas import (
    AiStage,
    ProcessingTrace,
    RiskLevel,
    SafetyPriority,
    UsageGuidance,
    UsageGuidanceStatus,
)
from ..pipeline_context import PipelineContext
from ..clarification_policy import unresolved_answered_required_fields


def execute_questionnaire_pending_stage(ctx: PipelineContext) -> None:
    """LLM 안내 없이 기존 추가 질문에 대한 고객 답변 대기를 반환한다."""

    started_at = time.perf_counter()
    if ctx.safety_assessment is None:
        raise RuntimeError("문진 대기 전에 안전 평가가 필요합니다.")
    cannot_confirm = bool(unresolved_answered_required_fields(ctx))
    if cannot_confirm:
        ctx.followup_questions = []
    ctx.awaiting_customer_input = True
    ctx.safety_assessment = ctx.safety_assessment.model_copy(
        update={
            "risk_level": RiskLevel.CAUTION,
            "priority": SafetyPriority.CONSULTATION_RECOMMENDED,
            "requires_consultation": True,
            "safety_reason": (
                "필수 정보를 확인하지 못해 상담 확인이 필요합니다."
                if cannot_confirm else "추가 정보 확인 전 안내 생성을 보류합니다."
            ),
        }
    )
    ctx.usage_guidance = UsageGuidance(
        guidance_status=UsageGuidanceStatus.PENDING_CONSULTATION,
        message=("필수 정보를 확인하지 못했습니다. 전문 상담을 통해 확인해 주세요."
                 if cannot_confirm else "안전한 안내를 위해 추가 정보가 필요합니다. 표시된 질문에 답변해 주세요."),
        restricted_functions=["근거 확인 전 자가조치 안내"],
        next_actions=["전문 상담 연결을 요청해 주세요." if cannot_confirm else "추가 질문에 답변해 주세요."],
    )
    ctx.processing_traces.append(
        ProcessingTrace(
            stage=AiStage.GENERATING,
            status="SUCCEEDED",
            latency_ms=round((time.perf_counter() - started_at) * 1000.0, 2),
            retry_count=ctx.retry_count,
        )
    )
