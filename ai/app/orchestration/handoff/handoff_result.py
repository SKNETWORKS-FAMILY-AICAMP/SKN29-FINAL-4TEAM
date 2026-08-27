"""Consultation handoff output contracts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .handoff_input import HandoffEvidence, HandoffQuestionnaireAnswer


class HandoffContextSynthesis(BaseModel):
    """Internal counselor brief attachment; not part of the Backend contract yet."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: str = Field(..., min_length=1, max_length=50)
    routing_reason: str = Field(..., min_length=1, max_length=100)
    brief: dict[str, Any]
    fallback_reason: str | None = Field(None, min_length=1, max_length=100)
    should_use_deterministic_handoff: bool
    provider_called: bool
    model_name: str | None = Field(None, min_length=1, max_length=200)
    prompt_version: str = Field(..., min_length=1, max_length=100)
    tokens_used: int | None = Field(None, ge=0)
    latency_ms: float | None = Field(None, ge=0)

    @classmethod
    def from_agent_output(cls, output: Any) -> "HandoffContextSynthesis":
        status = getattr(output.status, "value", output.status)
        routing_reason = getattr(output.routing_reason, "value", output.routing_reason)
        fallback_raw = getattr(output, "fallback_reason", None)
        fallback_reason = (
            getattr(fallback_raw, "value", fallback_raw)
            if fallback_raw is not None
            else None
        )
        return cls(
            status=str(status),
            routing_reason=str(routing_reason),
            brief=output.brief.model_dump(mode="json"),
            fallback_reason=(str(fallback_reason) if fallback_reason is not None else None),
            should_use_deterministic_handoff=bool(output.should_use_deterministic_handoff),
            provider_called=bool(output.provider_called),
            model_name=output.model_name,
            prompt_version=output.prompt_version,
            tokens_used=output.tokens_used,
            latency_ms=output.latency_ms,
        )


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
    context_synthesis: HandoffContextSynthesis | None = None
