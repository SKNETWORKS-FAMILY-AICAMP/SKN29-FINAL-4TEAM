"""T-017C token generation and account lifecycle security boundaries."""

from __future__ import annotations

from uuid import uuid4
from unittest.mock import patch

import pytest
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.models import AccountAuditEvent, User
from apps.accounts.services.account_lifecycle_service import (
    AccountLifecycleError,
    AccountLifecycleService,
)
from apps.accounts.services.authentication_service import AuthenticationService


pytestmark = pytest.mark.django_db


def create_customer(sequence: int) -> User:
    return User.objects.create_user(
        username=f"SYN-T017C-CUSTOMER-{sequence:03d}",
        full_name=f"Synthetic customer {sequence}",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )


def create_superuser(sequence: int) -> User:
    return User.objects.create_superuser(
        username=f"SYN-T017C-SUPER-{sequence:03d}",
        password="T017C-Synthetic-Password-2026!",
        full_name=f"Synthetic superuser {sequence}",
        employee_no=f"SYN-T017C-SUPER-EMP-{sequence:03d}",
        is_synthetic=True,
    )


def bearer(client, raw_access: str):
    return client.get(
        "/api/v1/me",
        HTTP_AUTHORIZATION=f"Bearer {raw_access}",
    )


def test_access_and_refresh_include_positive_auth_version_claim():
    user = create_customer(1)

    pair = AuthenticationService.issue_pair(user)
    access = AccessToken(pair.access_token)
    refresh = RefreshToken(pair.refresh_token)

    assert access["auth_version"] == 1
    assert refresh["auth_version"] == 1
    assert isinstance(access["auth_version"], int)
    assert not isinstance(access["auth_version"], bool)
    outstanding = OutstandingToken.objects.get(jti=str(refresh["jti"]))
    persisted = RefreshToken(outstanding.token)
    assert persisted["role_code"] == user.role_code
    assert persisted["auth_version"] == user.auth_version


@pytest.mark.parametrize(
    "invalid_version",
    [None, "1", True, 0, -1, 2],
    ids=("missing", "string", "boolean", "zero", "negative", "future"),
)
def test_protected_api_fails_closed_for_invalid_auth_version(
    client,
    invalid_version,
):
    user = create_customer(2)
    token = AccessToken.for_user(user)
    token["role_code"] = user.role_code
    if invalid_version is None:
        token.payload.pop("auth_version", None)
    else:
        token["auth_version"] = invalid_version

    response = bearer(client, str(token))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


@pytest.mark.parametrize(
    "invalid_version",
    [None, "1", True, 0, -1, 2],
    ids=("missing", "string", "boolean", "zero", "negative", "future"),
)
def test_refresh_fails_closed_for_invalid_auth_version(client, invalid_version):
    user = create_customer(20)
    token = RefreshToken.for_user(user)
    token["role_code"] = user.role_code
    if invalid_version is None:
        token.payload.pop("auth_version", None)
    else:
        token["auth_version"] = invalid_version

    response = client.post(
        "/api/v1/auth/refresh",
        {"refresh_token": str(token)},
        content_type="application/json",
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_deactivate_reactivate_keeps_old_access_and_refresh_revoked(client):
    actor = create_superuser(1)
    target = create_customer(3)
    first = AuthenticationService.issue_pair(target)
    second = AuthenticationService.issue_pair(target)

    AccountLifecycleService.deactivate(
        actor=actor,
        target=target,
        reason="Synthetic QA deactivation",
        correlation_id=uuid4(),
    )
    target.refresh_from_db()

    assert target.is_active is False
    assert target.auth_version == 2
    assert BlacklistedToken.objects.filter(
        token__user=target,
    ).count() == OutstandingToken.objects.filter(user=target).count() == 2
    assert bearer(client, first.access_token).status_code == 401

    AccountLifecycleService.reactivate(
        actor=actor,
        target=target,
        reason="Synthetic QA reactivation",
        correlation_id=uuid4(),
    )
    target.refresh_from_db()

    assert target.is_active is True
    assert target.auth_version == 3
    assert bearer(client, first.access_token).status_code == 401
    with pytest.raises(TokenError):
        RefreshToken(first.refresh_token).check_blacklist()

    replacement = AuthenticationService.issue_pair(target)
    assert bearer(client, replacement.access_token).status_code == 200
    assert list(
        AccountAuditEvent.objects.filter(target_user=target)
        .order_by("occurred_at")
        .values_list("event_type", flat=True)
    ) == ["DEACTIVATE", "REACTIVATE"]


def test_self_deactivation_and_duplicate_state_change_roll_back():
    actor = create_superuser(2)
    starting_version = actor.auth_version

    with pytest.raises(AccountLifecycleError) as self_error:
        AccountLifecycleService.deactivate(
            actor=actor,
            target=actor,
            reason="Must be rejected",
            correlation_id=uuid4(),
        )
    assert self_error.value.code == "SELF_DEACTIVATION_DENIED"

    actor.refresh_from_db()
    assert actor.is_active is True
    assert actor.auth_version == starting_version
    assert not AccountAuditEvent.objects.filter(target_user=actor).exists()

    target = create_customer(4)
    with pytest.raises(AccountLifecycleError) as state_error:
        AccountLifecycleService.reactivate(
            actor=actor,
            target=target,
            reason="Already active",
            correlation_id=uuid4(),
        )
    assert state_error.value.code == "ACCOUNT_STATE_CONFLICT"
    assert not AccountAuditEvent.objects.filter(target_user=target).exists()


def test_audit_failure_rolls_back_user_and_refresh_blacklist():
    actor = create_superuser(3)
    target = create_customer(5)
    pair = AuthenticationService.issue_pair(target)
    outstanding = OutstandingToken.objects.get(
        jti=str(RefreshToken(pair.refresh_token)["jti"])
    )

    with patch(
        "apps.accounts.services.account_lifecycle_service."
        "AccountAuditRepository.record",
        side_effect=RuntimeError("audit unavailable"),
    ):
        with pytest.raises(RuntimeError, match="audit unavailable"):
            AccountLifecycleService.deactivate(
                actor=actor,
                target=target,
                reason="Rollback injection",
                correlation_id=uuid4(),
            )

    target.refresh_from_db()
    assert target.is_active is True
    assert target.auth_version == 1
    assert not BlacklistedToken.objects.filter(token=outstanding).exists()
    assert not AccountAuditEvent.objects.filter(target_user=target).exists()


def test_refresh_blacklist_failure_rolls_back_user_and_audit():
    actor = create_superuser(4)
    target = create_customer(6)
    AuthenticationService.issue_pair(target)

    with patch.object(
        AccountLifecycleService,
        "_revoke_all_refresh_tokens",
        side_effect=RuntimeError("blacklist unavailable"),
    ):
        with pytest.raises(RuntimeError, match="blacklist unavailable"):
            AccountLifecycleService.deactivate(
                actor=actor,
                target=target,
                reason="Rollback blacklist injection",
                correlation_id=uuid4(),
            )

    target.refresh_from_db()
    assert target.is_active is True
    assert target.auth_version == 1
    assert not AccountAuditEvent.objects.filter(target_user=target).exists()
