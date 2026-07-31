"""T-005 AI execution model and database constraint tests."""

from datetime import date
from uuid import UUID, uuid4

import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AIRun
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db


def create_inquiry(sequence: int) -> Inquiry:
    """Create the minimum protected aggregate graph for an AI run."""

    user = User.objects.create_user(
        username=f"AI-RUN-CUSTOMER-{sequence:04d}",
        password=None,
        full_name=f"AI run customer {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    customer = CustomerProfile.objects.create(
        user=user,
        customer_no=f"AI-RUN-CUS-{sequence:04d}",
        customer_name=f"AI run customer {sequence}",
    )
    product = ProductModel.objects.create(
        model_code=f"AI-RUN-PMD-{sequence:04d}",
        model_name=f"AI run product {sequence}",
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"AI-RUN-SUB-{sequence:04d}",
        customer=customer,
        product_model=product,
        serial_no=f"AI-RUN-SERIAL-{sequence:04d}",
        started_on=date(2026, 7, 1),
    )
    return Inquiry.objects.create(
        subscription=subscription,
        initiated_by=user,
        channel_code=Inquiry.Channel.WEB,
        raw_text="Synthetic AI run test inquiry.",
    )


def ai_run_values(sequence: int, **overrides):
    values = {
        "inquiry": create_inquiry(sequence),
        "task_type_code": AIRun.TaskType.STRUCTURE_SYMPTOM,
        "response_schema_version": "1.0.0",
        "input_payload": {"raw_symptom": "water flow issue"},
        "input_sha256": "a" * 64,
        "idempotency_key": f"ai-run-{sequence:04d}",
        "correlation_id": uuid4(),
    }
    values.update(overrides)
    return values


def test_ai_run_uses_active_contract_identifiers_and_defaults():
    run = AIRun.objects.create(**ai_run_values(1))

    assert isinstance(run.pk, int)
    assert isinstance(run.public_id, UUID)
    assert isinstance(run.correlation_id, UUID)
    assert run._meta.db_table == "aiops_ai_run"
    assert run.inquiry.ai_runs.get() == run
    assert run.request_schema_version == "v1"
    assert run.model_config_version == "v1"
    assert run.model_config == {}
    assert run.schema_validation_errors == []
    assert run.schema_validation_status_code == "NOT_RUN"
    assert run.status_code == "QUEUED"
    assert run.retry_count == 0


def test_ai_run_declares_contract_indexes_and_constraints():
    constraint_names = {
        constraint.name for constraint in AIRun._meta.constraints
    }
    index_names = {index.name for index in AIRun._meta.indexes}

    assert {
        "ux_ai_run_idempotency",
        "ux_ai_run_id_inquiry",
        "ux_ai_run_id_inquiry_correlation",
        "ck_ai_run_success",
        "ck_ai_run_failure",
        "ck_ai_run_lifecycle",
        "ck_ai_run_reproducibility",
        "ck_ai_run_json_objects",
        "ck_ai_run_schema_failure",
        "ck_aiops_ai_run_task_type_code_allowed",
        "ck_aiops_ai_run_schema_validation_status_code_allowed",
        "ck_aiops_ai_run_status_code_allowed",
    }.issubset(constraint_names)
    assert index_names == {
        "ix_ai_run_inquiry_task",
        "ix_ai_run_status",
        "ix_ai_run_correlation",
    }


def test_ai_run_accepts_a_reproducible_success():
    started_at = timezone.now()
    run = AIRun.objects.create(
        **ai_run_values(
            2,
            model_provider="local",
            model_name="contract-test-model",
            prompt_version="prompt-v1",
            raw_output_text='{"result": "ok"}',
            validated_output_payload={"result": "ok"},
            schema_validation_status_code=(
                AIRun.SchemaValidationStatus.PASSED
            ),
            status_code=AIRun.Status.SUCCEEDED,
            started_at=started_at,
            completed_at=started_at,
            latency_ms=0,
            input_tokens=0,
            output_tokens=0,
        )
    )

    assert run.status_code == AIRun.Status.SUCCEEDED
    assert run.validated_output_payload == {"result": "ok"}


@pytest.mark.parametrize(
    ("sequence", "overrides"),
    [
        (10, {"task_type_code": "UNKNOWN_TASK"}),
        (11, {"input_sha256": "not-a-sha256"}),
        (12, {"status_code": AIRun.Status.RUNNING}),
        (
            13,
            {
                "status_code": AIRun.Status.SUCCEEDED,
                "started_at": timezone.now(),
                "completed_at": timezone.now(),
                "model_provider": "local",
                "model_name": "model",
                "prompt_version": "prompt-v1",
            },
        ),
        (
            14,
            {
                "status_code": AIRun.Status.FAILED,
                "started_at": timezone.now(),
                "completed_at": timezone.now(),
                "model_provider": "local",
                "model_name": "model",
                "prompt_version": "prompt-v1",
            },
        ),
        (15, {"retry_count": -1}),
        (16, {"input_payload": []}),
        (17, {"schema_validation_errors": {}}),
        (
            18,
            {
                "schema_validation_status_code": (
                    AIRun.SchemaValidationStatus.FAILED
                ),
                "schema_validation_errors": [],
                "raw_output_text": "invalid output",
            },
        ),
    ],
)
def test_ai_run_database_checks_reject_contract_mismatches(
    sequence,
    overrides,
):
    with pytest.raises(IntegrityError), transaction.atomic():
        AIRun.objects.create(
            **ai_run_values(sequence, **overrides)
        )


def test_ai_run_idempotency_is_unique_and_inquiry_is_protected():
    values = ai_run_values(30)
    inquiry = values["inquiry"]
    run = AIRun.objects.create(**values)

    with pytest.raises(IntegrityError), transaction.atomic():
        AIRun.objects.create(
            **ai_run_values(
                31,
                idempotency_key=run.idempotency_key,
            )
        )

    with pytest.raises(ProtectedError):
        inquiry.delete()
