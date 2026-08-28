"""Single-supervisor policy shared by the internal Django Admin boundary."""

from __future__ import annotations

from typing import Any

from django.conf import settings

from apps.accounts.models import User


def configured_supervisor_username() -> str:
    """Return the normalized, non-secret supervisor account identifier."""

    return str(
        getattr(settings, "WATERBRIDGE_SUPERVISOR_USERNAME", "") or ""
    ).strip()


def is_waterbridge_supervisor(user: Any) -> bool:
    """Fail closed unless the request user is the configured supervisor."""

    configured_username = configured_supervisor_username()
    return bool(
        configured_username
        and user
        and user.is_authenticated
        and user.is_active
        and user.is_synthetic
        and user.is_staff
        and user.is_superuser
        and user.role_code == User.Role.OPERATOR
        and user.has_usable_password()
        and str(user.username).casefold() == configured_username.casefold()
    )
