"""Shared service-to-service permission boundaries."""

import secrets

from django.conf import settings
from rest_framework.permissions import BasePermission


class HasValidAIInternalToken(BasePermission):
    """Fail closed unless the trusted AI service supplies its token."""

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
