"""Consultation role permission boundary."""

from rest_framework.permissions import BasePermission

from common.permissions import HasValidAIInternalToken


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


class HasValidAIHandoffToken(HasValidAIInternalToken):
    """Backward-compatible name for the internal AI service boundary."""
