"""Consultation role permission boundary."""

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
