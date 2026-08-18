"""고객 안내 후보 생성과 결정론적 최종 검증 역할."""

from __future__ import annotations

import time

from ...common.timeout import CancellationToken, get_stage_timeout_policy
from ...integrations.llm import GuidanceLLMClient
from ...schemas import AiStage, ProcessingTrace, UsageGuidance, UsageGuidanceStatus
from ..pipeline_context import PipelineContext
from ..stages import execute_generation_stage, execute_validation_stage
from .contracts import CareDecisionAgentOutput


class CareDecisionAgent:
    """검증된 Safety·Evidence 범위에서만 고객 안내 후보를 만든다."""

    allowed_tools = (
        "UsageGuidanceClassifier",
        "GuidanceLLMClient",
        "OutputValidator",
    )

    def __init__(
        self,
        cancellation_token: CancellationToken,
        llm_client: GuidanceLLMClient | None = None,
    ) -> None:
        self.cancellation_token = cancellation_token
        self.llm_client = llm_client
        self.timeout_policy = get_stage_timeout_policy()

    def run(
        self,
        ctx: PipelineContext,
        *,
        awaiting_customer_input: bool = False,
    ) -> CareDecisionAgentOutput:
        if awaiting_customer_input:
            self._set_questionnaire_pending_guidance(ctx)
        else:
            timeout_seconds = self.timeout_policy.for_stage(AiStage.GENERATING.value)
            with self.cancellation_token.deadline_scope(
                timeout_seconds,
                AiStage.GENERATING.value,
            ):
                execute_generation_stage(
                    ctx,
                    self.llm_client,
                    self.cancellation_token,
                    attempt_timeout_seconds=min(7.0, timeout_seconds / 2.0),
                )

        with self.cancellation_token.deadline_scope(
            self.timeout_policy.for_stage(AiStage.VALIDATING.value),
            AiStage.VALIDATING.value,
        ):
            execute_validation_stage(ctx)

        if ctx.usage_guidance is None or ctx.safety_assessment is None:
            raise RuntimeError("Care Decision Agent 출력이 완성되지 않았습니다.")
        return CareDecisionAgentOutput(
            usage_guidance=ctx.usage_guidance,
            requires_consultation=ctx.safety_assessment.requires_consultation,
            awaiting_customer_input=awaiting_customer_input,
        )

    @staticmethod
    def _set_questionnaire_pending_guidance(ctx: PipelineContext) -> None:
        """근거 부재 확정 전에는 LLM 자가조치 없이 질문 응답만 요청한다."""

        started_at = time.perf_counter()
        ctx.awaiting_customer_input = True
        ctx.usage_guidance = UsageGuidance(
            guidance_status=UsageGuidanceStatus.PENDING_CONSULTATION,
            message="안전한 안내를 위해 추가 정보가 필요합니다. 표시된 질문에 답변해 주세요.",
            restricted_functions=["근거 확인 전 자가조치 안내"],
            next_actions=["추가 질문에 답변해 주세요."],
        )
        ctx.processing_traces.append(
            ProcessingTrace(
                stage=AiStage.GENERATING,
                status="SUCCEEDED",
                latency_ms=round((time.perf_counter() - started_at) * 1000.0, 2),
                retry_count=ctx.retry_count,
            )
        )
