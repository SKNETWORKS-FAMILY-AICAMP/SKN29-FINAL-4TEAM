"""SingleRAG와 Multi-Agent가 공유하는 고객 추가 입력 대기 정책."""

from __future__ import annotations

from ..retrieval import EvidenceApplicabilityGate
from ..schemas import RiskLevel
from .pipeline_context import PipelineContext


def should_wait_for_customer_input(ctx: PipelineContext) -> bool:
    """Safety를 우선하고 미해결 required(high) 질문만 Runtime을 중단한다."""

    if (
        ctx.safety_assessment is not None
        and ctx.safety_assessment.risk_level == RiskLevel.DANGER
    ):
        return False

    symptom_type = (
        ctx.structured_symptom.symptom_type
        if ctx.structured_symptom is not None
        else None
    )
    if EvidenceApplicabilityGate().requires_more_information(
        symptom_type=symptom_type,
        missing_field_names=(item.field_name for item in ctx.missing_fields),
        previous_answers=ctx.previous_answers,
    ):
        return True

    blocking_fields = {
        item.field_name
        for item in ctx.missing_fields
        if item.importance == "high"
    }
    return any(
        question.target_field in blocking_fields
        for question in ctx.followup_questions
    )


__all__ = ["should_wait_for_customer_input"]
