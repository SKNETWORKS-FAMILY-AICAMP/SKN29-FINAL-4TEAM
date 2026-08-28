"""Supervisor consultation operations must preserve workflow semantics."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from apps.accounts.models import CustomerProfile, User
from apps.consultations.models import Consultation
from apps.consultations.services.supervisor_consultation_service import (
    SupervisorConsultationError,
    SupervisorConsultationService,
)
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import TransitionHistory


pytestmark = pytest.mark.django_db
PASSWORD = "SupervisorPassword2026!"


def user(sequence: int, role: str, *, supervisor: bool = False) -> User:
    username = (
        "SYN-WATERBRIDGE-SUPERVISOR"
        if supervisor
        else f"SYN-{role}-{sequence:03d}"
    )
    return User.objects.create_user(
        username=username,
        password=PASSWORD,
        full_name=f"Synthetic {role} {sequence}",
        role_code=role,
        employee_no=None if role == User.Role.CUSTOMER else f"SYN-EMP-{sequence:03d}",
        is_synthetic=True,
        is_staff=supervisor,
        is_superuser=supervisor,
    )


def consultation_fixture(sequence: int = 1):
    supervisor = user(900, User.Role.OPERATOR, supervisor=True)
    consultant_a = user(sequence + 100, User.Role.CONSULTANT)
    consultant_b = user(sequence + 200, User.Role.CONSULTANT)
    customer = user(sequence, User.Role.CUSTOMER)
    profile = CustomerProfile.objects.create(
        user=customer,
        customer_no=f"SYN-CUSTOMER-{sequence:03d}",
        customer_name=f"Synthetic customer {sequence}",
        is_synthetic=True,
    )
    product = ProductModel.objects.create(
        model_code=f"SYN-MODEL-{sequence:03d}",
        model_name=f"Synthetic model {sequence}",
        manufacturer="SK매직",
        is_supported_mvp=True,
        is_active=True,
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"SYN-CONTRACT-{sequence:03d}",
        customer=profile,
        product_model=product,
        serial_no=f"SYN-SERIAL-{sequence:03d}",
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 8, 1),
    )
    inquiry = Inquiry.objects.create(
        inquiry_code=f"SYN-INQUIRY-{sequence:03d}",
        subscription=subscription,
        initiated_by=customer,
        assigned_user=consultant_a,
        assigned_role_code=Inquiry.AssignedRole.CONSULTANT,
        channel_code=Inquiry.Channel.MOBILE,
        raw_text="Synthetic water flow issue",
        status_code=Inquiry.Status.CONSULTATION_REQUIRED,
        state_version=2,
    )
    consultation = Consultation.objects.create(
        consultation_code=f"SYN-CONSULTATION-{sequence:03d}",
        inquiry=inquiry,
        sequence=1,
        consultant=consultant_a,
        status=Consultation.Status.ASSIGNED,
        outcome=Consultation.Outcome.PENDING,
        summary="",
        state_version=2,
        idempotency_key=f"fixture-{sequence}",
        correlation_id=uuid4(),
        data_classification=Consultation.DataClassification.SYNTHETIC,
    )
    return supervisor, consultant_a, consultant_b, inquiry, consultation


def test_supervisor_can_reassign_and_complete_through_state_machine():
    supervisor, _, consultant_b, inquiry, consultation = consultation_fixture()

    SupervisorConsultationService.reassign(
        actor=supervisor,
        consultation_id=consultation.pk,
        target_consultant_id=consultant_b.pk,
        reason="Transfer unavailable consultant case",
    )
    inquiry.refresh_from_db()
    consultation.refresh_from_db()
    assert inquiry.assigned_user == consultant_b
    assert consultation.consultant == consultant_b

    SupervisorConsultationService.start(
        actor=supervisor,
        consultation_id=consultation.pk,
    )
    SupervisorConsultationService.update_details(
        actor=supervisor,
        consultation_id=consultation.pk,
        values={
            "summary": "Synthetic resolution summary",
            "consultation_note": "Synthetic note",
            "additional_check": "Synthetic follow-up",
            "customer_guidance": "Synthetic customer guidance",
            "result_code": Consultation.Outcome.COMPLETED_NO_VISIT,
            "usage_guidance_status": "NORMAL",
        },
    )
    SupervisorConsultationService.confirm(
        actor=supervisor,
        consultation_id=consultation.pk,
    )
    SupervisorConsultationService.complete(
        actor=supervisor,
        consultation_id=consultation.pk,
    )

    inquiry.refresh_from_db()
    consultation.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.COMPLETION_PENDING
    assert consultation.status == Consultation.Status.COMPLETED
    assert consultation.confirmed_summary == "Synthetic resolution summary"
    events = TransitionHistory.objects.filter(inquiry=inquiry).order_by(
        "state_version"
    )
    assert list(events.values_list("event_code", flat=True)) == [
        "START_CONSULTATION",
        "UPDATE_CONSULTATION_SUMMARY",
        "CONFIRM_CONSULTATION_SUMMARY",
        "CONSULTATION_COMPLETED",
    ]
    assert set(events.values_list("actor", flat=True)) == {supervisor.pk}


def test_supervisor_cancel_consultation_uses_terminal_inquiry_transition():
    supervisor, _, _, inquiry, consultation = consultation_fixture(sequence=2)
    SupervisorConsultationService.cancel_consultation(
        actor=supervisor,
        consultation_id=consultation.pk,
        reason="Synthetic customer requested cancellation",
    )
    inquiry.refresh_from_db()
    consultation.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CANCELLED
    assert inquiry.state_version == 3
    assert inquiry.assigned_user is not None
    assert inquiry.assigned_role_code == Inquiry.AssignedRole.CONSULTANT
    assert consultation.status == Consultation.Status.CANCELLED
    assert consultation.state_version == 3
    assert TransitionHistory.objects.filter(
        inquiry=inquiry,
        event_code="CANCEL_INQUIRY",
        from_state=Inquiry.Status.CONSULTATION_REQUIRED,
        to_state=Inquiry.Status.CANCELLED,
    ).exists()


def test_supervisor_can_cancel_in_progress_consultation_atomically():
    supervisor, _, _, inquiry, consultation = consultation_fixture(sequence=4)
    SupervisorConsultationService.start(
        actor=supervisor,
        consultation_id=consultation.pk,
    )
    consultation.refresh_from_db()
    assert consultation.status == Consultation.Status.IN_PROGRESS

    SupervisorConsultationService.cancel_consultation(
        actor=supervisor,
        consultation_id=consultation.pk,
        reason="Synthetic customer requested cancellation in progress",
    )

    inquiry.refresh_from_db()
    consultation.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CANCELLED
    assert consultation.status == Consultation.Status.CANCELLED
    assert consultation.state_version == inquiry.state_version
    assert list(
        TransitionHistory.objects.filter(inquiry=inquiry)
        .order_by("state_version")
        .values_list("event_code", flat=True)
    ) == ["START_CONSULTATION", "CANCEL_INQUIRY"]


def test_non_supervisor_cannot_use_override_service():
    _, consultant_a, consultant_b, _, consultation = consultation_fixture(
        sequence=3
    )
    with pytest.raises(SupervisorConsultationError, match="Supervisor"):
        SupervisorConsultationService.reassign(
            actor=consultant_a,
            consultation_id=consultation.pk,
            target_consultant_id=consultant_b.pk,
            reason="Unauthorized transfer",
        )
