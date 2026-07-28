"""사용 안내 상태 및 메시지 생성 Stage 모듈."""

import time
from ...safety import UsageGuidanceClassifier
from ...schemas import ProcessingTrace
from ..pipeline_context import PipelineContext


def execute_generation_stage(ctx: PipelineContext) -> None:
    """위험 평가 및 RAG 근거 존재 여부에 따라 최종 사용 안내 가이드 생성"""
    start_time = time.perf_counter()

    classifier = UsageGuidanceClassifier()
    has_evidence = bool(ctx.evidence_references)

    ctx.usage_guidance = classifier.determine_guidance(
        safety_assessment=ctx.safety_assessment,
        raw_text=ctx.raw_symptom,
        has_evidence=has_evidence
    )

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    ctx.processing_traces.append(
        ProcessingTrace(stage="generation_stage", status="success", latency_ms=round(elapsed_ms, 2))
    )
