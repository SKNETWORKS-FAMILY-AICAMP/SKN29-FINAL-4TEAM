"""현재 인증 사용자 응답 조립 Service."""

from __future__ import annotations

from apps.accounts.models import User


class AccountService:
    """민감 필드를 제외한 현재 사용자 projection을 제공한다."""

    @staticmethod
    def user_data(user: User) -> dict:
        profile_data = None
        if user.role_code == User.Role.CUSTOMER:
            try:
                profile = user.customer_profile
            except User.customer_profile.RelatedObjectDoesNotExist:
                profile = None
            if profile is not None and profile.deleted_at is None:
                profile_data = {
                    "id": str(profile.public_id),
                    "customer_no": profile.customer_no,
                    "customer_name": profile.customer_name,
                    "is_synthetic": profile.is_synthetic,
                }

        return {
            "id": str(user.public_id),
            "display_name": user.full_name,
            "role_code": user.role_code,
            "is_active": user.is_active,
            "customer_profile": profile_data,
            "allowed_actions": [],
        }
