"""End-to-end SQLite tests for the canonical synthetic handoff importer."""

from __future__ import annotations

import json
from collections import Counter
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.utils.dateparse import parse_datetime

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AuditEvent
from apps.care.models import CareRecord
from apps.consultations.models import Consultation
from apps.inquiries.models import (
    FollowupConfirmation,
    Inquiry,
    SymptomEntry,
)
from apps.operations.models import (
    SyntheticImportBatch,
    SyntheticImportItem,
)
from apps.operations.repositories import SyntheticImportConflict
from apps.operations.services import SyntheticHandoffImportService
from apps.operations.services.operations_service import (
    EXPECTED_FIXTURE_COUNTS,
    EXPECTED_FULL_COUNTS,
)
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.visits.models import Visit
from apps.workflow.models import TransitionHistory


DOMAIN_MODELS = (
    User,
    CustomerProfile,
    ProductModel,
    CustomerSubscription,
    Inquiry,
    SymptomEntry,
    Consultation,
    Visit,
    FollowupConfirmation,
    CareRecord,
    TransitionHistory,
    AuditEvent,
    SyntheticImportBatch,
    SyntheticImportItem,
)


def test_physical_fixture_products_are_filtered_by_database_profiles():
    service = SyntheticHandoffImportService()

    all_rows = service._load_fixture_set()
    actual_counts = {
        dataset: len(rows) for dataset, rows in all_rows.items()
    }

    assert actual_counts == EXPECTED_FIXTURE_COUNTS
    assert sum(actual_counts.values()) == 369
    assert {
        row["product_code"] for row in all_rows["products"]
    } == {
        "WPUJAC104DWH",
        "WPUIAC425SNW",
        "WPUIAC606SNW",
    }

    for profile in ("db-smoke", "db-full"):
        selected = service._select_rows(profile, all_rows)
        assert [
            row["product_code"] for row in selected["products"]
        ] == ["WPUJAC104DWH"]


@pytest.mark.django_db
def test_dry_run_command_emits_one_json_document_and_writes_nothing():
    output = StringIO()

    returned = call_command(
        "import_synthetic_handoff",
        profile="smoke",
        dry_run=True,
        stdout=output,
    )

    lines = [
        line for line in output.getvalue().splitlines() if line.strip()
    ]
    assert len(lines) == 1
    assert returned == lines[0]
    payload = json.loads(lines[0])
    assert payload["profile"] == "db-smoke"
    assert payload["dry_run"] is True
    assert payload["source_count"] == 37
    assert payload["created_count"] == 31
    assert payload["updated_count"] == 0
    assert payload["projected_count"] == 6
    assert payload["batch_public_id"] is None
    assert payload["batch_code"] is None
    assert all(model.objects.count() == 0 for model in DOMAIN_MODELS)


