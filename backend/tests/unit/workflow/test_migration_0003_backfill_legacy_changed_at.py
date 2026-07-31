"""Regression tests for the legacy workflow timestamp correction."""

from datetime import date, timedelta
from importlib import import_module
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.apps import apps as django_apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import TransitionHistory


pytestmark = pytest.mark.django_db


def create_inquiry(sequence: int) -> Inquiry:
    """Create the minimum isolated domain graph for one transition."""

    user = User.objects.create_user(
        username=f"WORKFLOW-MIGRATION-{sequence:03d}",
        password=None,
        full_name=f"Workflow migration user {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    customer = CustomerProfile.objects.create(
        user=user,
        customer_no=f"WORKFLOW-MIGRATION-CUS-{sequence:03d}",
        customer_name=f"Workflow migration customer {sequence}",
    )
    product = ProductModel.objects.create(
        model_code=f"WORKFLOW-MIGRATION-PMD-{sequence:03d}",
        model_name=f"Workflow migration product {sequence}",
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"WORKFLOW-MIGRATION-SUB-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"WORKFLOW-MIGRATION-SERIAL-{sequence:03d}",
        started_on=date(2026, 7, 1),
    )
    return Inquiry.objects.create(
        subscription=subscription,
        initiated_by=user,
        channel_code=Inquiry.Channel.WEB,
        raw_text="Workflow migration timestamp regression test.",
    )


def create_transition(sequence: int) -> TransitionHistory:
    """Create one valid initial-state transition."""

    inquiry = create_inquiry(sequence)
    return TransitionHistory.objects.create(
        inquiry=inquiry,
        actor=inquiry.initiated_by,
        event_code="START_INQUIRY",
        from_state=None,
        to_state=Inquiry.Status.DRAFT,
        state_version=1,
        correlation_id=uuid4(),
        idempotency_key=f"workflow-migration-{sequence}",
    )


def test_backfill_corrects_only_changed_at_after_created_at():
    migration = import_module(
        "apps.workflow.migrations."
        "0003_backfill_legacy_changed_at"
    )
    affected = create_transition(901)
    non_legacy_future = create_transition(902)
    legacy_past = create_transition(904)
    affected_future = affected.created_at + timedelta(days=1)
    non_legacy_future_value = (
        non_legacy_future.created_at + timedelta(days=1)
    )
    legacy_past_value = (
        legacy_past.created_at - timedelta(seconds=1)
    )

    TransitionHistory.objects.filter(pk=affected.pk).update(
        changed_at=affected_future,
        status_history_code=(
            f"HST-{affected.public_id.hex.upper()}"
        ),
    )
    TransitionHistory.objects.filter(pk=non_legacy_future.pk).update(
        changed_at=non_legacy_future_value,
    )
    TransitionHistory.objects.filter(pk=legacy_past.pk).update(
        changed_at=legacy_past_value,
        status_history_code=(
            f"HST-{legacy_past.public_id.hex.upper()}"
        ),
    )

    schema_editor = SimpleNamespace(
        connection=SimpleNamespace(alias="default"),
    )
    migration.backfill_legacy_changed_at(django_apps, schema_editor)
    migration.backfill_legacy_changed_at(django_apps, schema_editor)

    affected.refresh_from_db()
    non_legacy_future.refresh_from_db()
    legacy_past.refresh_from_db()
    assert affected.changed_at == affected.created_at
    assert non_legacy_future.changed_at == non_legacy_future_value
    assert legacy_past.changed_at == legacy_past_value


@pytest.mark.django_db(transaction=True)
def test_migration_executor_applies_0002_to_0003_transition():
    """Exercise the registered Migration operation, not only its function."""

    target_0002 = [("workflow", "0002_expand_transition_targets")]
    target_0003 = [("workflow", "0003_backfill_legacy_changed_at")]
    target_0004 = [("workflow", "0004_align_contract_status_history")]
    executor = MigrationExecutor(connection)
    executor.migrate(target_0002)
    history_0002 = executor.loader.project_state(
        target_0002
    ).apps.get_model("workflow", "TransitionHistory")
    inquiry = create_inquiry(903)
    affected = history_0002.objects.create(
        inquiry_id=inquiry.pk,
        actor_id=inquiry.initiated_by_id,
        event_code="START_INQUIRY",
        from_state=None,
        to_state=Inquiry.Status.DRAFT,
        state_version=1,
        correlation_id=uuid4(),
        idempotency_key="workflow-migration-903",
    )
    history_0002.objects.filter(pk=affected.pk).update(
        changed_at=affected.created_at + timedelta(days=1),
        status_history_code=(
            f"HST-{affected.public_id.hex.upper()}"
        ),
    )

    executor = MigrationExecutor(connection)
    executor.migrate(target_0003)
    history_0003 = executor.loader.project_state(
        target_0003
    ).apps.get_model("workflow", "TransitionHistory")
    migrated = history_0003.objects.get(pk=affected.pk)
    assert migrated.changed_at == migrated.created_at

    executor = MigrationExecutor(connection)
    executor.migrate(target_0002)
    history_0002 = executor.loader.project_state(
        target_0002
    ).apps.get_model("workflow", "TransitionHistory")
    rolled_back = history_0002.objects.get(pk=affected.pk)
    assert rolled_back.changed_at == rolled_back.created_at

    executor = MigrationExecutor(connection)
    executor.migrate(target_0003)
    history_0003 = executor.loader.project_state(
        target_0003
    ).apps.get_model("workflow", "TransitionHistory")
    reapplied = history_0003.objects.get(pk=affected.pk)
    assert reapplied.changed_at == reapplied.created_at

    executor = MigrationExecutor(connection)
    executor.migrate(target_0004)
