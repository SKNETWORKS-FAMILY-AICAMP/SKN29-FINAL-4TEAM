"""Consultation handoff output contracts."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .handoff_input import HandoffEvidence, HandoffQuestionnaireAnswer


class ConsultationHandoffResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    inquiry_id: UUID
    correlation_id: UUID
    ai_request_id: str = Field(..., min_length=1, max_length=100)
    model_code: str = Field(..., min_length=1, max_length=100)
    product_family: str = Field(..., min_length=1, max_length=100)
    customer_symptom_summary: str = Field(..., min_length=1, max_length=2000)
    questionnaire_answers: list[HandoffQuestionnaireAnswer] = Field(default_factory=list)
    self_help_actions: list[str] = Field(default_factory=list)
    evidence: list[HandoffEvidence] = Field(default_factory=list)
    safety_level: str = Field(..., min_length=1, max_length=50)
    safety_requires_consultation: bool
    safety_notes: list[str] = Field(default_factory=list)
    escalation_reason: str = Field(..., min_length=1, max_length=500)
    consultant_priority_checks: list[str] = Field(default_factory=list)
    source_chunk_ids: list[str] = Field(default_factory=list)
