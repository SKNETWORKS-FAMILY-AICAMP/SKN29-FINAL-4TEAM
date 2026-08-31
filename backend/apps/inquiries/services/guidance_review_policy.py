"""Backend-owned initial review policy for validated AI Guidance."""

from __future__ import annotations

from typing import Protocol


class ReviewableAIResult(Protocol):
    """Minimum validated AI result surface used by the review policy."""

    @property
    def is_fallback(self) -> bool: ...

    @property
    def is_no_evidence(self) -> bool: ...

    @property
    def risk_level(self) -> str: ...

    @property
    def requires_consultation(self) -> bool: ...


class GuidanceReviewPolicy:
    """Classify a validated AI draft without changing Inquiry state.

    The policy deliberately owns only customer visibility. Inquiry workflow
    transitions remain in the PM-owned state-machine contract.
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"

    @classmethod
    def initial_status(cls, result: ReviewableAIResult) -> str:
        """Return the customer-visibility status for one validated AI result.

        Runtime guidance is decided by deterministic Backend safety/evidence
        gates. HumanReview remains available for separate quality-review
        workflows, but is not a PRE_SEND dependency of the customer flow.
        """

        if (
            result.is_fallback
            or result.is_no_evidence
            or result.requires_consultation
        ):
            return cls.REJECTED
        if result.risk_level in {"general", "caution"}:
            # CONFIRMED means the existing Backend safety/evidence gate, not
            # a human approval. APPROVED remains reserved for a future
            # consultant decision API.
            return cls.CONFIRMED
        return cls.REJECTED
