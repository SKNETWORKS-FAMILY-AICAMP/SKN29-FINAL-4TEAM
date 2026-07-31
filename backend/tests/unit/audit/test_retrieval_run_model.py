"""T-005 Wave 2A retrieval run model and constraint tests."""

from __future__ import annotations

import importlib
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AIRetrievalRun, AIRun
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db


def create_inquiry(sequence: int) -> Inquiry:
    user = User.objects.create_user(
        username=f"RETRIEVAL-CUSTOMER-{sequence:03d}",
        password=None,
        full_name=f"Retrieval customer {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    customer = CustomerProfile.objects.create(
        user=user,
        customer_no=f"RETRIEVAL-CUS-{sequence:03d}",
        customer_name=f"Retrieval customer {sequence}",
    )
    product = ProductModel.objects.create(
        model_code=f"RETRIEVAL-PMD-{sequence:03d}",
        model_name=f"Retrieval product {sequence}",
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"RETRIEVAL-SUB-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"RETRIEVAL-SERIAL-{sequence:03d}",
        started_on=date(2026, 7, 1),
    )
    return Inquiry.objects.create(
        subscription=subscription,
        initiated_by=user,
        channel_code=Inquiry.Channel.WEB,
        raw_text="Synthetic retrieval test inquiry.",
    )


def create_ai_run(
    sequence: int,
    *,
    inquiry: Inquiry | None = None,
) -> AIRun:
    return AIRun.objects.create(
        inquiry=inquiry or create_inquiry(sequence),
        task_type_code=AIRun.TaskType.RETRIEVE_EVIDENCE,
        response_schema_version="1.0.0",
        input_payload={"query": "water flow issue"},
        input_sha256="a" * 64,
        idempotency_key=f"retrieval-ai-run-{sequence:03d}",
        correlation_id=uuid4(),
    )


def retrieval_values(sequence: int, **overrides):
    ai_run = overrides.pop("ai_run", None)
    if ai_run is None:
        ai_run = create_ai_run(sequence)
    values = {
        "ai_run": ai_run,
        "inquiry": ai_run.inquiry,
        "query_text": "WPU JAC104D water flow issue",
        "query_sha256": "b" * 64,
        "retrieval_config_version": "exact-cosine-v1",
        "correlation_id": ai_run.correlation_id,
    }
    values.update(overrides)
    return values


def test_retrieval_run_uses_active_identifiers_and_defaults():
    run = AIRetrievalRun.objects.create(**retrieval_values(1))

    assert isinstance(run.pk, int)
    assert isinstance(run.public_id, UUID)
    assert run._meta.db_table == "aiops_retrieval_run"
    assert run.ai_run.retrieval_runs.get() == run
    assert run.inquiry.retrieval_runs.get() == run
    assert run.filter_payload == {}
    assert run.retrieval_config == {}
    assert run.top_k == 5
    assert run.status_code == AIRetrievalRun.Status.QUEUED


def test_retrieval_run_declares_contract_indexes_and_constraints():
    constraint_names = {
        constraint.name
        for constraint in AIRetrievalRun._meta.constraints
    }
    indexes = {
        index.name: tuple(index.fields)
        for index in AIRetrievalRun._meta.indexes
    }

    assert constraint_names == {
        "ux_retrieval_id_ai_inquiry",
        "ck_retrieval_top_k",
        "ck_retrieval_no_evidence",
        "ck_retrieval_time_order",
        "ck_retrieval_terminal",
        "ck_retrieval_query_hash",
        "ck_retrieval_json_objects",
        "ck_retrieval_embedding_context",
        "ck_retrieval_failure",
        "ck_retrieval_latency",
        "ck_aiops_retrieval_run_distance_metric_code_allowed",
        "ck_aiops_retrieval_run_status_code_allowed",
    }
    assert indexes == {
        "ix_retrieval_ai_run": ("ai_run", "inquiry"),
        "ix_retrieval_inquiry": ("inquiry", "-created_at"),
        "ix_retrieval_status": ("status_code", "created_at"),
        "ix_retrieval_correlation": ("correlation_id",),
    }


def test_retrieval_run_accepts_valid_exact_cosine_success():
    started_at = timezone.now()
    run = AIRetrievalRun.objects.create(
        **retrieval_values(
            2,
            embedding_model="BAAI/bge-m3",
            embedding_model_version="upstream-1024-v1",
            distance_metric_code=(
                AIRetrievalRun.DistanceMetric.COSINE
            ),
            status_code=AIRetrievalRun.Status.SUCCEEDED,
            started_at=started_at,
            completed_at=started_at + timedelta(milliseconds=5),
            latency_ms=5,
        )
    )

    assert run.distance_metric_code == "COSINE"
    assert run.top_k == 5


