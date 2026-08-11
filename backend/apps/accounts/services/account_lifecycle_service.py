"""Atomic T-017C lifecycle, token revocation, and audit boundary."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.contrib.auth.models import Group, Permission
from django.db import transaction
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.accounts.account_admin_policy import (
    ACCOUNT_ADMIN_GROUP,
    ACCOUNT_ADMIN_PERMISSION_CODES,
)
from apps.accounts.account_admin_guards import allow_account_admin_m2m_change
from apps.accounts.models import (
    AccountAuditEvent,
    AccountLifecycleLock,
    User,
)
from apps.accounts.repositories.account_audit_repository import (
    AccountAuditRepository,
)


@dataclass(eq=False)
class AccountLifecycleError(Exception):
    """Stable internal error used by Admin and management commands."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


class AccountLifecycleService:
    """Serialize account changes so no stale token or admin gap survives."""

    audit_repository = AccountAuditRepository

    @staticmethod
    def _reason(value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise AccountLifecycleError(
                "REASON_REQUIRED",
                "A non-empty account change reason is required.",
            )
        return normalized

    @staticmethod
    def _correlation_id(value: UUID | str) -> UUID:
        try:
            return value if isinstance(value, UUID) else UUID(str(value))
        except (TypeError, ValueError, AttributeError) as exc:
            raise AccountLifecycleError(
                "CORRELATION_ID_REQUIRED",
                "A valid correlation UUID is required.",
            ) from exc

    @staticmethod
    def _ensure_policy_group() -> Group:
        permissions = list(
            Permission.objects.filter(
                content_type__app_label="accounts",
                content_type__model="user",
                codename__in=ACCOUNT_ADMIN_PERMISSION_CODES,
            )
        )
        found = {permission.codename for permission in permissions}
        if found != set(ACCOUNT_ADMIN_PERMISSION_CODES):
            raise AccountLifecycleError(
                "ACCOUNT_ADMIN_POLICY_INCOMPLETE",
                f"Missing account permissions: {sorted(set(ACCOUNT_ADMIN_PERMISSION_CODES) - found)}",
            )
        group, _ = Group.objects.get_or_create(name=ACCOUNT_ADMIN_GROUP)
        current = set(group.permissions.values_list("codename", flat=True))
        if current != set(ACCOUNT_ADMIN_PERMISSION_CODES):
            with allow_account_admin_m2m_change():
                group.permissions.set(permissions)
        return group

    @staticmethod
    def _is_practical_admin(user: User, group: Group | None = None) -> bool:
        if not (
            user.is_active
            and user.is_synthetic
            and user.is_staff
            and user.role_code == User.Role.OPERATOR
            and user.has_usable_password()
        ):
            return False
        group = group or Group.objects.filter(name=ACCOUNT_ADMIN_GROUP).first()
        if not group or not user.groups.filter(pk=group.pk).exists():
            return False
        permission_codes = set(
            group.permissions.filter(
                content_type__app_label="accounts",
                content_type__model="user",
            ).values_list("codename", flat=True)
        )
        return permission_codes.issuperset(ACCOUNT_ADMIN_PERMISSION_CODES)

    @classmethod
    def _authorize_actor(cls, actor: User, group: Group | None = None) -> None:
        if not (
            actor.is_active
            and actor.is_synthetic
            and actor.is_staff
            and actor.role_code == User.Role.OPERATOR
            and actor.has_usable_password()
        ):
            raise AccountLifecycleError(
                "ACCOUNT_ADMIN_REQUIRED",
                "An active synthetic account administrator is required.",
            )
        if actor.is_superuser:
            return
        if not cls._is_practical_admin(actor, group):
            raise AccountLifecycleError(
                "ACCOUNT_ADMIN_REQUIRED",
                "The fixed account-administrator membership is required.",
            )

    @staticmethod
    def _snapshot(user: User) -> dict[str, object]:
        group_names = sorted(user.groups.values_list("name", flat=True))
        permission_codes = sorted(
            set(
                Permission.objects.filter(group__user=user).values_list(
                    "codename",
                    flat=True,
                )
            )
            | set(user.user_permissions.values_list("codename", flat=True))
        )
        return {
            "role_code": user.role_code,
            "is_active": user.is_active,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "auth_version": user.auth_version,
            "groups": group_names,
            "permissions": permission_codes,
        }

    @staticmethod
    def _revoke_all_refresh_tokens(target: User) -> None:
        outstanding = list(
            OutstandingToken.objects.select_for_update().filter(user=target)
        )
        for token in outstanding:
            BlacklistedToken.objects.get_or_create(token=token)

    @staticmethod
    def _lock_users(actor: User, target: User) -> tuple[User, User]:
        AccountLifecycleLock.objects.select_for_update().get(pk=1)
        locked = {
            user.pk: user
            for user in User.objects.select_for_update()
            .filter(pk__in={actor.pk, target.pk})
            .order_by("pk")
        }
        if actor.pk not in locked or target.pk not in locked:
            raise AccountLifecycleError(
                "ACCOUNT_NOT_FOUND",
                "The actor or target account no longer exists.",
            )
        return locked[actor.pk], locked[target.pk]

    @staticmethod
    def _require_synthetic_target(target: User) -> None:
        if not target.is_synthetic:
            raise AccountLifecycleError(
                "SYNTHETIC_ACCOUNT_REQUIRED",
                "T-017C can change synthetic accounts only.",
            )

    @staticmethod
    def _protect_last_superuser(target: User) -> None:
        if not (
            target.is_active
            and target.is_staff
            and target.is_superuser
            and target.has_usable_password()
        ):
            return
        remaining = User.objects.filter(
            is_active=True,
            is_staff=True,
            is_superuser=True,
        ).exclude(pk=target.pk)
        if not any(user.has_usable_password() for user in remaining.iterator()):
            raise AccountLifecycleError(
                "LAST_ADMIN_PROTECTED",
                "The last active superuser cannot be changed.",
            )

    @classmethod
    def _protect_last_practical_admin(cls, target: User, group: Group) -> None:
        if not cls._is_practical_admin(target, group):
            return
        remaining = (
            User.objects.filter(
                is_active=True,
                is_synthetic=True,
                is_staff=True,
                role_code=User.Role.OPERATOR,
                groups=group,
            )
            .exclude(pk=target.pk)
        )
        if not any(user.has_usable_password() for user in remaining.iterator()):
            raise AccountLifecycleError(
                "LAST_ADMIN_PROTECTED",
                "The last active practical account administrator is protected.",
            )

    @classmethod
    def _record(
        cls,
        *,
        actor: User,
        target: User,
        event_type: str,
        before: dict[str, object],
        changed_fields: list[str],
        reason: str,
        correlation_id: UUID,
    ) -> None:
        target.refresh_from_db()
        cls.audit_repository.record(
            actor=actor,
            target=target,
            event_type=event_type,
            before_values=before,
            after_values=cls._snapshot(target),
            changed_fields=changed_fields,
            reason=reason,
            correlation_id=correlation_id,
        )

    @classmethod
    @transaction.atomic
    def deactivate(
        cls,
        *,
        actor: User,
        target: User,
        reason: str,
        correlation_id: UUID | str,
    ) -> User:
        reason = cls._reason(reason)
        correlation_id = cls._correlation_id(correlation_id)
        actor, target = cls._lock_users(actor, target)
        group = cls._ensure_policy_group()
        cls._authorize_actor(actor, group)
        cls._require_synthetic_target(target)
        if actor.pk == target.pk:
            raise AccountLifecycleError(
                "SELF_DEACTIVATION_DENIED",
                "Administrators cannot deactivate their own account.",
            )
        if not target.is_active:
            raise AccountLifecycleError(
                "ACCOUNT_STATE_CONFLICT",
                "The account is already inactive.",
            )
        cls._protect_last_superuser(target)
        cls._protect_last_practical_admin(target, group)
        before = cls._snapshot(target)
        target.is_active = False
        target.auth_version += 1
        target.save(update_fields=["is_active", "auth_version", "updated_at"])
        cls._revoke_all_refresh_tokens(target)
        cls._record(
            actor=actor,
            target=target,
            event_type=AccountAuditEvent.EventType.DEACTIVATE,
            before=before,
            changed_fields=["is_active", "auth_version"],
            reason=reason,
            correlation_id=correlation_id,
        )
        return target

    @classmethod
    @transaction.atomic
    def reactivate(
        cls,
        *,
        actor: User,
        target: User,
        reason: str,
        correlation_id: UUID | str,
    ) -> User:
        reason = cls._reason(reason)
        correlation_id = cls._correlation_id(correlation_id)
        actor, target = cls._lock_users(actor, target)
        group = cls._ensure_policy_group()
        cls._authorize_actor(actor, group)
        cls._require_synthetic_target(target)
        if target.is_active:
            raise AccountLifecycleError(
                "ACCOUNT_STATE_CONFLICT",
                "The account is already active.",
            )
        before = cls._snapshot(target)
        target.is_active = True
        target.auth_version += 1
        target.save(update_fields=["is_active", "auth_version", "updated_at"])
        cls._revoke_all_refresh_tokens(target)
        cls._record(
            actor=actor,
            target=target,
            event_type=AccountAuditEvent.EventType.REACTIVATE,
            before=before,
            changed_fields=["is_active", "auth_version"],
            reason=reason,
            correlation_id=correlation_id,
        )
        return target

    @classmethod
    @transaction.atomic
    def grant_account_admin(
        cls,
        *,
        actor: User,
        target: User,
        reason: str,
        correlation_id: UUID | str,
    ) -> User:
        reason = cls._reason(reason)
        correlation_id = cls._correlation_id(correlation_id)
        actor, target = cls._lock_users(actor, target)
        group = cls._ensure_policy_group()
        cls._authorize_actor(actor, group)
        cls._require_synthetic_target(target)
        if target.is_superuser or target.role_code != User.Role.OPERATOR:
            raise AccountLifecycleError(
                "PRIVILEGE_ESCALATION_DENIED",
                "Only a non-superuser synthetic OPERATOR can receive access.",
            )
        if not target.is_active:
            raise AccountLifecycleError(
                "ACCOUNT_STATE_CONFLICT",
                "Only active accounts can receive administrator access.",
            )
        if not target.has_usable_password():
            raise AccountLifecycleError(
                "PRIVILEGE_ESCALATION_DENIED",
                "Administrator access requires a usable credential.",
            )
        if cls._is_practical_admin(target, group):
            raise AccountLifecycleError(
                "ACCOUNT_STATE_CONFLICT",
                "The account already has administrator access.",
            )
        before = cls._snapshot(target)
        with allow_account_admin_m2m_change():
            target.groups.add(group)
        target.is_staff = True
        target.auth_version += 1
        target.save(update_fields=["is_staff", "auth_version", "updated_at"])
        cls._revoke_all_refresh_tokens(target)
        cls._record(
            actor=actor,
            target=target,
            event_type=AccountAuditEvent.EventType.ADMIN_PERMISSION_CHANGE,
            before=before,
            changed_fields=["is_staff", "auth_version", "groups", "permissions"],
            reason=reason,
            correlation_id=correlation_id,
        )
        return target

    @classmethod
    @transaction.atomic
    def revoke_account_admin(
        cls,
        *,
        actor: User,
        target: User,
        reason: str,
        correlation_id: UUID | str,
    ) -> User:
        reason = cls._reason(reason)
        correlation_id = cls._correlation_id(correlation_id)
        actor, target = cls._lock_users(actor, target)
        group = cls._ensure_policy_group()
        cls._authorize_actor(actor, group)
        cls._require_synthetic_target(target)
        if actor.pk == target.pk:
            raise AccountLifecycleError(
                "SELF_ADMIN_CHANGE_DENIED",
                "Administrators cannot revoke their own access.",
            )
        if target.is_superuser:
            raise AccountLifecycleError(
                "PRIVILEGE_ESCALATION_DENIED",
                "Superuser access is not managed by this service.",
            )
        if not cls._is_practical_admin(target, group):
            raise AccountLifecycleError(
                "ACCOUNT_STATE_CONFLICT",
                "The account does not have practical administrator access.",
            )
        cls._protect_last_practical_admin(target, group)
        before = cls._snapshot(target)
        with allow_account_admin_m2m_change():
            target.groups.remove(group)
        target.is_staff = False
        target.auth_version += 1
        target.save(update_fields=["is_staff", "auth_version", "updated_at"])
        cls._revoke_all_refresh_tokens(target)
        cls._record(
            actor=actor,
            target=target,
            event_type=AccountAuditEvent.EventType.ADMIN_PERMISSION_CHANGE,
            before=before,
            changed_fields=["is_staff", "auth_version", "groups", "permissions"],
            reason=reason,
            correlation_id=correlation_id,
        )
        return target
