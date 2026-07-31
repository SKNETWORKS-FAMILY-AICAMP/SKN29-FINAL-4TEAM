"""T-005 Wave 2D handoff report schema and integrity tests."""

from __future__ import annotations

import importlib
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AIRun
from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.visits.models import HandoffReport, Visit


pytestmark = pytest.mark.django_db


def create_inquiry(sequence: int) -> Inquiry:
    customer_user = User.objects.create_user(
        username=f"HANDOFF-CUSTOMER-{sequence:03d}",
        password=None,
        full_name=f"Handoff customer {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    customer = CustomerProfile.objects.create(
        user=customer_user,
        customer_no=f"HANDOFF-CUS-{sequence:03d}",
        customer_name=f"Handoff customer {sequence}",
    )
    product = ProductModel.objects.create(
        model_code=f"HANDOFF-PMD-{sequence:03d}",
        model_name=f"Handoff product {sequence}",
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"HANDOFF-SUB-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"HANDOFF-SERIAL-{sequence:03d}",
        started_on=date(2026, 7, 1),
    )
    return Inquiry.objects.create(
        subscription=subscription,
        initiated_by=customer_user,
        channel_code=Inquiry.Channel.WEB,
        raw_text="A technician handoff is required.",
    )


def create_consultant(sequence: int) -> User:
    return User.objects.create_user(
        username=f"HANDOFF-CONSULTANT-{sequence:03d}",
        password=None,
        full_name=f"Handoff consultant {sequence}",
        role_code=User.Role.CONSULTANT,
        employee_no=f"HANDOFF-EMP-{sequence:03d}",
    )


def create_technician(sequence: int) -> User:
    return User.objects.create_user(
        username=f"HANDOFF-TECH-{sequence:03d}",
        password=None,
        full_name=f"Handoff technician {sequence}",
        role_code=User.Role.TECHNICIAN,
        employee_no=f"HANDOFF-TECH-EMP-{sequence:03d}",
    )


def create_consultation(
    sequence: int,
    *,
    inquiry: Inquiry | None = None,
    consultant: User | None = None,
) -> Consultation:
    target_inquiry = inquiry or create_inquiry(sequence)
    assigned = consultant or create_consultant(sequence)
    started_at = timezone.now()
    return Consultation.objects.create(
        consultation_code=f"HANDOFF-CONSULT-{sequence:03d}",
        inquiry=target_inquiry,
        sequence=1,
        consultant=assigned,
        status=Consultation.Status.COMPLETED,
        outcome=Consultation.Outcome.VISIT_REQUIRED,
        summary="Synthetic completed consultation.",
        state_version=4,
        idempotency_key=f"handoff-consult-{sequence:03d}",
        correlation_id=uuid4(),
        started_at=started_at,
        completed_at=started_at + timedelta(minutes=5),
        data_classification=(
            Consultation.DataClassification.SYNTHETIC
        ),
        created_at=started_at - timedelta(minutes=1),
    )


def create_ai_run(
    sequence: int,
    *,
    inquiry: Inquiry,
) -> AIRun:
    return AIRun.objects.create(
        inquiry=inquiry,
        task_type_code=AIRun.TaskType.DRAFT_HANDOFF,
        response_schema_version="1.0.0",
        input_payload={"inquiry": str(inquiry.public_id)},
        input_sha256="a" * 64,
        idempotency_key=f"handoff-ai-run-{sequence:03d}",
        correlation_id=uuid4(),
    )


def report_values(sequence: int, **overrides) -> dict:
    consultation = overrides.pop("consultation", None)
    if consultation is None:
        consultation = create_consultation(sequence)
    ai_run = overrides.pop("generated_by_ai_run", None)
    if ai_run is None:
        ai_run = create_ai_run(
            sequence,
            inquiry=consultation.inquiry,
        )
    values = {
        "inquiry": consultation.inquiry,
        "consultation": consultation,
        "report_status_code": "TEAM_REVIEW_PENDING",
        "product_summary": "WPU-JAC104D synthetic product.",
        "symptom_summary": "Synthetic low-flow symptom.",
        "action_summary": "Synthetic customer actions.",
        "risk_summary": "No immediate synthetic safety risk.",
        "evidence_summary": "Synthetic approved manual reference.",
        "priority_check_items": [
            {
                "order": 1,
                "item": "Inspect the inlet and filter.",
            }
        ],
        "ai_draft": "Synthetic AI draft.",
        "generated_by_ai_run": ai_run,
    }
    values.update(overrides)
    return values


