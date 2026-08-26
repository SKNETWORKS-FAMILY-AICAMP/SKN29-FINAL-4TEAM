"""T-005 symptom assessment model and database integrity tests."""

from uuid import UUID, uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import PROTECT, ProtectedError
from django.utils import timezone

from apps.audit.models import AIRun
from apps.inquiries.models import Inquiry, SymptomAssessment
from tests.unit.inquiries.test_t022_models import create_inquiry


pytestmark = pytest.mark.django_db


def assessment_values(
    sequence: int,
    *,
    inquiry: Inquiry | None = None,
    **overrides,
):
    values = {
        "inquiry": inquiry or create_inquiry(sequence),
        "assessment_version": 1,
        "ruleset_version": "safety-rules-v1",
        "risk_level_code": SymptomAssessment.RiskLevel.GENERAL,
        # The historical candidate is data for the test only. It is not a
        # TextChoices or DB allowed-set until priority-levels.yaml is approved.
        "priority_code": "NORMAL",
        "usage_guidance_status": (
            SymptomAssessment.UsageGuidanceStatus.NORMAL
        ),
        "requires_consultation": False,
        "reason": "Synthetic rule assessment.",
        "rule_result": {"matched_rules": []},
        "assessed_by_type_code": "RULE",
    }
    values.update(overrides)
    return values


def create_passed_risk_run(
    sequence: int,
    inquiry: Inquiry,
) -> AIRun:
    now = timezone.now()
    return AIRun.objects.create(
        inquiry=inquiry,
        task_type_code=AIRun.TaskType.ASSESS_RISK,
        response_schema_version="1.0.0",
        model_provider="local",
        model_name="contract-test-model",
        prompt_version="risk-prompt-v1",
        input_payload={"inquiry_id": str(inquiry.public_id)},
        input_sha256="a" * 64,
        idempotency_key=f"assessment-ai-run-{sequence:04d}",
        raw_output_text='{"risk_level_code": "general"}',
        validated_output_payload={
            "risk_level_code": "general",
        },
        schema_validation_status_code=(
            AIRun.SchemaValidationStatus.PASSED
        ),
        status_code=AIRun.Status.SUCCEEDED,
        started_at=now,
        completed_at=now,
        correlation_id=uuid4(),
    )


def test_assessment_uses_three_layer_identifier_and_history_fields():
    assessment = SymptomAssessment.objects.create(
        **assessment_values(1)
    )

    assert isinstance(assessment.pk, int)
    assert isinstance(assessment.public_id, UUID)
    assert assessment._meta.db_table == "support_symptom_assessment"
    assert assessment.assessment_version == 1
    assert assessment.ruleset_version == "safety-rules-v1"
    assert assessment.rule_result == {"matched_rules": []}
    assert assessment.assessed_by_type_code == "RULE"
    assert assessment.created_at is not None
    assert assessment.updated_at is not None
    assert assessment.inquiry.symptom_assessments.get() == assessment


def test_only_canonical_yaml_codes_are_declared_as_choices_and_checks():
    risk_field = SymptomAssessment._meta.get_field(
        "risk_level_code"
    )
    priority_field = SymptomAssessment._meta.get_field(
        "priority_code"
    )
    guidance_field = SymptomAssessment._meta.get_field(
        "usage_guidance_status"
    )
    origin_field = SymptomAssessment._meta.get_field(
        "assessed_by_type_code"
    )
    constraint_names = {
        constraint.name
        for constraint in SymptomAssessment._meta.constraints
    }

    assert set(risk_field.flatchoices) == {
        ("general", "General"),
        ("caution", "Caution"),
        ("danger", "Danger"),
    }
    assert {
        value for value, _ in guidance_field.flatchoices
    } == {
        "NORMAL",
        "PARTIAL_STOP",
        "TOTAL_STOP",
        "PENDING_CONSULTATION",
    }
    assert guidance_field.max_length == 32
    assert guidance_field.null is True

    assert not priority_field.choices
    assert not origin_field.choices
    assert (
        "ck_support_symptom_assessment_priority_code_allowed"
        not in constraint_names
    )
    assert (
        "ck_support_symptom_assessment_assessed_by_type_code_allowed"
        not in constraint_names
    )
    assert "ck_assessment_danger_priority" not in constraint_names


