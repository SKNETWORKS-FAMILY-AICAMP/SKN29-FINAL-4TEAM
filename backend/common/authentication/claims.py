"""WaterCare Public JWT Claim 이름과 검증 helper."""

from __future__ import annotations

from typing import Any


SUBJECT_CLAIM = "sub"
ROLE_CLAIM = "role_code"
TOKEN_TYPE_CLAIM = "token_type"
AUTH_VERSION_CLAIM = "auth_version"


def required_claim(token: Any, claim_name: str) -> str:
    value = token.get(claim_name)
    normalized = str(value).strip() if value is not None else ""
    if not normalized:
        raise ValueError(f"{claim_name} claim이 없습니다.")
    return normalized


def required_positive_int_claim(token: Any, claim_name: str) -> int:
    """Return a positive integer claim while explicitly rejecting booleans."""

    value = token.get(claim_name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{claim_name} claim must be a positive integer.")
    return value