def test_handoff_report_uses_active_identifiers_and_open_status():
    report = HandoffReport.objects.create(**report_values(1))

    assert isinstance(report.pk, int)
    assert isinstance(report.public_id, UUID)
    assert report._meta.db_table == "support_handoff_report"
    assert report.report_version == 1
    assert report.report_status_code == "TEAM_REVIEW_PENDING"
    assert report.consultation.handoff_reports.get() == report
    assert report.inquiry.handoff_reports.get() == report
    assert (
        report.generated_by_ai_run.generated_handoff_reports.get()
        == report
    )
    assert HandoffReport._meta.get_field(
        "report_status_code"
    ).choices is None
    with pytest.raises(FieldDoesNotExist):
        Visit._meta.get_field("handoff_report")


def test_handoff_report_declares_contract_indexes_and_constraints():
    constraint_names = {
        constraint.name
        for constraint in HandoffReport._meta.constraints
    }
    indexes = {
        index.name: tuple(index.fields)
        for index in HandoffReport._meta.indexes
    }

    assert constraint_names == {
        "ux_handoff_report_version",
        "ux_handoff_id_inquiry",
        "ck_handoff_report_version",
        "ck_handoff_status_nonempty",
        "ck_handoff_report_confirmation",
        "ck_handoff_priority_items_array",
    }
    assert indexes == {
        "ix_handoff_consultation": (
            "consultation",
            "inquiry",
        ),
        "ix_handoff_status": (
            "report_status_code",
            "created_at",
        ),
        "ix_handoff_ai_run": (
            "generated_by_ai_run",
            "inquiry",
        ),
    }


def test_handoff_report_accepts_structurally_confirmed_content():
    values = report_values(2)
    consultant = values["consultation"].consultant
    report = HandoffReport.objects.create(
        **values,
        consultant_final="Consultant-reviewed handoff.",
        confirmed_by=consultant,
        confirmed_at=timezone.now(),
    )

    assert report.confirmed_by == consultant
    assert (
        consultant.confirmed_handoff_reports.get()
        == report
    )


def test_handoff_report_version_is_unique_within_inquiry():
    values = report_values(3)
    HandoffReport.objects.create(**values)

    with pytest.raises(IntegrityError), transaction.atomic():
        HandoffReport.objects.create(**values)


@pytest.mark.parametrize(
    ("sequence", "overrides"),
    [
        (10, {"report_version": 0}),
        (11, {"report_status_code": ""}),
        (12, {"priority_check_items": {}}),
        (
            13,
            {
                "confirmed_by": "USE_CONSULTANT",
            },
        ),
        (
            14,
            {
                "confirmed_at": "USE_NOW",
            },
        ),
        (
            15,
            {
                "confirmed_by": "USE_CONSULTANT",
                "confirmed_at": "USE_NOW",
                "consultant_final": None,
            },
        ),
    ],
)
def test_handoff_database_checks_reject_invalid_records(
    sequence,
    overrides,
):
    values = report_values(sequence)
    normalized = dict(overrides)
    if normalized.get("confirmed_by") == "USE_CONSULTANT":
        normalized["confirmed_by"] = values[
            "consultation"
        ].consultant
    if normalized.get("confirmed_at") == "USE_NOW":
        normalized["confirmed_at"] = timezone.now()
    values.update(normalized)

    with pytest.raises(IntegrityError), transaction.atomic():
        HandoffReport.objects.create(**values)


def test_handoff_clean_rejects_context_role_json_and_blank_status():
    consultation = create_consultation(20)
    other_inquiry = create_inquiry(21)
    other_ai_run = create_ai_run(21, inquiry=other_inquiry)
    technician = create_technician(20)
    report = HandoffReport(
        **report_values(
            22,
            consultation=consultation,
            inquiry=other_inquiry,
            generated_by_ai_run=other_ai_run,
            confirmed_by=technician,
            confirmed_at=timezone.now(),
            consultant_final="Invalid reviewer.",
            priority_check_items={},
            report_status_code=" ",
        )
    )

    with pytest.raises(ValidationError) as exc_info:
        report.full_clean()

    assert set(exc_info.value.message_dict) >= {
        "consultation",
        "confirmed_by",
        "priority_check_items",
        "report_status_code",
    }


