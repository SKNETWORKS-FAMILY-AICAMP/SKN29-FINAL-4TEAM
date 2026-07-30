"""증상 필드 구조화 Stage 모듈."""

import time
from ...schemas import AiStage, ProcessingTrace, StructuredSymptom
from ..pipeline_context import PipelineContext


def execute_structuring_stage(ctx: PipelineContext) -> None:
    """고객 입력 증상을 표준 항목으로 구조화"""
    start_time = time.perf_counter()

    primary_type = ctx.selected_symptoms[0] if ctx.selected_symptoms else "증상 분석 중"

    ctx.structured_symptom = StructuredSymptom(
        symptom_type=primary_type,
        occurrence_time="최근",
        target_water_type="전체",
        occurrence_condition=ctx.raw_symptom,
        accompanying_symptoms=ctx.selected_symptoms,
        actions_taken=[ans.get("answer_text", "") for ans in ctx.previous_answers if isinstance(ans, dict)]
    )

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    ctx.processing_traces.append(
        ProcessingTrace(stage=AiStage.STRUCTURING, status="SUCCEEDED", latency_ms=round(elapsed_ms, 2))
    )
