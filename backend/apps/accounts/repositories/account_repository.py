"""사용자·역할 ORM 접근 Repository."""

from __future__ import annotations

from apps.accounts.models import User


class AccountRepository:
    """인증 Service가 사용하는 사용자 원장 조회."""

    @staticmethod
    def find_active_by_demo_code(demo_user_code: str) -> User | None:
        return (
            User.objects.filter(
                username=demo_user_code,
                is_active=True,
            )
            .select_related("customer_profile")
            .first()
        )

    @staticmethod
    def find_active_by_id(user_id: str) -> User | None:
        return (
            User.objects.filter(
                pk=user_id,
                is_active=True,
            )
            .select_related("customer_profile")
            .first()
        )
