"""Consultation role permission boundary."""

import secrets

from django.conf import settings
from rest_framework.permissions import BasePermission


class IsConsultant(BasePermission):
    """Allow only active authenticated consultant accounts."""

    def has_permission(self, request, view) -> bool:
        del view
        user = getattr(request, "user", None)
        return bool(
            user is not None
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", False)
            and getattr(user, "role_code", None) == "CONSULTANT"
        )


class HasValidAIHandoffToken(BasePermission):
    """Fail closed unless the AI service supplies the protected token."""

    def has_permission(self, request, view) -> bool:
        del view
        expected = str(
            getattr(settings, "AI_HANDOFF_INTERNAL_TOKEN", "") or ""
        ).strip()
        supplied = str(
            request.headers.get("X-AI-Handoff-Token", "") or ""
        ).strip()
        return bool(
            expected
            and supplied
            and secrets.compare_digest(supplied, expected)
        )
