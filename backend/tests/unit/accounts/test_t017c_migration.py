"""T-017C auth generation, audit schema, cutover, and rollback migration."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


pytestmark = pytest.mark.django_db(transaction=True)

MIGRATE_FROM = ("accounts", "0004_add_user_is_synthetic")
MIGRATE_TO = ("accounts", "0005_account_lifecycle_and_audit")
TOKEN_TARGET = (
    "token_blacklist",
    "0013_alter_blacklistedtoken_options_and_more",
)


def test_forward_backfills_auth_version_blacklists_refresh_and_rolls_back_schema():
    executor = MigrationExecutor(connection)
    executor.migrate([MIGRATE_FROM, TOKEN_TARGET])
    old_apps = executor.loader.project_state(
        [MIGRATE_FROM, TOKEN_TARGET]
    ).apps
    OldUser = old_apps.get_model("accounts", "User")
    OutstandingToken = old_apps.get_model("token_blacklist", "OutstandingToken")
    user = OldUser.objects.create(
        password="!",
        public_id=uuid4(),
        username="SYN-T017C-MIGRATION-001",
        full_name="Synthetic migration user",
        role_code="CUSTOMER",
        is_staff=False,
        is_active=True,
        is_synthetic=True,
        date_joined=timezone.now(),
    )
    outstanding = OutstandingToken.objects.create(
        user_id=user.pk,
        jti=uuid4().hex,
        token="synthetic-not-a-real-token",
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=1),
    )

    executor = MigrationExecutor(connection)
    executor.migrate([MIGRATE_TO, TOKEN_TARGET])
    migrated_apps = executor.loader.project_state(
        [MIGRATE_TO, TOKEN_TARGET]
    ).apps
    MigratedUser = migrated_apps.get_model("accounts", "User")
    BlacklistedToken = migrated_apps.get_model(
        "token_blacklist",
        "BlacklistedToken",
    )
    LifecycleLock = migrated_apps.get_model("accounts", "AccountLifecycleLock")

    assert MigratedUser.objects.get(pk=user.pk).auth_version == 1
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MigratedUser.objects.filter(pk=user.pk).update(auth_version=0)
    assert BlacklistedToken.objects.filter(token_id=outstanding.pk).exists()
    assert LifecycleLock.objects.filter(pk=1).exists()

    executor = MigrationExecutor(connection)
    executor.migrate([MIGRATE_FROM, TOKEN_TARGET])
    rolled_back_apps = executor.loader.project_state(
        [MIGRATE_FROM, TOKEN_TARGET]
    ).apps
    field_names = {
        field.name
        for field in rolled_back_apps.get_model("accounts", "User")._meta.fields
    }
    assert "auth_version" not in field_names
    RolledBackBlacklist = rolled_back_apps.get_model(
        "token_blacklist",
        "BlacklistedToken",
    )
    assert RolledBackBlacklist.objects.filter(token_id=outstanding.pk).exists()

    MigrationExecutor(connection).migrate([MIGRATE_TO, TOKEN_TARGET])
