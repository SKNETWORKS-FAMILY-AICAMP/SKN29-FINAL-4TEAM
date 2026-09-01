"""증상 필드 구조화 Stage 모듈."""

import time
from ...schemas import AiStage, ProcessingTrace
from ...structuring import ProductSymptomDomainGuard, SymptomStructurer
from ...structuring.llm_contracts import SymptomStructuringLLMClient
from ..pipeline_context import PipelineContext


def execute_structuring_stage(
    ctx: PipelineContext,
    llm_client: SymptomStructuringLLMClient | None = None,
    *,
    timeout_seconds: float = 4.0,
) -> None:
    """고객 입력 증상을 표준 항목으로 구조화"""
    start_time = time.perf_counter()

    structurer = SymptomStructurer(llm_client=llm_client)
    ctx.structured_symptom = structurer.structure(
        raw_text=ctx.raw_symptom,
        selected_symptoms=ctx.selected_symptoms,
        previous_answers=ctx.previous_answers,
        trace_context=ctx.trace_context,
        model_code=ctx.model_code,
        timeout_seconds=timeout_seconds,
    )
    ctx.safety_signals = structurer.last_safety_signals
    domain_decision = ProductSymptomDomainGuard().evaluate(
        raw_symptom=ctx.raw_symptom,
        selected_symptoms=ctx.selected_symptoms,
        structured_symptom=ctx.structured_symptom,
    )
    ctx.domain_relevance = domain_decision.relevance
    ctx.domain_relevance_reason = domain_decision.reason
    if ctx.domain_relevance == "OFF_DOMAIN":
        ctx.evidence_clarification_allowed = False

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    ctx.processing_traces.append(
        ProcessingTrace(
            stage=AiStage.STRUCTURING,
            status="SUCCEEDED",
            latency_ms=round(elapsed_ms, 2),
        )
    )
