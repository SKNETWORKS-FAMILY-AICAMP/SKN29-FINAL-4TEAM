"""Validated request-header helpers shared by workflow write APIs."""

from rest_framework.exceptions import ValidationError


def require_idempotency_key(request) -> str:
    """Return one normalized key or raise the public 422 validation error."""

    raw_value = request.headers.get("Idempotency-Key")
    value = raw_value.strip() if isinstance(raw_value, str) else ""
    if not value:
        raise ValidationError(
            {"Idempotency-Key": ["이 헤더는 필수입니다."]}
        )
    if len(value) > 128:
        raise ValidationError(
            {"Idempotency-Key": ["128자 이하여야 합니다."]}
        )
    return value