def test_assessment_declares_historical_indexes_and_safe_constraints():
    constraint_names = {
        constraint.name
        for constraint in SymptomAssessment._meta.constraints
    }
    index_names = {
        index.name for index in SymptomAssessment._meta.indexes
    }

    assert {
        "ux_assessment_version",
        "ck_assessment_version_positive",
        "ck_assessment_rule_result_object",
        "ck_assessment_ai_origin",
        "ck_assessment_danger_safety",
        "ck_assessment_caution_safety",
        "ck_assessment_pending_consultation",
        (
            "ck_support_symptom_assessment_"
            "risk_level_code_allowed"
        ),
        (
            "ck_support_symptom_assessment_"
            "usage_guidance_status_allowed"
        ),
    } == constraint_names
    assert index_names == {
        "ix_assessment_risk",
        "ix_assessment_ai_run",
    }


@pytest.mark.parametrize(
    ("sequence", "overrides"),
    [
        (10, {"assessment_version": 0}),
        (11, {"rule_result": []}),
        (12, {"risk_level_code": "UNKNOWN"}),
        (13, {"usage_guidance_status": "UNKNOWN"}),
        (
            14,
            {
                "risk_level_code": "danger",
                "usage_guidance_status": "NORMAL",
                "requires_consultation": False,
            },
        ),
        (
            15,
            {
                "risk_level_code": "caution",
                "usage_guidance_status": "NORMAL",
            },
        ),
        (
            16,
            {
                "usage_guidance_status": (
                    "PENDING_CONSULTATION"
                ),
                "requires_consultation": False,
            },
        ),
        (17, {"assessed_by_type_code": "AI"}),
        (
            18,
            {
                "risk_level_code": "danger",
                "usage_guidance_status": "PARTIAL_STOP",
                "requires_consultation": True,
                "rule_result": {
                    "matched_safety_rule_ids": [
                        "SAFETY-HOT-WATER-001"
                    ]
                },
            },
        ),
    ],
)
def test_database_checks_reject_contract_mismatches(
    sequence,
    overrides,
):
    with pytest.raises(IntegrityError), transaction.atomic():
        SymptomAssessment.objects.create(
            **assessment_values(sequence, **overrides)
        )


