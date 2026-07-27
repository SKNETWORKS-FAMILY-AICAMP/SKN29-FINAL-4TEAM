"""T-005 도메인형 ID 생성·합성 Seed 형식 검증."""

import re

import pytest
from django.core.exceptions import ValidationError

from common.identifiers import (
    generate_domain_id,
    validate_domain_id,
)


def test_runtime_identifier_has_domain_prefix_and_uuid_entropy():
    first = generate_domain_id("USR")
    second = generate_domain_id("USR")

    assert re.fullmatch(r"USR-[0-9A-F]{32}", first)
    assert first != second
    validate_domain_id(first)


@pytest.mark.parametrize(
    "identifier",
    [
        "DEMO-USR-001",
        "SYN-INQ-002",
        "DEMO-TECH-1000",
    ],
)
def test_validated_synthetic_identifiers_are_allowed(identifier):
    validate_domain_id(identifier)


@pytest.mark.parametrize(
    "identifier",
    [
        "usr-0123456789abcdef0123456789abcdef",
        "DEMO-USR-1",
        "REAL-USR-001",
        "USR-short",
        "X" * 49,
    ],
)
def test_invalid_or_unapproved_identifier_shapes_are_rejected(
    identifier,
):
    with pytest.raises(ValidationError):
        validate_domain_id(identifier)


def test_invalid_entity_prefix_is_rejected():
    with pytest.raises(ValueError):
        generate_domain_id("x")
