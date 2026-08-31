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


class CautionAutoPublicationPolicy:
    """Current-release gate for customer-visible caution guidance.

    This is intentionally not configurable through settings or environment
    variables. Enabling selective caution auto-publication requires a
    separate policy implementation, validation evidence, and release
    approval instead of a runtime toggle.
    """

    RELEASE_MODE = "HUMAN_REVIEW_ONLY"

    @classmethod
    def initial_review_status(cls) -> str:
        """Keep every caution draft in PRE_SEND review for this release."""

        return GuidanceReviewPolicy.PENDING

    @classmethod
    def is_customer_visible(cls, review_status: str) -> bool:
        """Expose caution guidance only after an explicit human approval."""

        return review_status == GuidanceReviewPolicy.APPROVED


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
        """Return the fail-closed initial review status for one AI result."""

        if result.is_fallback or result.is_no_evidence:
            return cls.REJECTED
        if result.risk_level == "caution":
            return CautionAutoPublicationPolicy.initial_review_status()
        if result.risk_level in {"general", "danger"}:
            # CONFIRMED means the existing Backend safety/evidence gate, not
            # a human approval. APPROVED remains reserved for a future
            # consultant decision API.
            return cls.CONFIRMED
        return cls.REJECTED

    @classmethod
    def is_customer_visible(
        cls,
        *,
        risk_level: str,
        review_status: str,
    ) -> bool:
        """Apply the release review gate independently of consultation.

        ``requires_consultation`` deliberately is not an input. A caution
        case may or may not need a consultation, but both cases still need a
        human-approved customer message in the current release.
        """

        if risk_level == "caution":
            return CautionAutoPublicationPolicy.is_customer_visible(
                review_status
            )
        if risk_level in {"general", "danger"}:
            return review_status in {cls.APPROVED, cls.CONFIRMED}
        return False
