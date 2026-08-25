"""Unit tests for Backend-owned display masking."""

import pytest

from common.privacy import mask_person_name, mask_phone


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", ""),
        ("최", "*"),
        ("최용", "최*"),
        ("최지용", "최*용"),
        ("김지용수", "김**수"),
        ("김가람 (합성)", "김*람 (합성)"),
        (" 합성 고객 001 ", "합*******1"),
    ],
)
def test_mask_person_name_keeps_only_public_characters(value, expected):
    assert mask_person_name(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", ""),
        ("010-1234-5678", "010-****-5678"),
        ("031-123-4567", "031-***-4567"),
        ("1234", "****"),
    ],
)
def test_mask_phone_exposes_only_allowed_digits(value, expected):
    assert mask_phone(value) == expected
