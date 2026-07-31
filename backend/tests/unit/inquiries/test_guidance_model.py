"""T-005 versioned guidance model and database integrity tests."""

from uuid import UUID, uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, models, transaction
from django.db.models import Q
from django.db.models.deletion import PROTECT, ProtectedError
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AIRun
from apps.inquiries.models import Guidance, Inquiry
from tests.unit.inquiries.test_t022_models import create_inquiry


pytestmark = pytest.mark.django_db


def guidance_values(
    sequence: int,
    *,
    inquiry: Inquiry | None = None,
    **overrides,
):
    values = {
        "inquiry": inquiry or create_inquiry(sequence),
        "guidance_version": 1,
        "title": f"Guidance {sequence}",
        "summary_text": "Check the appliance and follow the safe steps.",
        "evidence_sufficiency_code": "SUFFICIENT",
    }
    values.update(overrides)
    return values


def create_passed_guidance_run(
    sequence: int,
    inquiry: Inquiry,
    *,
    task_type_code: str = AIRun.TaskType.GENERATE_GUIDANCE,
    schema_validation_status_code: str = (
        AIRun.SchemaValidationStatus.PASSED
    ),
) -> AIRun:
    now = timezone.now()
    is_validated = (
        schema_validation_status_code
        == AIRun.SchemaValidationStatus.PASSED
    )
    return AIRun.objects.create(
        inquiry=inquiry,
        task_type_code=task_type_code,
        response_schema_version="1.0.0",
        model_provider="local",
        model_name="contract-test-model",
        prompt_version="guidance-prompt-v1",
        input_payload={"inquiry_id": str(inquiry.public_id)},
        input_sha256="d" * 64,
        idempotency_key=f"guidance-ai-run-{sequence:04d}",
        raw_output_text=(
            '{"guidance": {}}' if is_validated else None
        ),
        validated_output_payload=(
            {"guidance": {}} if is_validated else None
        ),
        schema_validation_status_code=(
            schema_validation_status_code
        ),
        status_code=(
            AIRun.Status.SUCCEEDED
            if is_validated
            else AIRun.Status.QUEUED
        ),
        started_at=now if is_validated else None,
        completed_at=now if is_validated else None,
        correlation_id=uuid4(),
    )


def create_reviewer(sequence: int) -> User:
    return User.objects.create_user(
        username=f"GUIDANCE-REVIEWER-{sequence:04d}",
        password=None,
        full_name=f"Guidance reviewer {sequence}",
        role_code=User.Role.CONSULTANT,
        employee_no=f"GUIDANCE-EMP-{sequence:04d}",
    )


def test_guidance_uses_contract_identifiers_fields_and_defaults():
    guidance = Guidance.objects.create(**guidance_values(1))
    concrete_fields = Guidance._meta.concrete_fields

    assert isinstance(guidance.pk, int)
    assert isinstance(guidance.public_id, UUID)
    assert guidance._meta.db_table == "support_guidance"
    assert guidance.guidance_version == 1
    assert guidance.review_status_code == "PENDING"
    assert guidance.safety_notice is None
    assert guidance.requires_consultation is False
    assert guidance.generated_by_ai_run is None
    assert guidance.reviewed_by is None
    assert guidance.reviewed_at is None
    assert guidance.created_at is not None
    assert guidance.updated_at is not None
    assert guidance.inquiry.guidance_versions.get() == guidance
    assert len(concrete_fields) == 15
    assert not any(
        isinstance(field, models.JSONField)
        for field in concrete_fields
    )


