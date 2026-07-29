"""출력 가드레일 및 Schema 검증 Stage 모듈."""

import time
from ...validation.safety import ProhibitedPhraseValidator, UsageGuidanceValidator
from ...schemas import ProcessingTrace
from ..pipeline_context import PipelineContext


def execute_validation_stage(ctx: PipelineContext) -> None:
    """금지 표현 가드레일 및 스키마 정합성 2차 검증"""
    start_time = time.perf_counter()

    validator = ProhibitedPhraseValidator()
    if ctx.usage_guidance and ctx.usage_guidance.message:
        is_valid, sanitized_msg, detected = validator.validate(ctx.usage_guidance.message)
        if not is_valid:
            ctx.usage_guidance.message = sanitized_msg
        UsageGuidanceValidator().validate(
            ctx.safety_assessment,
            ctx.usage_guidance,
            has_evidence=bool(ctx.evidence_references),
        )

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    ctx.processing_traces.append(
        ProcessingTrace(stage="validation_stage", status="success", latency_ms=round(elapsed_ms, 2))
    )
