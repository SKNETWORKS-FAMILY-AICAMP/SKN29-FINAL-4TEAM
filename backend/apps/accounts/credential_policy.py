"""Credential rules that are stricter than Django's generic password policy."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError


CONSULTANT_PASSWORD_PATTERN = re.compile(
    r"^(?=.*[A-Za-z])(?=.*[0-9])[A-Za-z0-9]{12,64}$"
)
SYNTHETIC_USERNAME_PREFIXES = ("DEMO-", "SYN-")


def validate_consultant_password(value: str) -> None:
    """Require 12-64 ASCII alphanumerics with both letters and digits."""

    if CONSULTANT_PASSWORD_PATTERN.fullmatch(str(value or "")) is None:
        raise ValidationError(
            "상담사 비밀번호는 12~64자의 영문·숫자 조합이어야 하며 "
            "영문과 숫자를 각각 1자 이상 포함해야 합니다."
        )


def normalize_synthetic_username(value: str) -> str:
    username = str(value or "").strip().upper()
    if not username.startswith(SYNTHETIC_USERNAME_PREFIXES):
        raise ValidationError(
            "합성 계정 ID는 DEMO- 또는 SYN-으로 시작해야 합니다."
        )
    return username
