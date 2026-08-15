"""Synthetic-only Mobile-to-Web consultant assignment runtime checks."""

from __future__ import annotations

import json
from datetime import date
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry, SymptomEntry
from apps.inquiries.services.synthetic_e2e_assignment_service import (
    DEMO_CONSULTANT_USERNAME,
    DEMO_CUSTOMER_NO,
    DEMO_CUSTOMER_USERNAME,
    SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE,
)
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import IdempotencyRecord, TransitionHistory
from apps.workflow.repositories.workflow_repository import WorkflowRepository


pytestmark = pytest.mark.django_db

TARGET_MODEL_CODE = "WPUJAC104DWH"


def create_user(
    *,
    username: str,
    role: str,
    is_active: bool = True,
    is_synthetic: bool = True,
) -> User:
    return User.objects.create_user(
        username=username,
        password=None,
        full_name=f"Synthetic {username}",
        role_code=role,
        employee_no=(None if role == User.Role.CUSTOMER else username[-32:]),
        is_active=is_active,
        is_synthetic=is_synthetic,
    )


def create_target_inquiry(
    *,
    sequence: int,
    model_code: str = TARGET_MODEL_CODE,
    channel: str = Inquiry.Channel.MOBILE,
    status: str = Inquiry.Status.AI_GUIDANCE,
    owner_is_synthetic: bool = True,
    owner_username: str = DEMO_CUSTOMER_USERNAME,
    customer_no: str = DEMO_CUSTOMER_NO,
    symptom_code: str = "LOW_FLOW",
) -> tuple[User, Inquiry]:
    owner = User.objects.filter(username=owner_username).first()
    if owner is None:
        owner = create_user(
            username=owner_username,
            role=User.Role.CUSTOMER,
            is_synthetic=owner_is_synthetic,
        )
    customer, _ = CustomerProfile.objects.get_or_create(
        user=owner,
        defaults={
            "customer_no": customer_no,
            "customer_name": f"Synthetic E2E customer {sequence}",
            "is_synthetic": True,
        },
    )
    product_code = (
        f"{model_code}-{sequence:03d}"
        if model_code != TARGET_MODEL_CODE
        else model_code
    )
    product, _ = ProductModel.objects.get_or_create(
        model_code=product_code,
        defaults={
            "model_name": f"Synthetic E2E product {sequence}",
            "is_supported_mvp": True,
            "is_active": True,
        },
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"SYN-E2E-CONTRACT-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"SYN-E2E-SERIAL-{sequence:03d}",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 8, 1),
    )
    inquiry = Inquiry.objects.create(
        subscription=subscription,
        initiated_by=owner,
        channel_code=channel,
        raw_text="출수량이 줄어든 합성 E2E 문의입니다.",
        status_code=status,
        state_version=3,
    )
    SymptomEntry.objects.create(
        inquiry=inquiry,
        symptom_type_code=symptom_code,
        structured_payload={
            "representative_symptom_code": symptom_code,
        },
        schema_version="v1",
        is_customer_confirmed=True,
    )
    return owner, inquiry


def create_demo_consultant(*, is_active: bool = True) -> User:
    return create_user(
        username=DEMO_CONSULTANT_USERNAME,
        role=User.Role.CONSULTANT,
        is_active=is_active,
    )


def client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def request_consultation(
    *,
    actor: User,
    inquiry: Inquiry,
    key: str,
    state_version: int = 3,
) -> object:
    return client_for(actor).post(
        f"/api/v1/inquiries/{inquiry.public_id}/request-consultation",
        {"state_version": state_version},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )


def prepare(inquiry: Inquiry) -> dict:
    output = StringIO()
    call_command(
        "prepare_synthetic_e2e_assignment",
        "--inquiry-id",
        str(inquiry.public_id),
        "--json",
        stdout=output,
    )
    return json.loads(output.getvalue())


def test_prepare_command_marks_one_exact_runtime_inquiry_idempotently():
    create_demo_consultant()
    _, inquiry = create_target_inquiry(sequence=1)

    first = prepare(inquiry)
    second = prepare(inquiry)

    inquiry.refresh_from_db()
    assert first == second
    assert first == {
        "assigned_consultant_code": DEMO_CONSULTANT_USERNAME,
        "assignment_mode": "SYNTHETIC_E2E_ASSIGNMENT",
        "inquiry_code": inquiry.inquiry_code,
        "inquiry_id": str(inquiry.public_id),
        "operation_id": "requestConsultation",
        "scenario_code": SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE,
        "scenario_reference": "SYN-JAC104-002",
        "state_version": 3,
        "status_code": Inquiry.Status.AI_GUIDANCE,
    }
    assert inquiry.scenario_code == SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE
    assert inquiry.assigned_user is None
    assert inquiry.assigned_role_code == Inquiry.AssignedRole.NONE
    assert not Consultation.objects.filter(inquiry=inquiry).exists()


