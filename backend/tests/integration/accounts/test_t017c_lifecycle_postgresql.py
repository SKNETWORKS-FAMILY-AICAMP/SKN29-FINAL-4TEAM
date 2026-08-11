"""PostgreSQL-only concurrency proof for the T-017C singleton lock."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from django.db import connection, connections

from apps.accounts.models import AccountAuditEvent, User
from apps.accounts.services.account_lifecycle_service import (
    AccountLifecycleError,
    AccountLifecycleService,
)


pytestmark = pytest.mark.django_db(transaction=True)


def create_operator(sequence: int) -> User:
    return User.objects.create_user(
        username=f"SYN-T017C-PG-OPERATOR-{sequence:03d}",
        password="T017C-PostgreSQL-Synthetic-Password-2026!",
        full_name=f"Synthetic PostgreSQL operator {sequence}",
        role_code=User.Role.OPERATOR,
        employee_no=f"SYN-T017C-PG-EMP-{sequence:03d}",
        is_synthetic=True,
    )


def revoke_concurrently(
    *,
    actor_pk: int,
    target_pk: int,
    barrier: Barrier,
) -> str:
    connections.close_all()
    try:
        actor = User.objects.get(pk=actor_pk)
        target = User.objects.get(pk=target_pk)
        barrier.wait(timeout=10)
        try:
            AccountLifecycleService.revoke_account_admin(
                actor=actor,
                target=target,
                reason="Concurrent PostgreSQL last-admin verification",
                correlation_id=uuid4(),
            )
        except AccountLifecycleError as exc:
            return exc.code
        return "REVOKED"
    finally:
        connections.close_all()


def test_two_concurrent_revokes_preserve_one_practical_administrator():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    actor = User.objects.create_superuser(
        username="SYN-T017C-PG-SUPERUSER",
        password="T017C-PostgreSQL-Superuser-Password-2026!",
        full_name="Synthetic PostgreSQL superuser",
        employee_no="SYN-T017C-PG-SUPER-EMP-001",
        is_synthetic=True,
    )
    first = create_operator(1)
    second = create_operator(2)
    for target in (first, second):
        AccountLifecycleService.grant_account_admin(
            actor=actor,
            target=target,
            reason="Prepare PostgreSQL concurrency administrator",
            correlation_id=uuid4(),
        )

    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                revoke_concurrently,
                actor_pk=actor.pk,
                target_pk=target.pk,
                barrier=barrier,
            )
            for target in (first, second)
        ]
        results = [future.result(timeout=30) for future in futures]

    assert sorted(results) == ["LAST_ADMIN_PROTECTED", "REVOKED"]
    first.refresh_from_db()
    second.refresh_from_db()
    assert sum(user.is_staff for user in (first, second)) == 1
    assert sum(
        user.groups.filter(name="T017_ACCOUNT_ADMINISTRATORS").exists()
        for user in (first, second)
    ) == 1
    assert AccountAuditEvent.objects.filter(
        target_user__in=(first, second),
        event_type=AccountAuditEvent.EventType.ADMIN_PERMISSION_CHANGE,
    ).count() == 3
