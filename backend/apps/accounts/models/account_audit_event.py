"""Append-only audit ledger for synthetic-account lifecycle changes."""

from __future__ import annotations

import json
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


ALLOWED_SNAPSHOT_KEYS = frozenset(
    {
        "role_code",
        "is_active",
        "is_staff",
        "is_superuser",
        "auth_version",
        "groups",
        "permissions",
        "credential_changed",
    }
)
ALLOWED_CHANGED_FIELDS = frozenset(
    {
        *ALLOWED_SNAPSHOT_KEYS,
        "full_name",
        "email",
        "phone",
        "account_created",
    }
)
FORBIDDEN_KEY_FRAGMENTS = ("password", "token", "secret", "hash")
ACCOUNT_AUDIT_EVENT_TYPES = (
    "CREATE",
    "UPDATE",
    "DEACTIVATE",
    "REACTIVATE",
    "ROLE_CHANGE",
    "ADMIN_PERMISSION_CHANGE",
    "PASSWORD_CHANGE",
    "PASSWORD_RESET",
    "CREDENTIAL_RECOVERY",
)


class AppendOnlyAuditQuerySet(models.QuerySet):
    """Allow inserts and reads but reject all ORM mutation shortcuts."""

    @staticmethod
    def _raise_append_only() -> None:
        raise RuntimeError("Account audit events are append-only.")

    def update(self, **kwargs):
        del kwargs
        self._raise_append_only()

    def delete(self):
        self._raise_append_only()

    def bulk_update(self, objs, fields, batch_size=None):
        del objs, fields, batch_size
        self._raise_append_only()

    def bulk_create(
        self,
        objs,
        batch_size=None,
        ignore_conflicts=False,
        update_conflicts=False,
        update_fields=None,
        unique_fields=None,
    ):
        del (
            objs,
            batch_size,
            ignore_conflicts,
            update_conflicts,
            update_fields,
            unique_fields,
        )
        self._raise_append_only()


class AccountAuditEvent(models.Model):
    """Security audit event containing allowlisted, non-PII state only."""

    class EventType(models.TextChoices):
        CREATE = "CREATE", "Create"
        UPDATE = "UPDATE", "Update"
        DEACTIVATE = "DEACTIVATE", "Deactivate"
        REACTIVATE = "REACTIVATE", "Reactivate"
        ROLE_CHANGE = "ROLE_CHANGE", "Role change"
        ADMIN_PERMISSION_CHANGE = (
            "ADMIN_PERMISSION_CHANGE",
            "Admin permission change",
        )
        PASSWORD_CHANGE = "PASSWORD_CHANGE", "Password change"
        PASSWORD_RESET = "PASSWORD_RESET", "Password reset"
        CREDENTIAL_RECOVERY = "CREDENTIAL_RECOVERY", "Credential recovery"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    target_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="account_audit_events",
    )
    actor = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="performed_account_audit_events",
    )
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    before_values = models.JSONField(default=dict, blank=True)
    after_values = models.JSONField(default=dict)
    changed_fields = models.JSONField(default=list)
    reason = models.TextField()
    correlation_id = models.UUIDField()
    occurred_at = models.DateTimeField(default=timezone.now, editable=False)
    data_classification = models.CharField(
        max_length=20,
        default="synthetic",
        editable=False,
    )

    objects = AppendOnlyAuditQuerySet.as_manager()

    class Meta:
        db_table = "accounts_account_audit_event"
        ordering = ("occurred_at", "id")
        indexes = [
            models.Index(
                fields=("target_user", "occurred_at"),
                name="acct_audit_target_time_idx",
            ),
            models.Index(
                fields=("correlation_id",),
                name="acct_audit_correlation_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(data_classification="synthetic"),
                name="acct_audit_synthetic_only",
            ),
            models.CheckConstraint(
                condition=Q(event_type__in=ACCOUNT_AUDIT_EVENT_TYPES),
                name="acct_audit_valid_event_type",
            ),
        ]

    @staticmethod
    def _validate_snapshot(value: object, field_name: str) -> None:
        if not isinstance(value, dict):
            raise ValidationError({field_name: "Audit snapshots must be objects."})
        invalid = set(value) - ALLOWED_SNAPSHOT_KEYS
        if invalid:
            raise ValidationError(
                {field_name: f"Disallowed audit keys: {sorted(invalid)}"}
            )
        for key in value:
            normalized = str(key).lower()
            if any(fragment in normalized for fragment in FORBIDDEN_KEY_FRAGMENTS):
                raise ValidationError({field_name: "Secret fields are forbidden."})
        serialized = json.dumps(value, sort_keys=True).lower()
        if any(fragment in serialized for fragment in FORBIDDEN_KEY_FRAGMENTS):
            raise ValidationError({field_name: "Secret values are forbidden."})

    def clean(self) -> None:
        super().clean()
        self._validate_snapshot(self.before_values, "before_values")
        self._validate_snapshot(self.after_values, "after_values")
        if not isinstance(self.changed_fields, list) or any(
            not isinstance(field, str) or field not in ALLOWED_CHANGED_FIELDS
            for field in self.changed_fields
        ):
            raise ValidationError(
                {"changed_fields": "Changed fields must use the audit allowlist."}
            )
        if not str(self.reason or "").strip():
            raise ValidationError({"reason": "A non-empty reason is required."})
        if self.data_classification != "synthetic":
            raise ValidationError(
                {"data_classification": "Only synthetic data is allowed."}
            )

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Account audit events are append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        del args, kwargs
        raise RuntimeError("Account audit events are append-only.")


class AccountLifecycleLock(models.Model):
    """Singleton row used to serialize last-administrator checks."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    label = models.CharField(max_length=40, default="ACCOUNT_LIFECYCLE")

    class Meta:
        db_table = "accounts_account_lifecycle_lock"
        constraints = [
            models.CheckConstraint(
                condition=Q(id=1),
                name="acct_lifecycle_lock_singleton",
            )
        ]

    def delete(self, *args, **kwargs):
        del args, kwargs
        raise RuntimeError("The account lifecycle lock cannot be deleted.")