def test_sqlite_context_triggers_reject_mismatched_parents():
    consultation = create_consultation(30)
    other_inquiry = create_inquiry(31)
    other_ai_run = create_ai_run(31, inquiry=other_inquiry)

    with pytest.raises(IntegrityError), transaction.atomic():
        HandoffReport.objects.create(
            **report_values(
                32,
                consultation=consultation,
                inquiry=other_inquiry,
                generated_by_ai_run=other_ai_run,
            )
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        HandoffReport.objects.create(
            **report_values(
                33,
                consultation=consultation,
                generated_by_ai_run=other_ai_run,
            )
        )


def test_sqlite_context_triggers_reject_parent_inquiry_change():
    values = report_values(40)
    report = HandoffReport.objects.create(**values)
    other_inquiry = create_inquiry(41)

    with pytest.raises(IntegrityError), transaction.atomic():
        Consultation.objects.filter(
            pk=report.consultation_id
        ).update(inquiry=other_inquiry)

    with pytest.raises(IntegrityError), transaction.atomic():
        AIRun.objects.filter(
            pk=report.generated_by_ai_run_id
        ).update(inquiry=other_inquiry)


def test_handoff_parent_deletion_is_protected():
    values = report_values(50)
    report = HandoffReport.objects.create(
        **values,
        consultant_final="Confirmed synthetic report.",
        confirmed_by=values["consultation"].consultant,
        confirmed_at=timezone.now(),
    )

    with pytest.raises(ProtectedError):
        report.consultation.delete()
    with pytest.raises(ProtectedError):
        report.inquiry.delete()
    with pytest.raises(ProtectedError):
        report.generated_by_ai_run.delete()
    with pytest.raises(ProtectedError):
        report.confirmed_by.delete()


def test_handoff_context_migration_matches_supported_databases():
    migration_module = importlib.import_module(
        "apps.visits.migrations.0003_handoffreport"
    )

    postgresql_statements: list[str] = []
    migration_module.add_handoff_context_integrity(
        None,
        SimpleNamespace(
            connection=SimpleNamespace(vendor="postgresql"),
            execute=postgresql_statements.append,
        ),
    )
    postgresql_sql = [
        " ".join(statement.split())
        for statement in postgresql_statements
    ]

    assert len(postgresql_sql) == 5
    assert (
        "ADD CONSTRAINT fk_handoff_ai_run_inquiry"
        in postgresql_sql[0]
    )
    assert (
        "FOREIGN KEY (generated_by_ai_run_id, inquiry_id)"
        in postgresql_sql[0]
    )
    assert (
        "REFERENCES aiops_ai_run (id, inquiry_id)"
        in postgresql_sql[0]
    )
    assert any(
        "CREATE TRIGGER trg_handoff_consult_context_child"
        in statement
        for statement in postgresql_sql
    )
    assert any(
        "CREATE TRIGGER trg_handoff_consult_context_parent"
        in statement
        for statement in postgresql_sql
    )

    sqlite_statements: list[str] = []
    migration_module.add_handoff_context_integrity(
        None,
        SimpleNamespace(
            connection=SimpleNamespace(vendor="sqlite"),
            execute=sqlite_statements.append,
        ),
    )

    assert len(sqlite_statements) == 6
    assert all(
        "CREATE TRIGGER" in statement
        for statement in sqlite_statements
    )
    assert sum(
        "fk_handoff_consultation_inquiry" in statement
        for statement in sqlite_statements
    ) == 3
    assert sum(
        "fk_handoff_ai_run_inquiry" in statement
        for statement in sqlite_statements
    ) == 3

    postgresql_reverse: list[str] = []
    migration_module.remove_handoff_context_integrity(
        None,
        SimpleNamespace(
            connection=SimpleNamespace(vendor="postgresql"),
            execute=postgresql_reverse.append,
        ),
    )
    assert len(postgresql_reverse) == 5
    assert any(
        "DROP CONSTRAINT IF EXISTS fk_handoff_ai_run_inquiry"
        in " ".join(statement.split())
        for statement in postgresql_reverse
    )

    sqlite_reverse: list[str] = []
    migration_module.remove_handoff_context_integrity(
        None,
        SimpleNamespace(
            connection=SimpleNamespace(vendor="sqlite"),
            execute=sqlite_reverse.append,
        ),
    )
    assert len(sqlite_reverse) == 6
    assert all(
        "DROP TRIGGER IF EXISTS" in statement
        for statement in sqlite_reverse
    )