@pytest.mark.parametrize(
    ("sequence", "overrides"),
    [
        (10, {"top_k": 0}),
        (11, {"top_k": 101}),
        (12, {"query_sha256": "not-a-sha256"}),
        (13, {"status_code": "UNKNOWN"}),
        (
            14,
            {
                "embedding_model": "BAAI/bge-m3",
                "embedding_model_version": "v1",
                "distance_metric_code": "UNKNOWN",
            },
        ),
        (15, {"filter_payload": []}),
        (16, {"retrieval_config": []}),
        (17, {"embedding_model": "BAAI/bge-m3"}),
        (18, {"latency_ms": -1}),
        (
            19,
            {
                "status_code": AIRetrievalRun.Status.NO_EVIDENCE,
                "started_at": timezone.now(),
                "completed_at": timezone.now(),
            },
        ),
        (
            20,
            {
                "status_code": AIRetrievalRun.Status.FAILED,
                "started_at": timezone.now(),
                "completed_at": timezone.now(),
            },
        ),
        (21, {"status_code": AIRetrievalRun.Status.RUNNING}),
        (
            22,
            {
                "status_code": AIRetrievalRun.Status.SUCCEEDED,
                "started_at": timezone.now(),
            },
        ),
        (
            23,
            {
                "status_code": AIRetrievalRun.Status.SUCCEEDED,
                "started_at": timezone.now(),
                "completed_at": (
                    timezone.now() - timedelta(minutes=1)
                ),
            },
        ),
    ],
)
def test_retrieval_database_checks_reject_contract_mismatches(
    sequence,
    overrides,
):
    with pytest.raises(IntegrityError), transaction.atomic():
        AIRetrievalRun.objects.create(
            **retrieval_values(sequence, **overrides)
        )


def test_retrieval_model_validation_rejects_parent_context_mismatch():
    ai_run = create_ai_run(30)
    other_inquiry = create_inquiry(31)
    run = AIRetrievalRun(
        **retrieval_values(
            32,
            ai_run=ai_run,
            inquiry=other_inquiry,
            correlation_id=uuid4(),
        )
    )

    with pytest.raises(ValidationError) as exc_info:
        run.full_clean()

    assert set(exc_info.value.message_dict) >= {
        "inquiry",
        "correlation_id",
    }


def test_sqlite_composite_context_trigger_rejects_child_mismatch():
    ai_run = create_ai_run(40)
    other_inquiry = create_inquiry(41)

    with pytest.raises(IntegrityError), transaction.atomic():
        AIRetrievalRun.objects.create(
            **retrieval_values(
                42,
                ai_run=ai_run,
                inquiry=other_inquiry,
            )
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        AIRetrievalRun.objects.create(
            **retrieval_values(
                43,
                ai_run=ai_run,
                correlation_id=uuid4(),
            )
        )


def test_sqlite_composite_context_trigger_rejects_parent_change():
    run = AIRetrievalRun.objects.create(**retrieval_values(50))

    with pytest.raises(IntegrityError), transaction.atomic():
        AIRun.objects.filter(pk=run.ai_run_id).update(
            correlation_id=uuid4()
        )


def test_retrieval_parent_deletion_is_protected():
    run = AIRetrievalRun.objects.create(**retrieval_values(60))

    with pytest.raises(ProtectedError):
        run.ai_run.delete()
    with pytest.raises(ProtectedError):
        run.inquiry.delete()


def test_composite_context_migration_matches_both_databases():
    migration_module = importlib.import_module(
        "apps.audit.migrations.0003_airetrievalrun"
    )

    postgresql_statements: list[str] = []
    postgresql_editor = SimpleNamespace(
        connection=SimpleNamespace(vendor="postgresql"),
        execute=postgresql_statements.append,
    )
    migration_module.add_retrieval_context_fk(
        None,
        postgresql_editor,
    )
    postgresql_sql = " ".join(
        postgresql_statements[0].split()
    )

    assert (
        "ADD CONSTRAINT fk_retrieval_ai_run_context"
        in postgresql_sql
    )
    assert (
        "FOREIGN KEY (ai_run_id, inquiry_id, correlation_id)"
        in postgresql_sql
    )
    assert (
        "REFERENCES aiops_ai_run "
        "(id, inquiry_id, correlation_id)"
        in postgresql_sql
    )
    assert "MATCH SIMPLE" in postgresql_sql
    assert "ON DELETE RESTRICT" in postgresql_sql

    sqlite_statements: list[str] = []
    sqlite_editor = SimpleNamespace(
        connection=SimpleNamespace(vendor="sqlite"),
        execute=sqlite_statements.append,
    )
    migration_module.add_retrieval_context_fk(
        None,
        sqlite_editor,
    )

    assert len(sqlite_statements) == 3
    assert all(
        "CREATE TRIGGER" in statement
        for statement in sqlite_statements
    )
    assert "BEFORE INSERT" in sqlite_statements[0]
    assert "BEFORE UPDATE" in sqlite_statements[1]
    assert "ON aiops_ai_run" in sqlite_statements[2]

    postgresql_reverse: list[str] = []
    migration_module.remove_retrieval_context_fk(
        None,
        SimpleNamespace(
            connection=SimpleNamespace(vendor="postgresql"),
            execute=postgresql_reverse.append,
        ),
    )
    assert (
        "DROP CONSTRAINT IF EXISTS "
        "fk_retrieval_ai_run_context"
        in " ".join(postgresql_reverse[0].split())
    )

    sqlite_reverse: list[str] = []
    migration_module.remove_retrieval_context_fk(
        None,
        SimpleNamespace(
            connection=SimpleNamespace(vendor="sqlite"),
            execute=sqlite_reverse.append,
        ),
    )
    assert len(sqlite_reverse) == 3
    assert all(
        "DROP TRIGGER IF EXISTS" in statement
        for statement in sqlite_reverse
    )
