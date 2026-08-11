"""Inquiry API role boundary."""

from rest_framework.permissions import BasePermission


INQUIRY_CANCEL_PERMISSION = "inquiries.cancel_inquiry"


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


class IsConsultant(BasePermission):
    """Allow only an active authenticated CONSULTANT account."""

    def has_permission(self, request, view) -> bool:
        del view
        user = getattr(request, "user", None)
        return bool(
            user is not None
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", False)
            and getattr(user, "role_code", None) == "CONSULTANT"
        )


class CanAttemptInquiryCancel(BasePermission):
    """Allow only roles named by CANCEL_INQUIRY before object masking."""

    def has_permission(self, request, view) -> bool:
        del view
        user = getattr(request, "user", None)
        if not bool(
            user is not None
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", False)
        ):
            return False
        role = getattr(user, "role_code", None)
        if role in {"CUSTOMER", "CONSULTANT"}:
            return True
        return bool(
            role == "OPERATOR" and user.has_perm(INQUIRY_CANCEL_PERMISSION)
        )
