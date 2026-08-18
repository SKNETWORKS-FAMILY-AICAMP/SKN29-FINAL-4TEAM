"""증상 구조화·안전 우선·추가 질문 역할."""

from __future__ import annotations

from ...common.timeout import CancellationToken, get_stage_timeout_policy
from ...schemas import AiStage
from ..pipeline_context import PipelineContext
from ..stages import (
    execute_missing_fields_stage,
    execute_safety_check_stage,
    execute_structuring_stage,
)
from .contracts import SymptomAgentOutput


class SymptomAnalysisAgent:
    """구조화와 질문 후보만 소유하며 최종 안내를 결정하지 않는다."""

    allowed_tools = (
        "SymptomStructurer",
        "SafetyRule",
        "MissingFieldChecker",
        "DuplicateQuestionGuard",
    )

    def __init__(self, cancellation_token: CancellationToken) -> None:
        self.cancellation_token = cancellation_token
        self.timeout_policy = get_stage_timeout_policy()

    def run(self, ctx: PipelineContext) -> SymptomAgentOutput:
        self._run_stage(AiStage.STRUCTURING, execute_structuring_stage, ctx)
        self._run_stage(AiStage.SAFETY_CHECK, execute_safety_check_stage, ctx)
        self._run_stage(AiStage.CHECKING_MISSING_FIELDS, execute_missing_fields_stage, ctx)
        return self._output(ctx)

    def review_evidence_feedback(self, ctx: PipelineContext) -> SymptomAgentOutput:
        """검색 근거 부족 시 이미 생성된 질문을 고객 입력 대기로 확정한다."""

        if not ctx.followup_questions:
            raise RuntimeError("Evidence Feedback에 사용할 추가 질문이 없습니다.")
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
            clarification_needed=bool(ctx.followup_questions),
        )
