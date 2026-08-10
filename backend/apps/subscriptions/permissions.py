"""Customer-only access boundary for subscription Runtime APIs."""

from rest_framework.permissions import BasePermission


class IsCustomer(BasePermission):
    """Allow only an active authenticated CUSTOMER account."""

    def has_permission(self, request, view) -> bool:
        del view
        user = getattr(request, "user", None)
        return bool(
            user is not None
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", False)
            and getattr(user, "role_code", None) == "CUSTOMER"
        )
