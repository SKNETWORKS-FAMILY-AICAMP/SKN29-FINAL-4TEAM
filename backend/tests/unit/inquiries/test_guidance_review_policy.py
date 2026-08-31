"""Unit tests for Backend-owned Guidance visibility routing."""

from dataclasses import dataclass

import pytest

from apps.inquiries.services.guidance_review_policy import (
    CautionAutoPublicationPolicy,
    GuidanceReviewPolicy,
)


@dataclass(frozen=True)
class ResultStub:
    risk_level: str
    requires_consultation: bool = False
    is_fallback: bool = False
    is_no_evidence: bool = False


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (ResultStub("general"), GuidanceReviewPolicy.CONFIRMED),
        (ResultStub("danger"), GuidanceReviewPolicy.CONFIRMED),
        (ResultStub("caution"), GuidanceReviewPolicy.PENDING),
        (
            ResultStub("caution", is_fallback=True),
            GuidanceReviewPolicy.REJECTED,
        ),
        (
            ResultStub("caution", is_fallback=True, is_no_evidence=True),
            GuidanceReviewPolicy.REJECTED,
        ),
        (ResultStub("unknown"), GuidanceReviewPolicy.REJECTED),
    ],
)
def test_initial_status_is_fail_closed(result, expected):
    assert GuidanceReviewPolicy.initial_status(result) == expected


@pytest.mark.parametrize("requires_consultation", [False, True])
def test_caution_review_is_independent_from_consultation(
    requires_consultation,
):
    result = ResultStub(
        "caution",
        requires_consultation=requires_consultation,
    )

    assert GuidanceReviewPolicy.initial_status(result) == "PENDING"


@pytest.mark.parametrize(
    ("risk_level", "review_status", "expected"),
    [
        ("caution", "PENDING", False),
        ("caution", "CONFIRMED", False),
        ("caution", "APPROVED", True),
        ("general", "CONFIRMED", True),
        ("danger", "CONFIRMED", True),
        ("unknown", "APPROVED", False),
    ],
)
def test_customer_visibility_is_risk_aware(
    risk_level,
    review_status,
    expected,
):
    assert (
        GuidanceReviewPolicy.is_customer_visible(
            risk_level=risk_level,
            review_status=review_status,
        )
        is expected
    )


def test_caution_auto_publication_has_no_runtime_opt_in():
    assert CautionAutoPublicationPolicy.RELEASE_MODE == "HUMAN_REVIEW_ONLY"
    assert CautionAutoPublicationPolicy.initial_review_status() == "PENDING"
    assert CautionAutoPublicationPolicy.is_customer_visible("CONFIRMED") is False
