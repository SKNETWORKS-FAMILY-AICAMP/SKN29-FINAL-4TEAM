"""Consultation handoff input contracts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HandoffEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chunk_id: str = Field(..., min_length=1, max_length=200)
    document_title: str = Field(..., min_length=1, max_length=500)
    page: int | None = Field(None, ge=1)
    summary: str = Field(..., min_length=1, max_length=2000)


class HandoffQuestionnaireAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    field_name: str = Field(..., min_length=1, max_length=100)
    answer: str = Field(..., min_length=1, max_length=500)


class ConsultationHandoffInput(BaseModel):
    """Only structured runtime facts are accepted; prompts/internal errors are excluded."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    inquiry_id: UUID
    correlation_id: UUID
    ai_request_id: str = Field(..., min_length=1, max_length=100)
    state_version: int | None = Field(default=None, ge=1)
    routing_reason: str | None = Field(default=None, min_length=1, max_length=100)
    model_code: str = Field(..., min_length=1, max_length=100)
    product_family: str = Field(..., min_length=1, max_length=100)
    symptom_summary: str = Field(..., min_length=1, max_length=2000)
    questionnaire_answers: list[HandoffQuestionnaireAnswer] = Field(default_factory=list)
    proposed_self_help_actions: list[str] = Field(default_factory=list)
    evidence: list[HandoffEvidence] = Field(default_factory=list)
    safety_level: str = Field(..., min_length=1, max_length=50)
    safety_requires_consultation: bool
    safety_notes: list[str] = Field(default_factory=list)
    escalation_reason: str = Field(..., min_length=1, max_length=500)
    consultant_priority_checks: list[str] = Field(default_factory=list)

    @classmethod
    def from_pipeline_context(
        cls,
        *,
        ctx: Any,
        product_family: str,
        escalation_reason: str,
        accepted_evidence_chunk_ids: list[str] | None = None,
        routing_reason: str | None = None,
    ) -> "ConsultationHandoffInput":
        symptom = getattr(ctx, "structured_symptom", None)
        symptom_parts: list[str] = []
        if symptom is not None:
            for name in (
                "symptom_type",
                "occurrence_time",
                "target_water_type",
                "occurrence_condition",
                "error_code",
            ):
                value = getattr(symptom, name, None)
                if value:
                    symptom_parts.append(f"{name}={value}")
            for value in getattr(symptom, "accompanying_symptoms", []) or []:
                symptom_parts.append(f"accompanying_symptom={value}")
        if not symptom_parts:
            symptom_parts.append("structured symptom unavailable")

        answers: list[HandoffQuestionnaireAnswer] = []
        for item in getattr(ctx, "previous_answers", []) or []:
            if not isinstance(item, dict):
                continue
            field_name = str(item.get("field_name") or item.get("target_field") or item.get("question_id") or "answer")
            value = (
                item.get("answer_text")
                or item.get("answer")
                or item.get("value")
                or item.get("selected_option")
            )
            if value is None:
                continue
            answers.append(HandoffQuestionnaireAnswer(field_name=field_name, answer=str(value)))

        accepted_ids = (
            set(accepted_evidence_chunk_ids)
            if accepted_evidence_chunk_ids is not None
            else None
        )
        evidence = [
            HandoffEvidence(
                chunk_id=item.chunk_id,
                document_title=item.document_title,
                page=item.page,
                summary=item.summary,
            )
            for item in (getattr(ctx, "evidence_references", []) or [])
            if accepted_ids is None or item.chunk_id in accepted_ids
        ]

        safety = getattr(ctx, "safety_assessment", None)
        safety_level = getattr(getattr(safety, "risk_level", None), "value", None) or "unknown"
        safety_requires_consultation = bool(
            getattr(safety, "requires_consultation", False)
        )
        safety_notes = list(getattr(safety, "detected_risks", []) or [])
        safety_reason = getattr(safety, "safety_reason", None)
        if safety_reason:
            safety_notes.append(safety_reason)

        # 기존 Backend 계약 필드명은 유지하되, 값은 고객이 실제 수행한 조치만 담는다.
        # usage_guidance.next_actions는 앞으로 할 행동이므로 수행 이력으로 사용하지 않는다.
        actions = list(getattr(symptom, "actions_taken", []) or [])
        priority_checks = [item.reason for item in (getattr(ctx, "missing_fields", []) or [])]

        trace = ctx.trace_context
        return cls(
            inquiry_id=trace.inquiry_id,
            correlation_id=trace.correlation_id,
            ai_request_id=trace.ai_request_id,
            state_version=getattr(trace, "state_version", None),
            routing_reason=routing_reason,
            model_code=ctx.model_code,
            product_family=product_family,
            symptom_summary=" | ".join(symptom_parts),
            questionnaire_answers=answers,
            proposed_self_help_actions=actions,
            evidence=evidence,
            safety_level=str(safety_level),
            safety_requires_consultation=safety_requires_consultation,
            safety_notes=safety_notes,
            escalation_reason=escalation_reason,
            consultant_priority_checks=priority_checks,
        )
