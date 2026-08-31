"""증상 구조화·안전 우선·검색 문맥 생성 역할."""

from __future__ import annotations

from ...common.timeout import CancellationToken, get_stage_timeout_policy
from ...structuring.llm_contracts import (
    FollowUpWordingLLMClient,
    SymptomStructuringLLMClient,
)
from ...schemas import AiStage, RiskLevel
from ..pipeline_context import PipelineContext
from ..stages import (
    execute_missing_fields_stage,
    execute_safety_check_stage,
    execute_structuring_stage,
)
from .contracts import SymptomAgentOutput
from ..clarification_policy import should_wait_for_customer_input


class SymptomAnalysisAgent:
    """구조화와 Safety를 소유하며 질문·최종 안내를 결정하지 않는다."""

    allowed_tools = (
        "SymptomStructurer",
        "SymptomStructuringLLM",
        "SafetyRule",
        "MissingFieldChecker",
        "DuplicateQuestionGuard",
    )

    def __init__(
        self,
        cancellation_token: CancellationToken,
        *,
        symptom_llm_client: SymptomStructuringLLMClient | None = None,
        followup_llm_client: FollowUpWordingLLMClient | None = None,
    ) -> None:
        self.cancellation_token = cancellation_token
        self.timeout_policy = get_stage_timeout_policy()
        self.symptom_llm_client = symptom_llm_client
        self.followup_llm_client = followup_llm_client

    def run(self, ctx: PipelineContext) -> SymptomAgentOutput:
        self._run_stage(
            AiStage.STRUCTURING,
            lambda current: execute_structuring_stage(
                current,
                self.symptom_llm_client,
                timeout_seconds=self.timeout_policy.for_provider(
                    "SYMPTOM_STRUCTURING"
                ),
            ),
            ctx,
        )
        self._run_stage(AiStage.SAFETY_CHECK, execute_safety_check_stage, ctx)
        if ctx.safety_assessment is None:
            raise RuntimeError("질문 생성 전에 안전 평가가 필요합니다.")
        if ctx.safety_assessment.risk_level == RiskLevel.DANGER:
            ctx.missing_fields = []
            ctx.followup_questions = []
        else:
            # MissingField는 retrieval context로만 기록하고 이 단계에서는
            # 고객 입력을 차단하는 질문을 만들지 않는다.
            self._run_stage(
                AiStage.CHECKING_MISSING_FIELDS,
                lambda current: execute_missing_fields_stage(
                    current,
                    None,
                    timeout_seconds=self.timeout_policy.for_provider(
                        "FOLLOWUP_WORDING"
                    ),
                    target_field_names=(),
                ),
                ctx,
            )
        return self._output(ctx)

    def _run_stage(self, stage: AiStage, callback, ctx: PipelineContext) -> None:
        with self.cancellation_token.deadline_scope(
            self.timeout_policy.for_stage(stage.value),
            stage.value,
        ):
            callback(ctx)

    @staticmethod
    def _output(ctx: PipelineContext) -> SymptomAgentOutput:
        if ctx.structured_symptom is None or ctx.safety_assessment is None:
            raise RuntimeError("Symptom Agent 출력이 완성되지 않았습니다.")
        return SymptomAgentOutput(
            structured_symptom=ctx.structured_symptom,
            safety_assessment=ctx.safety_assessment,
            missing_fields=list(ctx.missing_fields),
            followup_questions=list(ctx.followup_questions),
            clarification_needed=should_wait_for_customer_input(ctx),
        )
