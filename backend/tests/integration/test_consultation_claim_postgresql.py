"""PostgreSQL row-lock proof for the unassigned consultation Claim."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection
from rest_framework.exceptions import APIException

from apps.accounts.models import CustomerProfile, User
from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry
from apps.inquiries.services.consultation_claim_service import (
    ConsultationClaimService,
)
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import IdempotencyRecord, TransitionHistory
from common.exceptions.business import BusinessError


pytestmark = pytest.mark.django_db(transaction=True)


def create_user(sequence: int, *, role: str) -> User:
    user = User.objects.create_user(
        username=f"CLAIM-PG-{role}-{sequence:03d}",
        password=None,
        full_name=f"Claim PG {role} {sequence}",
        role_code=role,
        employee_no=(
            None
            if role == User.Role.CUSTOMER
            else f"CLAIM-PG-EMP-{sequence:03d}"
        ),
        is_active=True,
        is_synthetic=True,
    )
    if role == User.Role.CUSTOMER:
        CustomerProfile.objects.create(
            user=user,
            customer_no=f"CLAIM-PG-CUSTOMER-{sequence:03d}",
            customer_name=f"Claim PG customer {sequence}",
            is_synthetic=True,
        )
    return user


def create_queue_item(sequence: int) -> tuple[Inquiry, Consultation]:
    owner = create_user(sequence, role=User.Role.CUSTOMER)
    product = ProductModel.objects.create(
        model_code=f"CLAIM-PG-MODEL-{sequence:03d}",
        model_name=f"Claim PG model {sequence}",
        is_supported_mvp=True,
        is_active=True,
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"CLAIM-PG-CONTRACT-{sequence:03d}",
        customer=owner.customer_profile,
        product_model=product,
        serial_no=f"CLAIM-PG-SERIAL-{sequence:03d}",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 8, 1),
    )
    inquiry = Inquiry.objects.create(
        inquiry_code=f"CLAIM-PG-INQ-{sequence:03d}",
        subscription=subscription,
        initiated_by=owner,
        assigned_role_code=Inquiry.AssignedRole.NONE,
        channel_code=Inquiry.Channel.MOBILE,
        raw_text="동시 Claim 검증용 합성 문의",
        status_code=Inquiry.Status.CONSULTATION_REQUIRED,
        state_version=4,
    )
    consultation = Consultation.objects.create(
        consultation_code=f"CLAIM-PG-CONSULTATION-{sequence:03d}",
        inquiry=inquiry,
        sequence=1,
        status=Consultation.Status.WAITING,
        outcome=Consultation.Outcome.PENDING,
        state_version=4,
        idempotency_key=f"claim-pg-request-{sequence:03d}",
        correlation_id=uuid4(),
        data_classification=Consultation.DataClassification.SYNTHETIC,
    )
    return inquiry, consultation


def test_postgresql_two_consultants_claim_one_queue_item_once():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")
    first = create_user(1, role=User.Role.CONSULTANT)
    second = create_user(2, role=User.Role.CONSULTANT)
    inquiry, consultation = create_queue_item(10)
    barrier = Barrier(2)

    def perform_claim(index: int):
        close_old_connections()
        actor = (first, second)[index]
        try:
            barrier.wait(timeout=10)
            outcome = ConsultationClaimService.claim(
                actor=actor,
                inquiry_public_id=inquiry.public_id,
                validated_data={"state_version": 4},
                idempotency_key=f"claim-pg-winner-{index}",
                correlation_id=uuid4(),
            )
            return outcome.status_code
        except (BusinessError, APIException) as exc:
            return exc.status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(perform_claim, range(2)))

    assert sorted(statuses) == [200, 404]
    inquiry.refresh_from_db()
    consultation.refresh_from_db()
    assert inquiry.assigned_user_id in {first.pk, second.pk}
    assert inquiry.assigned_role_code == Inquiry.AssignedRole.CONSULTANT
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 5
    assert consultation.consultant_id == inquiry.assigned_user_id
    assert consultation.status == Consultation.Status.ASSIGNED
    assert consultation.state_version == 5
    assert consultation.started_at is None
    assert Consultation.objects.filter(inquiry=inquiry).count() == 1
    assert TransitionHistory.objects.filter(
        inquiry=inquiry,
        event_code="CLAIM_CONSULTATION",
    ).count() == 1
    assert IdempotencyRecord.objects.filter(
        operation_id="claimConsultation",
    ).count() == 1