@pytest.mark.django_db
def test_smoke_import_is_idempotent_and_only_repairs_dirty_fields():
    service = SyntheticHandoffImportService()

    first = service.run(profile="db-smoke")
    second = service.run(profile="smoke")

    assert (
        first.source_count,
        first.created_count,
        first.updated_count,
        first.unchanged_count,
        first.projected_count,
    ) == (37, 31, 0, 0, 6)
    assert (
        second.source_count,
        second.created_count,
        second.updated_count,
        second.unchanged_count,
        second.projected_count,
    ) == (37, 0, 0, 31, 6)
    assert first.fixture_set_sha256 == second.fixture_set_sha256
    assert len(first.fixture_set_sha256) == 64

    assert User.objects.count() == 8
    assert User.objects.filter(is_synthetic=True).count() == 8
    assert CustomerProfile.objects.count() == 6
    assert ProductModel.objects.count() == 1
    assert CustomerSubscription.objects.count() == 6
    assert Inquiry.objects.count() == 6
    assert SymptomEntry.objects.count() == 6
    assert Consultation.objects.count() == 3
    assert Visit.objects.count() == 1
    assert SyntheticImportBatch.objects.count() == 2
    assert SyntheticImportItem.objects.count() == 74

    user = User.objects.get(username="CUS-0001")
    source_name = user.full_name
    User.objects.filter(pk=user.pk).update(full_name="dirty-value")

    preview = service.run(profile="db-smoke", dry_run=True)
    assert (
        preview.created_count,
        preview.updated_count,
        preview.unchanged_count,
        preview.projected_count,
    ) == (0, 1, 30, 6)
    assert User.objects.get(pk=user.pk).full_name == "dirty-value"
    assert SyntheticImportBatch.objects.count() == 2
    assert SyntheticImportItem.objects.count() == 74

    repair = service.run(profile="db-smoke")
    stable = service.run(profile="db-smoke")

    assert (
        repair.created_count,
        repair.updated_count,
        repair.unchanged_count,
        repair.projected_count,
    ) == (0, 1, 30, 6)
    assert User.objects.get(pk=user.pk).full_name == source_name
    assert (
        stable.created_count,
        stable.updated_count,
        stable.unchanged_count,
        stable.projected_count,
    ) == (0, 0, 31, 6)


@pytest.mark.django_db
def test_full_import_preserves_provenance_and_history_invariants():
    service = SyntheticHandoffImportService()

    first = service.run(profile="db-full")
    second = service.run(profile="full")

    assert (
        first.source_count,
        first.created_count,
        first.updated_count,
        first.unchanged_count,
        first.projected_count,
    ) == (367, 355, 0, 0, 12)
    assert (
        second.source_count,
        second.created_count,
        second.updated_count,
        second.unchanged_count,
        second.projected_count,
    ) == (367, 0, 0, 355, 12)
    assert first.verification == {
        "source_items": 367,
        "projection_checks": 12,
        "aggregate_checks": 26,
        "audit_history_checks": 125,
    }

    assert User.objects.count() == 16
    assert User.objects.filter(is_synthetic=True).count() == 16
    assert CustomerProfile.objects.count() == 12
    assert ProductModel.objects.count() == 1
    assert list(
        ProductModel.objects.values_list("model_code", flat=True)
    ) == ["WPUJAC104DWH"]
    assert not ProductModel.objects.filter(
        model_code__in=("WPUIAC425SNW", "WPUIAC606SNW")
    ).exists()
    assert CustomerSubscription.objects.count() == 12
    assert Inquiry.objects.count() == 22
    assert SymptomEntry.objects.count() == 22
    assert Consultation.objects.count() == 12
    assert Visit.objects.count() == 4
    assert FollowupConfirmation.objects.count() == 1
    assert CareRecord.objects.count() == 25
    assert TransitionHistory.objects.count() == 125
    assert AuditEvent.objects.count() == 125

    first_batch = SyntheticImportBatch.objects.order_by(
        "created_at"
    ).first()
    assert first_batch is not None
    assert first_batch.dataset_version == first.dataset_version
    assert first_batch.mapping_version == first.mapping_version
    assert first_batch.fixture_set_sha256 == first.fixture_set_sha256
    dataset_counts = Counter(
        first_batch.items.values_list("source_dataset", flat=True)
    )
    assert dataset_counts == Counter(EXPECTED_FULL_COUNTS)
    assert Counter(
        first_batch.items.values_list("action", flat=True)
    ) == Counter({"CREATED": 355, "PROJECTED": 12})

    customer = User.objects.get(username="CUS-0001")
    assert customer.has_usable_password() is False
    assert customer.employee_no is None
    assert customer.date_joined == parse_datetime(
        "2026-07-29T00:00:00+09:00"
    )
    assert customer.created_at == parse_datetime(
        "2026-07-29T00:00:00+09:00"
    )
    assert all(
        user.employee_no == user.username
        for user in User.objects.exclude(role_code="CUSTOMER")
    )
    assert all(
        user.has_usable_password() is False
        for user in User.objects.all()
    )

    inquiry = Inquiry.objects.get(
        inquiry_code="INQ-20260701-0001"
    )
    assert inquiry.created_at == parse_datetime(
        "2026-07-01T15:00:00+09:00"
    )
    assert inquiry.updated_at == parse_datetime(
        "2026-07-01T15:30:00+09:00"
    )
    assert inquiry.channel_code is None
    assert all(
        type(value) is not int
        for symptom in SymptomEntry.objects.all()
        for value in symptom.structured_payload.values()
    )

    item_fields = {
        field.name for field in SyntheticImportItem._meta.fields
    }
    assert "source_fixture_id" not in item_fields
    assert "target_fixture_id" not in item_fields

    for aggregate in Inquiry.objects.all():
        latest = aggregate.transition_history.order_by(
            "-state_version"
        ).first()
        assert latest is not None
        assert aggregate.state_version == latest.state_version
        assert aggregate.status_code == latest.to_state

    for aggregate in Visit.objects.all():
        latest = aggregate.transition_history.order_by(
            "-state_version"
        ).first()
        assert latest is not None
        assert aggregate.state_version == latest.state_version
        assert aggregate.status == latest.to_state

    for audit in AuditEvent.objects.select_related("transition"):
        history = audit.transition
        assert audit.event_code == history.event_code
        assert audit.state_version == history.state_version
        assert audit.actor_id == history.actor_id
        assert audit.idempotency_key == history.idempotency_key
        assert audit.correlation_id == history.correlation_id
        assert audit.occurred_at == history.changed_at


