"""T-017B existing-data classification, rejection, and rollback tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


pytestmark = pytest.mark.django_db(transaction=True)

MIGRATE_FROM = ("accounts", "0003_promote_integer_primary_keys")
OPERATIONS_LEDGER = ("operations", "0001_initial")
MIGRATE_TO = ("accounts", "0004_add_user_is_synthetic")
OLD_TARGETS = [MIGRATE_FROM, OPERATIONS_LEDGER]
NEW_TARGETS = [MIGRATE_TO]


def _state_apps(targets):
    executor = MigrationExecutor(connection)
    return executor.loader.project_state(targets).apps


def _cleanup(apps) -> None:
    models = (
        apps.get_model("operations", "SyntheticImportItem"),
        apps.get_model("accounts", "CustomerProfile"),
        apps.get_model("operations", "SyntheticImportBatch"),
        apps.get_model("accounts", "User"),
    )
    for model in models:
        model.objects.all()._raw_delete(connection.alias)


def _create_historical_user(User, *, username, role_code, employee_no=None):
    return User.objects.create(
        password="!",
        username=username,
        full_name="Synthetic migration fixture",
        role_code=role_code,
        employee_no=employee_no,
        is_staff=False,
        is_active=True,
        date_joined=timezone.now(),
    )


def test_existing_demo_profile_and_ledger_users_backfill_and_rollback():
    executor = MigrationExecutor(connection)
    executor.migrate(OLD_TARGETS)
    old_apps = executor.loader.project_state(OLD_TARGETS).apps
    User = old_apps.get_model("accounts", "User")
    CustomerProfile = old_apps.get_model("accounts", "CustomerProfile")
    SyntheticImportBatch = old_apps.get_model(
        "operations",
        "SyntheticImportBatch",
    )
    SyntheticImportItem = old_apps.get_model(
        "operations",
        "SyntheticImportItem",
    )
    restored = False

    try:
        demo_user = _create_historical_user(
            User,
            username="DEMO-CUSTOMER-001",
            role_code="CUSTOMER",
        )
        profile_user = _create_historical_user(
            User,
            username="CUS-PROFILE-SYN",
            role_code="CUSTOMER",
        )
        CustomerProfile.objects.create(
            user_id=profile_user.pk,
            customer_no="SYN-PROFILE-001",
            customer_name="Synthetic profile",
            is_synthetic=True,
        )
        ledger_user = _create_historical_user(
            User,
            username="SYN-LEDGER-OPERATOR",
            role_code="OPERATOR",
            employee_no="SYN-LEDGER-EMP-001",
        )
        batch = SyntheticImportBatch.objects.create(
            profile="db-full",
            status="COMPLETED",
            dataset_version="test-v1",
            mapping_version="test-v1",
            fixture_set_sha256="a" * 64,
            source_count=367,
            created_count=367,
            updated_count=0,
            unchanged_count=0,
            projected_count=0,
            completed_at=timezone.now(),
        )
        SyntheticImportItem.objects.create(
            batch_id=batch.pk,
            source_dataset="users",
            source_public_id=ledger_user.public_id,
            source_business_key=ledger_user.username,
            source_sha256="b" * 64,
            action="CREATED",
            target_model="accounts.User",
            target_public_id=ledger_user.public_id,
            target_business_key=ledger_user.username,
        )

        executor = MigrationExecutor(connection)
        executor.migrate(NEW_TARGETS)
        migrated_apps = executor.loader.project_state(NEW_TARGETS).apps
        MigratedUser = migrated_apps.get_model("accounts", "User")

        assert set(
            MigratedUser.objects.filter(is_synthetic=True).values_list(
                "username",
                flat=True,
            )
        ) == {
            demo_user.username,
            profile_user.username,
            ledger_user.username,
        }
        assert not MigratedUser.objects.filter(
            is_synthetic__isnull=True
        ).exists()

        _cleanup(migrated_apps)
        executor = MigrationExecutor(connection)
        executor.migrate(OLD_TARGETS)
        rolled_back_apps = executor.loader.project_state(OLD_TARGETS).apps
        field_names = {
            field.name
            for field in rolled_back_apps.get_model(
                "accounts",
                "User",
            )._meta.fields
        }
        assert "is_synthetic" not in field_names

        executor = MigrationExecutor(connection)
        executor.migrate(NEW_TARGETS)
        restored = True
    finally:
        if not restored:
            executor = MigrationExecutor(connection)
            is_applied = MIGRATE_TO in executor.loader.applied_migrations
            targets = NEW_TARGETS if is_applied else OLD_TARGETS
            apps = executor.loader.project_state(targets).apps
            _cleanup(apps)
            if is_applied:
                executor.migrate(OLD_TARGETS)
            MigrationExecutor(connection).migrate(NEW_TARGETS)


def test_unclassified_existing_user_aborts_without_partial_backfill():
    executor = MigrationExecutor(connection)
    executor.migrate(OLD_TARGETS)
    old_apps = executor.loader.project_state(OLD_TARGETS).apps
    User = old_apps.get_model("accounts", "User")
    _create_historical_user(
        User,
        username=f"UNCLASSIFIED-{uuid4().hex[:12].upper()}",
        role_code="CUSTOMER",
    )

    with pytest.raises(RuntimeError, match="unclassified_users=1"):
        MigrationExecutor(connection).migrate(NEW_TARGETS)

    executor = MigrationExecutor(connection)
    assert MIGRATE_TO not in executor.loader.applied_migrations
    _cleanup(executor.loader.project_state(OLD_TARGETS).apps)
    executor.migrate(NEW_TARGETS)
