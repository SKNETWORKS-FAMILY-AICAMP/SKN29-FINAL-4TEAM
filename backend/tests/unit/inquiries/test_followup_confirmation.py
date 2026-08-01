"""Synthetic follow-up source linkage and lifecycle constraints."""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.accounts.models import CustomerProfile, User
from apps.consultations.models import Consultation
from apps.inquiries.models import FollowupConfirmation, Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.visits.models import Visit


pytestmark = pytest.mark.django_db


def create_inquiry(sequence: int) -> Inquiry:
    customer_user = User.objects.create_user(
        username=f"FOLLOWUP-CUSTOMER-{sequence:03d}",
        full_name=f"Followup customer {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    customer = CustomerProfile.objects.create(
        user=customer_user,
        customer_no=f"FOLLOWUP-CUS-{sequence:03d}",
        customer_name=f"Followup customer {sequence}",
    )
    product = ProductModel.objects.create(
        model_code=f"FOLLOWUP-PMD-{sequence:03d}",
        model_name=f"Followup product {sequence}",
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"FOLLOWUP-SUB-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"FOLLOWUP-SERIAL-{sequence:03d}",
        started_on=date(2026, 7, 1),
    )
    return Inquiry.objects.create(
        subscription=subscription,
        initiated_by=customer_user,
        channel_code=None,
        raw_text="Synthetic follow-up fixture inquiry.",
    )


def create_sources(sequence: int):
    inquiry = create_inquiry(sequence)
    consultant = User.objects.create_user(
        username=f"FOLLOWUP-CONSULTANT-{sequence:03d}",
        full_name=f"Followup consultant {sequence}",
        role_code=User.Role.CONSULTANT,
        employee_no=f"FOLLOWUP-CNS-{sequence:03d}",
    )
    technician = User.objects.create_user(
        username=f"FOLLOWUP-TECHNICIAN-{sequence:03d}",
        full_name=f"Followup technician {sequence}",
        role_code=User.Role.TECHNICIAN,
        employee_no=f"FOLLOWUP-TEC-{sequence:03d}",
    )
    created_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    consultation = Consultation.objects.create(
        consultation_code=f"CON-SYN-FUP-{sequence:03d}",
        inquiry=inquiry,
        sequence=1,
        consultant=consultant,
        status=Consultation.Status.COMPLETED,
        outcome=Consultation.Outcome.VISIT_REQUIRED,
        summary="Synthetic completed consultation.",
        state_version=1,
        idempotency_key=f"followup-consult-{sequence}",
        correlation_id=uuid4(),
        created_at=created_at,
        started_at=created_at + timedelta(hours=1),
        completed_at=created_at + timedelta(hours=2),
        data_classification=(
            Consultation.DataClassification.SYNTHETIC
        ),
    )
    visit = Visit.objects.create(
        visit_code=f"VIS-SYN-FUP-{sequence:03d}",
        inquiry=inquiry,
        technician=technician,
        status=Visit.Status.COMPLETED,
        requested_at=created_at + timedelta(hours=2),
        scheduled_at=created_at + timedelta(days=1),
        started_at=created_at + timedelta(days=1),
        completed_at=created_at + timedelta(days=1, hours=1),
        confirmed_cause="Synthetic cause",
        action_taken="Synthetic action",
        state_version=5,
        idempotency_key=f"followup-visit-{sequence}",
        correlation_id=consultation.correlation_id,
        data_classification=Visit.DataClassification.SYNTHETIC,
    )
    return inquiry, consultation, visit


def test_followup_preserves_consultation_and_visit_lineage():
    inquiry, consultation, visit = create_sources(1)
    requested_at = visit.completed_at
    followup = FollowupConfirmation(
        followup_code="SYN-FOLLOWUP-0001",
        inquiry=inquiry,
        consultation=consultation,
        visit=visit,
        channel_code=FollowupConfirmation.Channel.APP,
        resolution_status_code=(
            FollowupConfirmation.ResolutionStatus.RESOLVED
        ),
        state_version=1,
        customer_response="방문 후 해결되었습니다.",
        next_action=(
            FollowupConfirmation.NextAction.FINALIZE_INQUIRY
        ),
        requested_at=requested_at,
        responded_at=requested_at + timedelta(hours=2),
        confirmed_at=requested_at + timedelta(hours=3),
    )
    followup.full_clean()
    followup.save()

    assert followup.consultation == consultation
    assert followup.visit == visit
    assert followup.channel_code == FollowupConfirmation.Channel.APP


def test_followup_rejects_source_from_another_inquiry():
    inquiry, consultation, _ = create_sources(2)
    other_inquiry, _, other_visit = create_sources(3)
    followup = FollowupConfirmation(
        followup_code="SYN-FOLLOWUP-0002",
        inquiry=inquiry,
        consultation=consultation,
        visit=other_visit,
        channel_code=FollowupConfirmation.Channel.APP,
        resolution_status_code=(
            FollowupConfirmation.ResolutionStatus.RESOLVED
        ),
        state_version=1,
        requested_at=other_visit.completed_at,
        responded_at=other_visit.completed_at,
        confirmed_at=other_visit.completed_at,
    )

    with pytest.raises(ValidationError):
        followup.full_clean()
    assert other_inquiry != inquiry


def test_pending_followup_cannot_have_a_response_timestamp():
    inquiry, consultation, _ = create_sources(4)
    with pytest.raises(IntegrityError), transaction.atomic():
        FollowupConfirmation.objects.create(
            followup_code="SYN-FOLLOWUP-0004",
            inquiry=inquiry,
            consultation=consultation,
            channel_code=FollowupConfirmation.Channel.APP,
            resolution_status_code=(
                FollowupConfirmation.ResolutionStatus.PENDING
            ),
            state_version=1,
            requested_at=consultation.completed_at,
            responded_at=consultation.completed_at,
        )


def test_consultation_rejects_non_consultant_assignment():
    inquiry, consultation, visit = create_sources(5)
    invalid = Consultation(
        consultation_code="CON-SYN-FUP-005-2",
        inquiry=inquiry,
        sequence=2,
        consultant=visit.technician,
        status=Consultation.Status.IN_PROGRESS,
        outcome=Consultation.Outcome.PENDING,
        summary="Invalid staff role.",
        state_version=1,
        idempotency_key="followup-invalid-consultant",
        correlation_id=consultation.correlation_id,
        created_at=consultation.created_at,
        started_at=consultation.started_at,
    )

    with pytest.raises(ValidationError):
        invalid.full_clean()


def test_visit_completed_state_requires_result_fields():
    inquiry, consultation, visit = create_sources(6)
    with pytest.raises(IntegrityError), transaction.atomic():
        Visit.objects.create(
            visit_code="VIS-SYN-FUP-006-2",
            inquiry=inquiry,
            technician=visit.technician,
            status=Visit.Status.COMPLETED,
            requested_at=visit.requested_at,
            started_at=visit.started_at,
            completed_at=visit.completed_at,
            confirmed_cause=None,
            action_taken=None,
            state_version=5,
            idempotency_key="followup-invalid-visit",
            correlation_id=consultation.correlation_id,
            data_classification=Visit.DataClassification.SYNTHETIC,
        )