@pytest.mark.django_db
def test_demo_seed_bundle_and_full_handoff_import_do_not_collide():
    """Demo seed와 canonical handoff를 같은 DB에서 반복 실행할 수 있다."""

    seed_commands = (
        "seed_common_codes",
        "seed_demo_accounts",
        "seed_demo_products",
        "seed_demo_subscriptions",
        "seed_demo_care_records",
    )
    for _ in range(2):
        for command in seed_commands:
            call_command(command, verbosity=0)

    service = SyntheticHandoffImportService()
    first = service.run(profile="db-full")
    second = service.run(profile="db-full")

    assert (
        first.created_count,
        first.updated_count,
        first.unchanged_count,
        first.projected_count,
    ) == (355, 0, 0, 12)
    assert (
        second.created_count,
        second.updated_count,
        second.unchanged_count,
        second.projected_count,
    ) == (0, 0, 355, 12)

    assert User.objects.count() == 20
    assert CustomerProfile.objects.count() == 13
    assert ProductModel.objects.count() == 2
    assert CustomerSubscription.objects.count() == 13
    assert CareRecord.objects.count() == 28
    assert CustomerProfile.objects.filter(
        customer_no="DEMO-CUSTOMER-001"
    ).exists()
    assert CustomerProfile.objects.filter(
        customer_no="SYN-CUSTOMER-001"
    ).exists()
    assert CustomerSubscription.objects.filter(
        serial_no="DEMO-JAC104D-0001"
    ).exists()
    assert CustomerSubscription.objects.filter(
        serial_no="SYN-JAC104D-0001"
    ).exists()


@pytest.mark.django_db
def test_identifier_conflict_rolls_back_the_whole_import():
    ProductModel.objects.create(
        public_id=uuid4(),
        model_code="WPUJAC104DWH",
        model_name="conflicting existing row",
    )

    with pytest.raises(
        SyntheticImportConflict,
        match="public UUID mismatch",
    ):
        SyntheticHandoffImportService().run(profile="db-smoke")

    assert ProductModel.objects.count() == 1
    assert User.objects.count() == 0
    assert CustomerProfile.objects.count() == 0
    assert SyntheticImportBatch.objects.count() == 0
    assert SyntheticImportItem.objects.count() == 0
