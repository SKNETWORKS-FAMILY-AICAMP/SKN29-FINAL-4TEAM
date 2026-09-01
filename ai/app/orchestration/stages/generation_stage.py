"""사용 안내 상태 및 메시지 생성 Stage 모듈."""

import time
from ...common.timeout import CancellationToken
from ...safety import UsageGuidanceClassifier
from ...generation.customer_guidance.guidance_generator import (
    CustomerGuidanceGenerator,
    GuidanceGenerationExecutionError,
)
from ...integrations.llm import GuidanceLLMClient
from ...schemas import AiStage, ProcessingTrace
from ..pipeline_context import PipelineContext


def execute_generation_stage(
    ctx: PipelineContext,
    llm_client: GuidanceLLMClient | None = None,
    cancellation_token: CancellationToken | None = None,
    attempt_timeout_seconds: float = 7.0,
) -> None:
    """위험 평가 및 RAG 근거 존재 여부에 따라 최종 사용 안내 가이드 생성"""
    start_time = time.perf_counter()

    classifier = UsageGuidanceClassifier()
    has_evidence = bool(ctx.evidence_references)

    ctx.safety_assessment, deterministic_guidance = (
        classifier.determine_assessment_and_guidance(
            safety_assessment=ctx.safety_assessment,
            raw_text=ctx.raw_symptom,
            has_evidence=has_evidence,
        )
    )

    if ctx.domain_relevance == "OFF_DOMAIN" and not has_evidence:
        deterministic_guidance = deterministic_guidance.model_copy(
            update={
                "message": (
                    "입력하신 내용은 정수기 사용 중 발생한 증상으로 확인되지 "
                    "않았어요. 정수기 사용 중 발생한 불편한 점을 입력해 주세요."
                ),
                "restricted_functions": ["정수기 자가조치 안내"],
                "next_actions": ["정수기 사용 중 발생한 증상을 다시 입력해 주세요."],
            }
        )

    if ctx.safety_assessment.risk_level.value == "danger" or not has_evidence:
        ctx.usage_guidance = deterministic_guidance
    else:
        try:
            ctx.usage_guidance = CustomerGuidanceGenerator(llm_client).generate(
                ctx=ctx,
                deterministic_guidance=deterministic_guidance,
                cancellation_token=cancellation_token,
                attempt_timeout_seconds=attempt_timeout_seconds,
            )
        except GuidanceGenerationExecutionError as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            ctx.processing_traces.append(
                ProcessingTrace(
                    stage=AiStage.GENERATING,
                    status="FAILED",
                    latency_ms=round(elapsed_ms, 2),
                    retry_count=exc.retry_count,
                    error_code="AI-TIMEOUT-01" if exc.timed_out else "AI-FAILED-01",
                )
            )
            raise

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    ctx.processing_traces.append(
        ProcessingTrace(
            stage=AiStage.GENERATING,
            status="SUCCEEDED",
            latency_ms=round(elapsed_ms, 2),
            retry_count=ctx.retry_count,
        )
    )