def test_unapproved_review_and_evidence_code_sets_remain_open():
    review_field = Guidance._meta.get_field("review_status_code")
    evidence_field = Guidance._meta.get_field(
        "evidence_sufficiency_code"
    )
    constraint_names = {
        constraint.name for constraint in Guidance._meta.constraints
    }

    assert not review_field.choices
    assert not evidence_field.choices
    assert (
        "ck_support_guidance_review_status_code_allowed"
        not in constraint_names
    )
    assert (
        "ck_support_guidance_evidence_sufficiency_code_allowed"
        not in constraint_names
    )

    guidance = Guidance.objects.create(
        **guidance_values(
            2,
            review_status_code="FUTURE_REVIEW_STATE",
            evidence_sufficiency_code="FUTURE_EVIDENCE_STATE",
        )
    )
    assert guidance.review_status_code == "FUTURE_REVIEW_STATE"
    assert (
        guidance.evidence_sufficiency_code
        == "FUTURE_EVIDENCE_STATE"
    )


def test_guidance_declares_structural_constraints_and_indexes():
    constraint_names = {
        constraint.name for constraint in Guidance._meta.constraints
    }
    indexes = {
        index.name: index for index in Guidance._meta.indexes
    }

    assert constraint_names == {
        "ux_guidance_version",
        "ux_guidance_id_inquiry",
        "ck_guidance_version_positive",
        "ck_guidance_review_status_nonempty",
        "ck_guidance_title_nonempty",
        "ck_guidance_summary_nonempty",
        "ck_guidance_evidence_code_nonempty",
        "ck_guidance_review_pair",
    }
    assert set(indexes) == {
        "ix_guidance_review_queue",
        "ix_guidance_ai_run",
    }
    assert indexes["ix_guidance_review_queue"].condition == Q(
        review_status_code="PENDING"
    )


