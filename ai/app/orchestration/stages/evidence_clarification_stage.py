"""Retrieval 후 Evidence sufficiency에 따라 필요한 질문만 생성한다."""

from __future__ import annotations

from ...structuring.llm_contracts import FollowUpWordingLLMClient
from ..evidence_clarification_policy import (
    EvidenceClarificationDecision,
    EvidenceClarificationPolicy,
)
from ..pipeline_context import PipelineContext
from .missing_fields_stage import execute_missing_fields_stage


def execute_evidence_clarification_stage(
    ctx: PipelineContext,
    llm_client: FollowUpWordingLLMClient | None = None,
    *,
    timeout_seconds: float = 4.0,
) -> EvidenceClarificationDecision:
    """Evidence Agent의 결정을 기존 FollowUpQuestionGenerator에 연결한다."""

    decision = EvidenceClarificationPolicy().decide(ctx)
    ctx.evidence_sufficient = decision.evidence_sufficient
    ctx.evidence_clarification_reason = decision.reason
    execute_missing_fields_stage(
        ctx,
        llm_client,
        timeout_seconds=timeout_seconds,
        target_field_names=decision.target_fields,
        question_overrides=decision.question_overrides,
    )
    return decision


__all__ = ["execute_evidence_clarification_stage"]
