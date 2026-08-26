"""Unit tests for Backend-owned Guidance visibility routing."""

from dataclasses import dataclass

import pytest

from apps.inquiries.services.guidance_review_policy import (
    GuidanceReviewPolicy,
)


@dataclass(frozen=True)
class ResultStub:
    risk_level: str
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
