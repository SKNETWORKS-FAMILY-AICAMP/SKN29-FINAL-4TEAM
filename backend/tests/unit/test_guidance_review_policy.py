from types import SimpleNamespace

from apps.inquiries.services.guidance_review_policy import GuidanceReviewPolicy


def _result(
    *,
    risk_level: str,
    requires_consultation: bool,
    is_fallback: bool = False,
    is_no_evidence: bool = False,
):
    return SimpleNamespace(
        risk_level=risk_level,
        requires_consultation=requires_consultation,
        is_fallback=is_fallback,
        is_no_evidence=is_no_evidence,
    )


def test_caution_without_consultation_is_customer_visible():
    assert (
        GuidanceReviewPolicy.initial_status(
            _result(
                risk_level="caution",
                requires_consultation=False,
            )
        )
        == GuidanceReviewPolicy.CONFIRMED
    )


def test_caution_requiring_consultation_is_not_customer_visible():
    assert (
        GuidanceReviewPolicy.initial_status(
            _result(
                risk_level="caution",
                requires_consultation=True,
            )
        )
        == GuidanceReviewPolicy.REJECTED
    )


def test_fallback_and_no_evidence_remain_fail_closed():
    assert (
        GuidanceReviewPolicy.initial_status(
            _result(
                risk_level="caution",
                requires_consultation=False,
                is_fallback=True,
            )
        )
        == GuidanceReviewPolicy.REJECTED
    )
    assert (
        GuidanceReviewPolicy.initial_status(
            _result(
                risk_level="caution",
                requires_consultation=False,
                is_no_evidence=True,
            )
        )
        == GuidanceReviewPolicy.REJECTED
    )


def test_general_is_confirmed_and_danger_is_rejected():
    assert (
        GuidanceReviewPolicy.initial_status(
            _result(
                risk_level="general",
                requires_consultation=False,
            )
        )
        == GuidanceReviewPolicy.CONFIRMED
    )
    assert (
        GuidanceReviewPolicy.initial_status(
            _result(
                risk_level="danger",
                requires_consultation=True,
            )
        )
        == GuidanceReviewPolicy.REJECTED
    )