def test_assessment_version_is_unique_per_inquiry():
    inquiry = create_inquiry(20)
    SymptomAssessment.objects.create(
        **assessment_values(20, inquiry=inquiry)
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        SymptomAssessment.objects.create(
            **assessment_values(21, inquiry=inquiry)
        )


def test_danger_accepts_only_the_approved_safety_combination():
    assessment = SymptomAssessment(
        **assessment_values(
            30,
            risk_level_code=SymptomAssessment.RiskLevel.DANGER,
            usage_guidance_status=(
                SymptomAssessment.UsageGuidanceStatus.TOTAL_STOP
            ),
            requires_consultation=True,
        )
    )

    assessment.full_clean()
    assessment.save()

    assert assessment.risk_level_code == "danger"
    assert assessment.requires_consultation is True


def test_danger_accepts_approved_hot_water_heater_partial_stop():
    assessment = SymptomAssessment(
        **assessment_values(
            31,
            risk_level_code=SymptomAssessment.RiskLevel.DANGER,
            usage_guidance_status=(
                SymptomAssessment.UsageGuidanceStatus.PARTIAL_STOP
            ),
            requires_consultation=True,
            rule_result={
                "matched_safety_rule_ids": [
                    "SAFETY-HOT-WATER-HEATER-001"
                ]
            },
        )
    )

    assessment.full_clean()
    assessment.save()

    assert assessment.usage_guidance_status == "PARTIAL_STOP"


def test_model_rejects_unapproved_danger_partial_stop_rule():
    assessment = SymptomAssessment(
        **assessment_values(
            32,
            risk_level_code=SymptomAssessment.RiskLevel.DANGER,
            usage_guidance_status=(
                SymptomAssessment.UsageGuidanceStatus.PARTIAL_STOP
            ),
            requires_consultation=True,
            rule_result={
                "matched_safety_rule_ids": ["SAFETY-HOT-WATER-001"]
            },
        )
    )

    with pytest.raises(ValidationError) as exc_info:
        assessment.full_clean()

    assert "risk_level_code" in exc_info.value.message_dict


def test_ai_assessment_requires_validated_risk_run_on_same_inquiry():
    inquiry = create_inquiry(40)
    run = create_passed_risk_run(40, inquiry)
    assessment = SymptomAssessment(
        **assessment_values(
            40,
            inquiry=inquiry,
            assessed_by_type_code="AI",
            ai_run=run,
        )
    )

    assessment.full_clean()
    assessment.save()

    assert assessment.ai_run == run


def test_model_validation_rejects_non_risk_or_unvalidated_ai_run():
    inquiry = create_inquiry(41)
    run = AIRun.objects.create(
        inquiry=inquiry,
        task_type_code=AIRun.TaskType.STRUCTURE_SYMPTOM,
        response_schema_version="1.0.0",
        input_payload={},
        input_sha256="b" * 64,
        idempotency_key="assessment-ai-run-0041",
        correlation_id=uuid4(),
    )
    assessment = SymptomAssessment(
        **assessment_values(
            41,
            inquiry=inquiry,
            assessed_by_type_code="AI",
            ai_run=run,
        )
    )

    with pytest.raises(ValidationError) as exc_info:
        assessment.full_clean()

    assert "ai_run" in exc_info.value.message_dict


def test_database_enforces_ai_run_and_assessment_same_inquiry():
    first_inquiry = create_inquiry(50)
    other_inquiry = create_inquiry(51)
    run = create_passed_risk_run(50, first_inquiry)

    with pytest.raises(IntegrityError), transaction.atomic():
        SymptomAssessment.objects.create(
            **assessment_values(
                50,
                inquiry=other_inquiry,
                assessed_by_type_code="AI",
                ai_run=run,
            )
        )


def test_database_blocks_ai_run_parent_context_change():
    inquiry = create_inquiry(60)
    other_inquiry = create_inquiry(61)
    run = create_passed_risk_run(60, inquiry)
    SymptomAssessment.objects.create(
        **assessment_values(
            60,
            inquiry=inquiry,
            assessed_by_type_code="AI",
            ai_run=run,
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
                  AND name LIKE 'fk_assessment_context_%'
                ORDER BY name
                """
            )
            names = {row[0] for row in cursor.fetchall()}
            assert names == {
                "fk_assessment_context_child_insert",
                "fk_assessment_context_child_update",
                "fk_assessment_context_parent_update",
            }
        elif connection.vendor == "postgresql":
            cursor.execute(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conrelid =
                    'support_symptom_assessment'::regclass
                  AND conname = 'fk_assessment_ai_run_inquiry'
                """
            )
            assert cursor.fetchone() == (
                "fk_assessment_ai_run_inquiry",
            )
        else:
            pytest.fail(
                f"Unsupported database vendor: {connection.vendor}"
            )


def test_ai_run_deletion_is_protected_and_inquiry_fk_declares_protect():
    inquiry = create_inquiry(70)
    run = create_passed_risk_run(70, inquiry)
    SymptomAssessment.objects.create(
        **assessment_values(
            70,
            inquiry=inquiry,
            assessed_by_type_code="AI",
            ai_run=run,
        )
    )

    with pytest.raises(ProtectedError):
        run.delete()

    assert (
        SymptomAssessment._meta.get_field(
            "inquiry"
        ).remote_field.on_delete
        is PROTECT
    )
