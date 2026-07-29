"""사용자·역할 ORM 접근 Repository."""

from __future__ import annotations

from uuid import UUID

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
    def find_active_by_subject(subject: str) -> User | None:
        """공개 UUID subject를 우선하고 기존 문자열 PK도 임시 허용한다."""
        normalized = str(subject).strip()
        try:
            public_id = UUID(normalized)
        except (ValueError, AttributeError, TypeError):
            filters = {"pk": normalized}
        else:
            filters = {"public_id": public_id}
        return (
            User.objects.filter(
                is_active=True,
                **filters,
            )
            .select_related("customer_profile")
            .first()
        )

    @classmethod
    def find_active_by_id(cls, user_id: str) -> User | None:
        """기존 호출자 호환용 alias."""
        return cls.find_active_by_subject(user_id)
