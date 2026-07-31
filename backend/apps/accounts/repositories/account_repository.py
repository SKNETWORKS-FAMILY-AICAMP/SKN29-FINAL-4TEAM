"""사용자·역할 ORM 접근 Repository."""

from __future__ import annotations

from uuid import UUID

from apps.accounts.models import User


class AccountRepository:
    """인증 Service가 사용하는 사용자 원장 조회."""

    @staticmethod
    def find_active_by_demo_code(demo_user_code: str) -> User | None:
        code = str(demo_user_code).strip()
        if code.startswith("DEMO-"):
            filters = {
                "username": code,
                "is_active": True,
            }
        elif code.startswith("SYN-"):
            filters = {
                "is_active": True,
                "role_code": User.Role.CUSTOMER,
                "customer_profile__customer_no": code,
                "customer_profile__is_synthetic": True,
                "customer_profile__deleted_at__isnull": True,
            }
        else:
            return None

        return (
            User.objects.filter(**filters)
            .select_related("customer_profile")
            .first()
        )

    @staticmethod
    def find_active_by_subject(subject: str) -> User | None:
        """공개 UUID JWT subject로 활성 사용자만 조회한다."""
        normalized = str(subject).strip()
        try:
            public_id = UUID(normalized)
        except (ValueError, AttributeError, TypeError):
            return None
        return (
            User.objects.filter(
                is_active=True,
                public_id=public_id,
            )
            .select_related("customer_profile")
            .first()
        )

    @classmethod
    def find_active_by_id(cls, user_id: str) -> User | None:
        """공개 사용자 UUID를 받는 기존 호출명 호환 alias."""
        return cls.find_active_by_subject(user_id)
