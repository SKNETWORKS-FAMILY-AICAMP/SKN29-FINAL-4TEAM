"""T-022 inquiry and workflow persistence constraints."""

from datetime import date
from uuid import UUID, uuid4

import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import Inquiry, SymptomEntry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import IdempotencyRecord, TransitionHistory


pytestmark = pytest.mark.django_db


def create_subscription(sequence: int = 1) -> CustomerSubscription:
    user = User.objects.create_user(
        id=f"DEMO-USR-{sequence + 700:03d}",
        username=f"T022-MODEL-CUSTOMER-{sequence:03d}",
        password=None,
        full_name=f"T022 model customer {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    customer = CustomerProfile.objects.create(
        id=f"DEMO-CUS-{sequence + 700:03d}",
        user=user,
        customer_no=f"T022-MODEL-CUS-{sequence:03d}",
        customer_name=f"T022 model customer {sequence}",
    )
    product = ProductModel.objects.create(
        model_code=f"T022-MODEL-PMD-{sequence:03d}",
        model_name=f"T022 model product {sequence}",
    )
    return CustomerSubscription.objects.create(
        contract_no=f"T022-MODEL-SUB-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"T022-MODEL-SERIAL-{sequence:03d}",
        started_on=date(2026, 7, 1),
    )


def create_inquiry(sequence: int = 1, **overrides) -> Inquiry:
    subscription = overrides.pop(
        "subscription",
        create_subscription(sequence),
    )
    values = {
        "subscription": subscription,
        "initiated_by": subscription.customer.user,
        "channel_code": Inquiry.Channel.WEB,
        "raw_text": "Water flow is lower than usual.",
    }
    values.update(overrides)
    return Inquiry.objects.create(**values)


def test_inquiry_uses_three_layer_identifiers_and_pm_initial_state():
    inquiry = create_inquiry()

    assert isinstance(inquiry.pk, int)
    assert isinstance(inquiry.public_id, UUID)
    assert inquiry.inquiry_code.startswith("INQ-")
    assert inquiry.status_code == Inquiry.Status.DRAFT
    assert inquiry.state_version == 1
    assert inquiry._meta.db_table == "support_inquiry"
    assert set(Inquiry.Status.values) == {
        "DRAFT",
        "QUESTIONNAIRE_IN_PROGRESS",
        "AI_GUIDANCE",
        "CONSULTATION_REQUIRED",
        "CONSULTATION_IN_PROGRESS",
        "VISIT_REVIEW_PENDING",
        "VISIT_SCHEDULING",
        "VISIT_SCHEDULED",
        "COMPLETION_PENDING",
        "REVISIT_REQUIRED",
        "REOPENED",
        "RESOLVED",
        "CANCELLED",
    }


def test_inquiry_database_checks_reject_invalid_codes_and_version():
    subscription = create_subscription()
    base_values = {
        "subscription": subscription,
        "initiated_by": subscription.customer.user,
        "raw_text": "Valid text",
    }

    with pytest.raises(IntegrityError), transaction.atomic():
        Inquiry.objects.create(
            **base_values,
            channel_code="UNKNOWN",
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        Inquiry.objects.create(
            **base_values,
            channel_code=Inquiry.Channel.WEB,
            status_code="UNKNOWN",
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        Inquiry.objects.create(
            **base_values,
            channel_code=Inquiry.Channel.WEB,
            state_version=0,
        )


def test_representative_symptom_is_normalized_and_protected():
    inquiry = create_inquiry()
    symptom = SymptomEntry.objects.create(
        inquiry=inquiry,
        symptom_type_code="LOW_FLOW",
        structured_payload={
            "representative_symptom_code": "LOW_FLOW",
        },
    )

    assert isinstance(symptom.pk, int)
    assert isinstance(symptom.public_id, UUID)
    assert symptom._meta.db_table == "support_inquiry_symptom"
    assert symptom.structured_payload == {
        "representative_symptom_code": "LOW_FLOW",
    }
    with pytest.raises(ProtectedError):
        inquiry.delete()


def test_workflow_records_use_public_uuid_and_unique_scopes():
    inquiry = create_inquiry()
    actor = inquiry.initiated_by
    first = IdempotencyRecord.objects.create(
        actor=actor,
        operation_id="startInquiry",
        idempotency_key="t022-model-key",
        request_hash="a" * 64,
    )
    history = TransitionHistory.objects.create(
        inquiry=inquiry,
        actor=actor,
        event_code="START_INQUIRY",
        from_state=None,
        to_state=Inquiry.Status.DRAFT,
        state_version=1,
        correlation_id=uuid4(),
        idempotency_key=first.idempotency_key,
    )

    assert isinstance(first.pk, int)
    assert isinstance(first.public_id, UUID)
    assert isinstance(history.pk, int)
    assert isinstance(history.public_id, UUID)

    with pytest.raises(IntegrityError), transaction.atomic():
        IdempotencyRecord.objects.create(
            actor=actor,
            operation_id="startInquiry",
            idempotency_key="t022-model-key",
            request_hash="b" * 64,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        TransitionHistory.objects.create(
            inquiry=inquiry,
            actor=actor,
            event_code="START_INQUIRY",
            from_state=None,
            to_state=Inquiry.Status.DRAFT,
            state_version=1,
            correlation_id=uuid4(),
            idempotency_key="another-key",
        )


def test_cancellation_reason_and_state_fields_are_database_constrained():
    assert Inquiry.CancellationReason.values == [
        "CUSTOMER_REQUEST",
        "DUPLICATE_INQUIRY",
        "ISSUE_RESOLVED",
        "OTHER",
    ]

    with pytest.raises(IntegrityError), transaction.atomic():
        create_inquiry(
            sequence=10,
            status_code=Inquiry.Status.CANCELLED,
            cancelled_at=timezone.now(),
            cancellation_reason_code="NOT_ALLOWED",
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_inquiry(
            sequence=11,
            status_code=Inquiry.Status.CANCELLED,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_inquiry(
            sequence=12,
            cancellation_reason_code=(
                Inquiry.CancellationReason.CUSTOMER_REQUEST
            ),
        )

    cancelled = create_inquiry(
        sequence=13,
        status_code=Inquiry.Status.CANCELLED,
        cancelled_at=timezone.now(),
        cancellation_reason_code=(
            Inquiry.CancellationReason.CUSTOMER_REQUEST
        ),
    )
    assert cancelled.status_code == Inquiry.Status.CANCELLED
