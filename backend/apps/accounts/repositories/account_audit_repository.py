"""Create-only persistence boundary for account lifecycle audit events."""

from __future__ import annotations

from uuid import UUID

from apps.accounts.models import AccountAuditEvent, User


class AccountAuditRepository:
    """Persist one immutable event after the owning transaction is valid."""

    @staticmethod
    def record(
        *,
        actor: User,
        target: User,
        event_type: str,
        before_values: dict[str, object],
        after_values: dict[str, object],
        changed_fields: list[str],
        reason: str,
        correlation_id: UUID,
    ) -> AccountAuditEvent:
        return AccountAuditEvent.objects.create(
            actor=actor,
            target_user=target,
            event_type=event_type,
            before_values=before_values,
            after_values=after_values,
            changed_fields=changed_fields,
            reason=reason,
            correlation_id=correlation_id,
            data_classification="synthetic",
        )