@pytest.mark.parametrize(
    ("case", "kwargs", "message"),
    [
        ("wrong-model", {"model_code": "UNSUPPORTED"}, "제품"),
        ("wrong-channel", {"channel": Inquiry.Channel.WEB}, "Mobile"),
        ("wrong-state", {"status": Inquiry.Status.DRAFT}, "AI_GUIDANCE"),
        ("real-owner", {"owner_is_synthetic": False}, "합성"),
        (
            "wrong-demo-owner",
            {
                "owner_username": "SYN-E2E-CUSTOMER-OTHER",
                "customer_no": "SYN-E2E-CUSTOMER-OTHER",
            },
            DEMO_CUSTOMER_USERNAME,
        ),
        ("wrong-symptom", {"symptom_code": "LEAK"}, "LOW_FLOW"),
    ],
)
def test_prepare_command_rejects_out_of_scope_inquiries(case, kwargs, message):
    del case
    create_demo_consultant()
    _, inquiry = create_target_inquiry(sequence=2, **kwargs)

    with pytest.raises(CommandError, match=message):
        prepare(inquiry)

    inquiry.refresh_from_db()
    assert inquiry.scenario_code is None


def test_prepare_command_rejects_a_second_active_marker():
    create_demo_consultant()
    _, first = create_target_inquiry(sequence=9)
    _, second = create_target_inquiry(sequence=10)
    prepare(first)

    with pytest.raises(CommandError, match="이미 합성 E2E"):
        prepare(second)

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.scenario_code == SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE
    assert second.scenario_code is None


def test_prepare_command_rotates_marker_after_the_previous_p0_run_finishes():
    create_demo_consultant()
    _, previous = create_target_inquiry(sequence=11)
    _, current = create_target_inquiry(sequence=12)
    prepare(previous)
    previous.status_code = Inquiry.Status.COMPLETION_PENDING
    previous.save(update_fields=["status_code", "updated_at"])
    previous_updated_at = previous.updated_at

    prepared = prepare(current)

    previous.refresh_from_db()
    current.refresh_from_db()
    assert previous.status_code == Inquiry.Status.COMPLETION_PENDING
    assert previous.scenario_code is None
    assert previous.updated_at == previous_updated_at
    assert current.scenario_code == SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE
    assert prepared["inquiry_id"] == str(current.public_id)


def test_marked_request_assigns_inquiry_but_preserves_waiting_consultation():
    consultant = create_demo_consultant()
    other_consultant = create_user(
        username="SYN-E2E-CONSULTANT-OTHER",
        role=User.Role.CONSULTANT,
    )
    owner, inquiry = create_target_inquiry(sequence=3)
    prepare(inquiry)

    response = request_consultation(
        actor=owner,
        inquiry=inquiry,
        key="synthetic-e2e-request-consultation-003",
    )

    assert response.status_code == 200
    inquiry.refresh_from_db()
    consultation = Consultation.objects.get(inquiry=inquiry)
    assert inquiry.assigned_user == consultant
    assert inquiry.assigned_role_code == Inquiry.AssignedRole.CONSULTANT
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 4
    assert consultation.status == Consultation.Status.WAITING
    assert consultation.consultant is None

    consultant_client = client_for(consultant)
    inquiry_list = consultant_client.get("/api/v1/inquiries")
    detail = consultant_client.get(f"/api/v1/inquiries/{inquiry.public_id}")
    other_list = client_for(other_consultant).get("/api/v1/inquiries")
    hidden = client_for(other_consultant).get(
        f"/api/v1/inquiries/{inquiry.public_id}"
    )
    hidden_start = client_for(other_consultant).post(
        f"/api/v1/inquiries/{inquiry.public_id}/start-consultation",
        {"state_version": 4},
        format="json",
        HTTP_IDEMPOTENCY_KEY="synthetic-e2e-hidden-start-003",
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )

    assert inquiry_list.status_code == detail.status_code == 200
    assert str(inquiry.public_id) in {
        item["inquiry_id"] for item in inquiry_list.data["data"]["items"]
    }
    assert other_list.status_code == 200
    assert other_list.data["data"]["items"] == []
    assert hidden.status_code == 404
    assert hidden_start.status_code == 404

    started = consultant_client.post(
        f"/api/v1/inquiries/{inquiry.public_id}/start-consultation",
        {"state_version": 4},
        format="json",
        HTTP_IDEMPOTENCY_KEY="synthetic-e2e-start-consultation-003",
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )
    assert started.status_code == 200
    inquiry.refresh_from_db()
    consultation.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_IN_PROGRESS
    assert consultation.status == Consultation.Status.IN_PROGRESS
    assert consultation.consultant == consultant


