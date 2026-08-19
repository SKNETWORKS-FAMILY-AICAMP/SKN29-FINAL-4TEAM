"""Human-review interrupt contracts and node."""

from __future__ import annotations

from uuid import UUID

from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, Field

from ...schemas import UsageGuidance


class HumanReviewRequest(BaseModel):
    """PII-minimized payload persisted before a human review interrupt."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    inquiry_id: UUID
    correlation_id: UUID
    ai_request_id: str = Field(..., min_length=1, max_length=100)
    state_version: int = Field(..., ge=1)
    model_code: str = Field(..., min_length=1, max_length=100)
    product_family: str = Field(..., min_length=1, max_length=100)
    review_reason: str = Field(..., min_length=1, max_length=500)
    verification_issue_codes: list[str] = Field(default_factory=list)
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    proposed_guidance: UsageGuidance

    def interrupt_payload(self) -> dict:
        """Return only JSON-serializable counselor-facing review data."""

        return {
            "inquiry_id": str(self.inquiry_id),
            "correlation_id": str(self.correlation_id),
            "ai_request_id": self.ai_request_id,
            "state_version": self.state_version,
            "model_code": self.model_code,
            "product_family": self.product_family,
            "review_reason": self.review_reason,
            "verification_issue_codes": list(self.verification_issue_codes),
            "evidence_chunk_ids": list(self.evidence_chunk_ids),
            "proposed_guidance": self.proposed_guidance.model_dump(mode="json"),
        }


def human_review_interrupt_node(state: dict) -> dict:
    """Pause execution and validate the eventual resume payload in resume.py."""

    request = HumanReviewRequest.model_validate(state["request"])
    resume_payload = interrupt(request.interrupt_payload())
    return {**state, "resume_payload": resume_payload}