def test_database_enforces_positive_and_unique_guidance_version():
    inquiry = create_inquiry(10)
    Guidance.objects.create(**guidance_values(10, inquiry=inquiry))

    with pytest.raises(IntegrityError), transaction.atomic():
        Guidance.objects.create(
            **guidance_values(11, inquiry=inquiry)
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        Guidance.objects.create(
            **guidance_values(
                12,
                inquiry=inquiry,
                guidance_version=0,
            )
        )


@pytest.mark.parametrize(
    ("field_name", "empty_value"),
    [
        ("review_status_code", " "),
        ("title", "\t"),
        ("summary_text", "\r\n"),
        ("evidence_sufficiency_code", "   "),
    ],
)
def test_database_rejects_whitespace_only_required_text(
    field_name,
    empty_value,
):
    with pytest.raises(IntegrityError), transaction.atomic():
        Guidance.objects.create(
            **guidance_values(
                20,
                **{field_name: empty_value},
            )
        )


def test_database_requires_reviewer_and_review_time_as_a_pair():
    inquiry = create_inquiry(30)
    reviewer = create_reviewer(30)

    with pytest.raises(IntegrityError), transaction.atomic():
        Guidance.objects.create(
            **guidance_values(
                30,
                inquiry=inquiry,
                reviewed_by=reviewer,
            )
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        Guidance.objects.create(
            **guidance_values(
                31,
                inquiry=inquiry,
                reviewed_at=timezone.now(),
            )
        )

    guidance = Guidance.objects.create(
        **guidance_values(
            32,
            inquiry=inquiry,
            reviewed_by=reviewer,
            reviewed_at=timezone.now(),
        )
    )
    assert guidance.reviewed_by == reviewer


def test_unapproved_status_dependent_policies_are_deferred():
    guidance = Guidance(
        **guidance_values(
            40,
            review_status_code="APPROVED",
            evidence_sufficiency_code="INSUFFICIENT",
            requires_consultation=False,
        )
    )

    guidance.full_clean()
    guidance.save()
    Guidance.objects.filter(pk=guidance.pk).update(
        title="Updated before immutable policy approval"
    )
    deleted_count, _ = Guidance.objects.filter(
        pk=guidance.pk
    ).delete()

    constraint_names = {
        constraint.name for constraint in Guidance._meta.constraints
    }
    assert "ck_guidance_review_fields" not in constraint_names
    assert (
        "ck_guidance_insufficient_handoff"
        not in constraint_names
    )
    assert deleted_count == 1


def test_guidance_accepts_validated_generation_run():
    inquiry = create_inquiry(50)
    run = create_passed_guidance_run(50, inquiry)
    guidance = Guidance(
        **guidance_values(
            50,
            inquiry=inquiry,
            generated_by_ai_run=run,
        )
    )

    guidance.full_clean()
    guidance.save()

    assert guidance.generated_by_ai_run == run


@pytest.mark.parametrize(
    ("task_type_code", "schema_validation_status_code"),
    [
        (
            AIRun.TaskType.GENERATE_QUESTIONS,
            AIRun.SchemaValidationStatus.PASSED,
        ),
        (
            AIRun.TaskType.GENERATE_GUIDANCE,
            AIRun.SchemaValidationStatus.NOT_RUN,
        ),
    ],
)
def test_model_rejects_wrong_task_or_unvalidated_ai_run(
    task_type_code,
    schema_validation_status_code,
):
    inquiry = create_inquiry(60)
    run = create_passed_guidance_run(
        60,
        inquiry,
        task_type_code=task_type_code,
        schema_validation_status_code=(
            schema_validation_status_code
        ),
    )
    guidance = Guidance(
        **guidance_values(
            60,
            inquiry=inquiry,
            generated_by_ai_run=run,
        )
    )

    with pytest.raises(ValidationError) as exc_info:
        guidance.full_clean()

    assert "generated_by_ai_run" in exc_info.value.message_dict


def test_database_enforces_ai_run_and_guidance_same_inquiry():
    first_inquiry = create_inquiry(70)
    other_inquiry = create_inquiry(71)
    run = create_passed_guidance_run(70, first_inquiry)

    with pytest.raises(IntegrityError), transaction.atomic():
        Guidance.objects.create(
            **guidance_values(
                70,
                inquiry=other_inquiry,
                generated_by_ai_run=run,
            )
        )


def test_database_blocks_ai_run_parent_context_change():
    inquiry = create_inquiry(80)
    other_inquiry = create_inquiry(81)
    run = create_passed_guidance_run(80, inquiry)
    Guidance.objects.create(
        **guidance_values(
            80,
            inquiry=inquiry,
            generated_by_ai_run=run,
        )
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        AIRun.objects.filter(pk=run.pk).update(
            inquiry=other_inquiry
        )


def test_composite_integrity_ddl_is_installed_for_current_database():
    with connection.cursor() as cursor:
        if connection.vendor == "sqlite":
            cursor.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'trigger'
                  AND name LIKE 'fk_guidance_context_%'
                ORDER BY name
                """
            )
            names = {row[0] for row in cursor.fetchall()}
            assert names == {
                "fk_guidance_context_child_insert",
                "fk_guidance_context_child_update",
                "fk_guidance_context_parent_update",
            }
        elif connection.vendor == "postgresql":
            cursor.execute(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'support_guidance'::regclass
                  AND conname = 'fk_guidance_ai_run_inquiry'
                """
            )
            assert cursor.fetchone() == (
                "fk_guidance_ai_run_inquiry",
            )
        else:
            pytest.fail(
                f"Unsupported database vendor: {connection.vendor}"
            )


def test_parent_deletions_are_protected():
    inquiry = create_inquiry(90)
    run = create_passed_guidance_run(90, inquiry)
    reviewer = create_reviewer(90)
    Guidance.objects.create(
        **guidance_values(
            90,
            inquiry=inquiry,
            generated_by_ai_run=run,
            reviewed_by=reviewer,
            reviewed_at=timezone.now(),
        )
    )

    with pytest.raises(ProtectedError):
        run.delete()
    with pytest.raises(ProtectedError):
        reviewer.delete()
    with pytest.raises(ProtectedError):
        inquiry.delete()

    assert (
        Guidance._meta.get_field("inquiry").remote_field.on_delete
        is PROTECT
    )
