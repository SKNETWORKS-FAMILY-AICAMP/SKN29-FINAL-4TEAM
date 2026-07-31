"""T-005 Evidence Wave ingestion batch Model and constraint tests."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from django.apps import apps
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from apps.evidence.models import IngestionBatch


pytestmark = pytest.mark.django_db


def create_batch(sequence: int = 1, **overrides) -> IngestionBatch:
    values = {
        "batch_no": f"INGESTION-{sequence:03d}",
        "source_type_code": IngestionBatch.SourceType.LOCAL_FILE,
        "idempotency_key": f"ingestion-idempotency-{sequence:03d}",
        "correlation_id": uuid4(),
        "pipeline_version": "data-pipeline-v1",
    }
    values.update(overrides)
    return IngestionBatch.objects.create(**values)


def test_ingestion_batch_uses_target_identifier_policy_and_defaults():
    batch = create_batch()

    assert isinstance(batch.pk, int)
    assert isinstance(batch.public_id, UUID)
    assert batch._meta.db_table == "knowledge_ingestion_batch"
    assert batch.dataset_scope_code == IngestionBatch.DatasetScope.MVP
    assert batch.status_code == IngestionBatch.Status.QUEUED
    assert batch.total_count == 0
    assert batch.success_count == 0
    assert batch.failure_count == 0


def test_ingestion_batch_is_exported_and_runtime_registered():
    config = apps.get_app_config("evidence")

    assert config.name == "apps.evidence"
    assert config.get_model("IngestionBatch") is IngestionBatch
    assert IngestionBatch._meta.app_label == "evidence"


def test_started_by_is_nullable_protected_accounts_fk():
    field = IngestionBatch._meta.get_field("started_by")

    assert field.remote_field.model._meta.label == "accounts.User"
    assert field.remote_field.on_delete is models.PROTECT
    assert field.db_column == "started_by_id"
    assert field.db_index is False
    assert field.null is True


def test_ingestion_batch_contract_indexes_and_constraints_are_declared():
    indexes = {
        index.name: tuple(index.fields)
        for index in IngestionBatch._meta.indexes
    }
    constraints = {
        constraint.name: constraint
        for constraint in IngestionBatch._meta.constraints
    }

    assert indexes == {
        "ix_ingestion_batch_status": (
            "status_code",
            "-created_at",
        ),
        "ix_ingestion_batch_correlation": ("correlation_id",),
    }
    assert set(constraints) == {
        "ux_ingestion_batch_no",
        "ux_ingestion_batch_idempotency",
        "ux_ingestion_batch_id_scope",
        "ck_ingestion_counts",
        "ck_ingestion_time_order",
        "ck_ingestion_terminal",
        "ck_ingestion_error_summary",
        "ck_knowledge_ingestion_batch_dataset_scope_code_allowed",
        "ck_knowledge_ingestion_batch_source_type_code_allowed",
        "ck_knowledge_ingestion_batch_status_code_allowed",
    }


def test_ingestion_batch_code_sets_are_database_constrained():
    with pytest.raises(IntegrityError), transaction.atomic():
        create_batch(
            dataset_scope_code="UNSUPPORTED",
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_batch(
            sequence=2,
            source_type_code="DATABASE",
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_batch(
            sequence=3,
            status_code="UNKNOWN",
        )


def test_ingestion_batch_counts_are_database_constrained():
    with pytest.raises(IntegrityError), transaction.atomic():
        create_batch(
            total_count=1,
            success_count=1,
            failure_count=1,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_batch(
            sequence=2,
            total_count=-1,
        )


def test_ingestion_batch_lifecycle_is_database_constrained():
    now = timezone.now()

    with pytest.raises(IntegrityError), transaction.atomic():
        create_batch(
            status_code=IngestionBatch.Status.RUNNING,
            started_at=None,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_batch(
            sequence=2,
            status_code=IngestionBatch.Status.SUCCEEDED,
            started_at=now,
            completed_at=now - timedelta(seconds=1),
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_batch(
            sequence=3,
            status_code=IngestionBatch.Status.PARTIAL,
            started_at=now,
            completed_at=now,
            total_count=2,
            success_count=1,
            failure_count=1,
            error_summary=None,
        )


def test_ingestion_batch_accepts_valid_terminal_states():
    now = timezone.now()
    batch = create_batch(
        status_code=IngestionBatch.Status.SUCCEEDED,
        started_at=now,
        completed_at=now + timedelta(seconds=1),
        total_count=2,
        success_count=2,
        failure_count=0,
    )

    assert batch.status_code == IngestionBatch.Status.SUCCEEDED


def test_ingestion_batch_business_keys_are_unique():
    batch = create_batch()

    with pytest.raises(IntegrityError), transaction.atomic():
        create_batch(
            sequence=2,
            batch_no=batch.batch_no,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_batch(
            sequence=3,
            idempotency_key=batch.idempotency_key,
        )
