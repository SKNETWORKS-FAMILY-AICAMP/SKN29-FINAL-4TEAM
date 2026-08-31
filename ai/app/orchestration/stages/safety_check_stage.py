"""명시적 안전 검사 Stage 모듈."""

import time
from ...safety import RiskClassifier
from ...schemas import AiStage, ProcessingTrace
from ..pipeline_context import PipelineContext


def execute_safety_check_stage(ctx: PipelineContext) -> None:
    """명시적 안전 분기 및 위험도 판정"""
    start_time = time.perf_counter()

    classifier = RiskClassifier()
    ctx.safety_assessment = classifier.classify(
        ctx.raw_symptom,
        ctx.selected_symptoms,
        ctx.safety_signals,
    )

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    ctx.processing_traces.append(
        ProcessingTrace(stage=AiStage.SAFETY_CHECK, status="SUCCEEDED", latency_ms=round(elapsed_ms, 2))
    )
