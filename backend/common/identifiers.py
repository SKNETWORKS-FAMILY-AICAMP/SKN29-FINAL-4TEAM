"""T-005 OWNER 기준 도메인형 문자열 식별자 생성·검증."""

from __future__ import annotations

import re
import uuid

from django.core.exceptions import ValidationError


MAX_IDENTIFIER_LENGTH = 48
ENTITY_PATTERN = re.compile(r"^[A-Z]{3,8}$")
RUNTIME_IDENTIFIER_PATTERN = re.compile(
    r"^[A-Z]{3,8}-[0-9A-F]{32}$"
)
SYNTHETIC_IDENTIFIER_PATTERN = re.compile(
    r"^(?:DEMO|SYN)-[A-Z]{3,8}-[0-9]{3,}$"
)


def generate_domain_id(entity: str) -> str:
    """Backend가 발급하는 `<ENTITY>-<UUID4_HEX_32>` ID를 만든다."""

    normalized = str(entity).strip().upper()
    if not ENTITY_PATTERN.fullmatch(normalized):
        raise ValueError("entity는 3~8자의 영문 대문자여야 합니다.")
    return f"{normalized}-{uuid.uuid4().hex.upper()}"


def generate_user_id() -> str:
    return generate_domain_id("USR")


def generate_customer_profile_id() -> str:
    return generate_domain_id("CUS")


def validate_domain_id(value: str) -> None:
    """일반 실행 ID 또는 검증된 합성 Seed ID만 허용한다."""

    normalized = str(value).strip()
    if (
        len(normalized) > MAX_IDENTIFIER_LENGTH
        or (
            RUNTIME_IDENTIFIER_PATTERN.fullmatch(normalized) is None
            and SYNTHETIC_IDENTIFIER_PATTERN.fullmatch(normalized) is None
        )
    ):
        raise ValidationError(
            "도메인형 식별자 형식이 올바르지 않습니다."
        )