def test_unmarked_request_keeps_existing_unassigned_behavior():
    create_demo_consultant()
    owner, inquiry = create_target_inquiry(sequence=4)

    response = request_consultation(
        actor=owner,
        inquiry=inquiry,
        key="ordinary-request-consultation-004",
    )

    assert response.status_code == 200
    inquiry.refresh_from_db()
    assert inquiry.assigned_user is None
    assert inquiry.assigned_role_code == Inquiry.AssignedRole.NONE
    assert Consultation.objects.get(inquiry=inquiry).consultant is None


def test_replay_does_not_duplicate_assignment_consultation_or_history():
    consultant = create_demo_consultant()
    owner, inquiry = create_target_inquiry(sequence=5)
    prepare(inquiry)

    created = request_consultation(
        actor=owner,
        inquiry=inquiry,
        key="synthetic-e2e-replay-005",
    )
    replayed = request_consultation(
        actor=owner,
        inquiry=inquiry,
        key="synthetic-e2e-replay-005",
    )

    assert created.status_code == replayed.status_code == 200
    assert replayed.data["data"]["idempotent_replay"] is True
    inquiry.refresh_from_db()
    assert inquiry.assigned_user == consultant
    assert Consultation.objects.filter(inquiry=inquiry).count() == 1
    assert TransitionHistory.objects.filter(inquiry=inquiry).count() == 1
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="requestConsultation",
    ).count() == 1


def test_inactive_target_consultant_rolls_back_all_request_writes():
    consultant = create_demo_consultant()
    owner, inquiry = create_target_inquiry(sequence=6)
    prepare(inquiry)
    consultant.is_active = False
    consultant.save(update_fields=["is_active", "updated_at"])

    response = request_consultation(
        actor=owner,
        inquiry=inquiry,
        key="synthetic-e2e-inactive-consultant-006",
    )

    assert response.status_code == 500
    inquiry.refresh_from_db()
    assert inquiry.assigned_user is None
    assert inquiry.status_code == Inquiry.Status.AI_GUIDANCE
    assert inquiry.state_version == 3
    assert not Consultation.objects.filter(inquiry=inquiry).exists()
    assert not TransitionHistory.objects.filter(inquiry=inquiry).exists()
    assert not IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="requestConsultation",
    ).exists()


def test_existing_other_assignment_is_never_overwritten():
    create_demo_consultant()
    other_consultant = create_user(
        username="SYN-E2E-CONSULTANT-EXISTING",
        role=User.Role.CONSULTANT,
    )
    owner, inquiry = create_target_inquiry(sequence=7)
    prepare(inquiry)
    inquiry.assigned_user = other_consultant
    inquiry.assigned_role_code = Inquiry.AssignedRole.CONSULTANT
    inquiry.save(
        update_fields=["assigned_user", "assigned_role_code", "updated_at"]
    )

    response = request_consultation(
        actor=owner,
        inquiry=inquiry,
        key="synthetic-e2e-existing-assignment-007",
    )

    assert response.status_code == 409
    inquiry.refresh_from_db()
    assert inquiry.assigned_user == other_consultant
    assert inquiry.status_code == Inquiry.Status.AI_GUIDANCE
    assert inquiry.state_version == 3
    assert not Consultation.objects.filter(inquiry=inquiry).exists()
    assert not TransitionHistory.objects.filter(inquiry=inquiry).exists()
    assert not IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="requestConsultation",
    ).exists()


def test_late_failure_rolls_back_assignment_and_all_request_writes(
    monkeypatch,
):
    create_demo_consultant()
    owner, inquiry = create_target_inquiry(sequence=8)
    prepare(inquiry)

    def fail_completion(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("private-synthetic-e2e-late-error")

    monkeypatch.setattr(
        WorkflowRepository,
        "complete_idempotency_record",
        fail_completion,
    )
    response = request_consultation(
        actor=owner,
        inquiry=inquiry,
        key="synthetic-e2e-late-rollback-008",
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private-synthetic-e2e-late-error" not in response.content.decode()
    inquiry.refresh_from_db()
    assert inquiry.assigned_user is None
    assert inquiry.assigned_role_code == Inquiry.AssignedRole.NONE
    assert inquiry.status_code == Inquiry.Status.AI_GUIDANCE
    assert inquiry.state_version == 3
    assert not Consultation.objects.filter(inquiry=inquiry).exists()
    assert not TransitionHistory.objects.filter(inquiry=inquiry).exists()
    assert not IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="requestConsultation",
    ).exists()
