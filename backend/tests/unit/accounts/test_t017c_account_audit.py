"""T-017C append-only audit and last account-administrator protection."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError

from apps.accounts.models import AccountAuditEvent, User
from apps.accounts.repositories.account_audit_repository import (
    AccountAuditRepository,
)
from apps.accounts.services.account_lifecycle_service import (
    AccountLifecycleError,
    AccountLifecycleService,
)


pytestmark = pytest.mark.django_db


def create_operator(sequence: int) -> User:
    return User.objects.create_user(
        username=f"SYN-T017C-OPERATOR-{sequence:03d}",
        password="T017C-Synthetic-Password-2026!",
        full_name=f"Synthetic operator {sequence}",
        role_code=User.Role.OPERATOR,
        employee_no=f"SYN-T017C-EMP-{sequence:03d}",
        is_synthetic=True,
    )


def create_superuser(sequence: int) -> User:
    return User.objects.create_superuser(
        username=f"SYN-T017C-AUDIT-SUPER-{sequence:03d}",
        password="T017C-Synthetic-Password-2026!",
        full_name=f"Synthetic audit superuser {sequence}",
        employee_no=f"SYN-T017C-AUDIT-EMP-{sequence:03d}",
        is_synthetic=True,
    )


def test_last_practical_account_admin_cannot_be_deactivated_or_revoked():
    actor = create_superuser(1)
    target = create_operator(1)
    AccountLifecycleService.grant_account_admin(
        actor=actor,
        target=target,
        reason="Initial synthetic account manager",
        correlation_id=uuid4(),
    )

    with pytest.raises(AccountLifecycleError) as deactivate_error:
        AccountLifecycleService.deactivate(
            actor=actor,
            target=target,
            reason="Must keep one practical administrator",
            correlation_id=uuid4(),
        )
    assert deactivate_error.value.code == "LAST_ADMIN_PROTECTED"

    with pytest.raises(AccountLifecycleError) as revoke_error:
        AccountLifecycleService.revoke_account_admin(
            actor=actor,
            target=target,
            reason="Must keep one practical administrator",
            correlation_id=uuid4(),
        )
    assert revoke_error.value.code == "LAST_ADMIN_PROTECTED"

    target.refresh_from_db()
    assert target.is_active is True
    assert target.is_staff is True
    assert AccountAuditEvent.objects.filter(
        target_user=target,
        event_type=AccountAuditEvent.EventType.ADMIN_PERMISSION_CHANGE,
    ).count() == 1


def test_second_practical_admin_allows_first_to_be_deactivated():
    actor = create_superuser(2)
    first = create_operator(2)
    second = create_operator(3)
    for target in (first, second):
        AccountLifecycleService.grant_account_admin(
            actor=actor,
            target=target,
            reason="Synthetic account manager grant",
            correlation_id=uuid4(),
        )

    AccountLifecycleService.deactivate(
        actor=actor,
        target=first,
        reason="Second practical administrator remains",
        correlation_id=uuid4(),
    )

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.is_active is False
    assert second.is_active is True and second.is_staff is True


def test_audit_is_append_only_and_contains_no_secret_values():
    actor = create_superuser(3)
    target = create_operator(4)
    AccountLifecycleService.grant_account_admin(
        actor=actor,
        target=target,
        reason="Synthetic audit security test",
        correlation_id=uuid4(),
    )
    event = AccountAuditEvent.objects.get(target_user=target)
    serialized = json.dumps(
        {
            "before": event.before_values,
            "after": event.after_values,
            "changed": event.changed_fields,
        },
        sort_keys=True,
    ).lower()

    for forbidden in ("password", "token", "secret", "hash"):
        assert forbidden not in serialized
    assert event.reason == "Synthetic audit security test"
    assert event.data_classification == "synthetic"

    event.reason = "tampered"
    with pytest.raises(RuntimeError, match="append-only"):
        event.save()
    with pytest.raises(RuntimeError, match="append-only"):
        event.delete()
    with pytest.raises(RuntimeError, match="append-only"):
        AccountAuditEvent.objects.filter(pk=event.pk).update(reason="tampered")
    with pytest.raises(RuntimeError, match="append-only"):
        AccountAuditEvent.objects.filter(pk=event.pk).delete()


def test_last_recoverable_superuser_is_protected():
    target = create_superuser(4)
    actor = create_operator(5)
    AccountLifecycleService.grant_account_admin(
        actor=target,
        target=actor,
        reason="Create independent practical administrator",
        correlation_id=uuid4(),
    )

    with pytest.raises(AccountLifecycleError) as error:
        AccountLifecycleService.deactivate(
            actor=actor,
            target=target,
            reason="Must keep one recoverable superuser",
            correlation_id=uuid4(),
        )

    assert error.value.code == "LAST_ADMIN_PROTECTED"
    target.refresh_from_db()
    assert target.is_active is True


def test_direct_fixed_group_m2m_mutation_is_rejected():
    actor = create_superuser(5)
    target = create_operator(6)
    AccountLifecycleService.grant_account_admin(
        actor=actor,
        target=target,
        reason="Create protected practical administrator",
        correlation_id=uuid4(),
    )
    group = Group.objects.get(name="T017_ACCOUNT_ADMINISTRATORS")

    with pytest.raises(ValidationError):
        with transaction.atomic():
            target.groups.remove(group)
    with pytest.raises(ValidationError):
        with transaction.atomic():
            group.permissions.clear()


def test_audit_rejects_secret_payload_and_protects_actor_target_rows():
    actor = create_superuser(6)
    target = create_operator(7)

    with pytest.raises(ValidationError):
        AccountAuditRepository.record(
            actor=actor,
            target=target,
            event_type=AccountAuditEvent.EventType.UPDATE,
            before_values={"groups": ["synthetic-secret-token"]},
            after_values={"groups": []},
            changed_fields=["groups"],
            reason="Reject secret-like payload",
            correlation_id=uuid4(),
        )
    assert not AccountAuditEvent.objects.filter(target_user=target).exists()

    AccountLifecycleService.grant_account_admin(
        actor=actor,
        target=target,
        reason="Create immutable audit foreign keys",
        correlation_id=uuid4(),
    )
    with pytest.raises(ProtectedError):
        with transaction.atomic():
            target.delete()
    with pytest.raises(RuntimeError, match="append-only"):
        AccountAuditEvent.objects.bulk_create([])
