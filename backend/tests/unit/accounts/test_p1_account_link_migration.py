"""P1-A account-link Migration Backfill·Rollback 경계 검증."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


pytestmark = pytest.mark.django_db(transaction=True)

MIGRATE_FROM = ("accounts", "0005_account_lifecycle_and_audit")
MIGRATE_TO = ("accounts", "0006_p1_account_link_foundation")
MIGRATE_LATEST = ("accounts", "0009_approved_test_contract_email")


def _cleanup(apps) -> None:
    for model_name in (
        "P1AuthEmailOutbox",
        "P1AuthTicket",
        "P1AuthOtpChallenge",
        "P1AuthOperationReceipt",
        "P1AccountConsent",
        "P1AuthIdempotencyLock",
        "P1AuthLoginRateBucket",
        "P1AuthChallengeRateBucket",
        "P1AuthRateLimitEvent",
        "ContractEmailContact",
        "CustomerAccountLink",
        "CustomerProfile",
        "User",
    ):
        try:
            model = apps.get_model("accounts", model_name)
        except LookupError:
            continue
        model.objects.all()._raw_delete(connection.alias)


def test_forward_backfills_existing_owner_and_allows_pre_signup_customer():
    executor = MigrationExecutor(connection)
    executor.migrate([MIGRATE_FROM])
    old_apps = executor.loader.project_state([MIGRATE_FROM]).apps
    OldUser = old_apps.get_model("accounts", "User")
    OldCustomer = old_apps.get_model("accounts", "CustomerProfile")
    restored = False

    try:
        user = OldUser.objects.create(
            password="!",
            public_id=uuid4(),
            username="SYN-P1-MIGRATION-CUSTOMER",
            full_name="Synthetic migration customer",
            role_code="CUSTOMER",
            is_staff=False,
            is_active=True,
            is_synthetic=True,
            auth_version=1,
            date_joined=timezone.now(),
        )
        customer = OldCustomer.objects.create(
            public_id=uuid4(),
            user_id=user.pk,
            customer_no="SYN-P1-MIGRATION-CUSTOMER",
            customer_name="Synthetic migration customer",
            is_synthetic=True,
        )

        executor = MigrationExecutor(connection)
        executor.migrate([MIGRATE_TO])
        migrated_apps = executor.loader.project_state([MIGRATE_TO]).apps
        MigratedCustomer = migrated_apps.get_model(
            "accounts",
            "CustomerProfile",
        )
        Link = migrated_apps.get_model("accounts", "CustomerAccountLink")

        link = Link.objects.get(customer_id=customer.pk)
        assert link.user_id == user.pk
        assert link.is_active is True
        assert link.link_reason == "LEGACY_BACKFILL"
        assert Link.objects.count() == 1
        pre_signup = MigratedCustomer.objects.create(
            public_id=uuid4(),
            user_id=None,
            customer_no="SYN-P1-MIGRATION-PRE-SIGNUP",
            customer_name="Synthetic pre-signup customer",
            is_synthetic=True,
        )
        assert pre_signup.user_id is None
        assert not Link.objects.filter(customer_id=pre_signup.pk).exists()

        pre_signup.delete()
        _cleanup(migrated_apps)
        MigrationExecutor(connection).migrate([MIGRATE_FROM])
        rolled_back_apps = MigrationExecutor(connection).loader.project_state(
            [MIGRATE_FROM]
        ).apps
        customer_field = rolled_back_apps.get_model(
            "accounts",
            "CustomerProfile",
        )._meta.get_field("user")
        assert customer_field.null is False
        with pytest.raises(LookupError):
            rolled_back_apps.get_model("accounts", "CustomerAccountLink")

        MigrationExecutor(connection).migrate([MIGRATE_LATEST])
        restored = True
    finally:
        if not restored:
            executor = MigrationExecutor(connection)
            applied = MIGRATE_TO in executor.loader.applied_migrations
            target = MIGRATE_TO if applied else MIGRATE_FROM
            apps = executor.loader.project_state([target]).apps
            _cleanup(apps)
            if applied:
                executor.migrate([MIGRATE_FROM])
            MigrationExecutor(connection).migrate([MIGRATE_LATEST])


def test_forward_rejects_non_synthetic_owner_before_any_link_is_created():
    executor = MigrationExecutor(connection)
    executor.migrate([MIGRATE_FROM])
    old_apps = executor.loader.project_state([MIGRATE_FROM]).apps
    OldUser = old_apps.get_model("accounts", "User")
    OldCustomer = old_apps.get_model("accounts", "CustomerProfile")
    restored = False

    try:
        for sequence, is_synthetic in ((1, True), (2, False)):
            user = OldUser.objects.create(
                password="!",
                public_id=uuid4(),
                username=f"SYN-P1-UNSAFE-{sequence}",
                full_name=f"Synthetic migration owner {sequence}",
                role_code="CUSTOMER",
                is_staff=False,
                is_active=True,
                is_synthetic=is_synthetic,
                auth_version=1,
                date_joined=timezone.now(),
            )
            OldCustomer.objects.create(
                public_id=uuid4(),
                user_id=user.pk,
                customer_no=f"SYN-P1-UNSAFE-{sequence}",
                customer_name=f"Synthetic migration customer {sequence}",
                is_synthetic=True,
            )

        with pytest.raises(RuntimeError, match="active synthetic customer"):
            MigrationExecutor(connection).migrate([MIGRATE_TO])

        assert "accounts_customer_account_link" not in connection.introspection.table_names()
        assert OldCustomer.objects.count() == 2
        _cleanup(old_apps)
        MigrationExecutor(connection).migrate([MIGRATE_LATEST])
        restored = True
    finally:
        if not restored:
            executor = MigrationExecutor(connection)
            target = (
                MIGRATE_TO
                if MIGRATE_TO in executor.loader.applied_migrations
                else MIGRATE_FROM
            )
            apps = executor.loader.project_state([target]).apps
            _cleanup(apps)
            MigrationExecutor(connection).migrate([MIGRATE_LATEST])


def test_each_p1_migration_blocks_reverse_while_its_owned_data_exists():
    executor = MigrationExecutor(connection)
    executor.migrate([MIGRATE_LATEST])
    restored = False

    try:
        latest_apps = executor.loader.project_state([MIGRATE_LATEST]).apps
        Challenge = latest_apps.get_model("accounts", "P1AuthOtpChallenge")
        Outbox = latest_apps.get_model("accounts", "P1AuthEmailOutbox")
        challenge = Challenge.objects.create(
            purpose="SIGNUP",
            target_resolved=False,
            idempotency_key_hmac="a" * 64,
            request_fingerprint_hmac="b" * 64,
            otp_digest="c" * 64,
            expires_at=timezone.now() + timedelta(minutes=5),
            resend_not_before=timezone.now() + timedelta(minutes=1),
            max_failures=5,
        )
        Outbox.objects.create(
            challenge=challenge,
            encrypted_otp="",
            status="SUPPRESSED",
            last_error_code="TARGET_UNRESOLVED",
        )

        with pytest.raises(RuntimeError, match="0008 reverse"):
            MigrationExecutor(connection).migrate(
                [("accounts", "0007_p1_auth_runtime")]
            )
        assert Outbox.objects.count() == 1
        Outbox.objects.all()._raw_delete(connection.alias)
        Challenge.objects.all()._raw_delete(connection.alias)

        MigrationExecutor(connection).migrate(
            [("accounts", "0007_p1_auth_runtime")]
        )
        executor = MigrationExecutor(connection)
        auth_apps = executor.loader.project_state(
            [("accounts", "0007_p1_auth_runtime")]
        ).apps
        Bucket = auth_apps.get_model(
            "accounts", "P1AuthChallengeRateBucket"
        )
        Bucket.objects.create(
            purpose="SIGNUP",
            request_fingerprint_hmac="d" * 64,
        )

        with pytest.raises(RuntimeError, match="0007 reverse"):
            MigrationExecutor(connection).migrate([MIGRATE_TO])
        assert Bucket.objects.count() == 1
        Bucket.objects.all()._raw_delete(connection.alias)

        MigrationExecutor(connection).migrate([MIGRATE_TO])
        executor = MigrationExecutor(connection)
        foundation_apps = executor.loader.project_state([MIGRATE_TO]).apps
        Customer = foundation_apps.get_model("accounts", "CustomerProfile")
        pre_signup = Customer.objects.create(
            public_id=uuid4(),
            user_id=None,
            customer_no="SYN-P1-REVERSE-GUARD",
            customer_name="Synthetic reverse guard customer",
            is_synthetic=True,
        )

        with pytest.raises(RuntimeError, match="0006 reverse"):
            MigrationExecutor(connection).migrate([MIGRATE_FROM])
        assert Customer.objects.filter(pk=pre_signup.pk).exists()
        pre_signup.delete()

        MigrationExecutor(connection).migrate([MIGRATE_LATEST])
        restored = True
    finally:
        if not restored:
            executor = MigrationExecutor(connection)
            applied = executor.loader.applied_migrations
            target = next(
                (
                    candidate
                    for candidate in (MIGRATE_LATEST, MIGRATE_TO, MIGRATE_FROM)
                    if candidate in applied
                ),
                MIGRATE_FROM,
            )
            apps = executor.loader.project_state([target]).apps
            _cleanup(apps)
            MigrationExecutor(connection).migrate([MIGRATE_LATEST])
