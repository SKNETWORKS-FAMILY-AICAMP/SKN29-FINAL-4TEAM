"""PM-approved unassigned consultation queue and atomic Claim checks."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import IdempotencyRecord, TransitionHistory
from apps.workflow.repositories.workflow_repository import WorkflowRepository


pytestmark = pytest.mark.django_db

QUEUE_PATH = "/api/v1/inquiries/unassigned-consultations"


def create_user(sequence: int, *, role: str, synthetic: bool = True) -> User:
    user = User.objects.create_user(
        username=f"CLAIM-{role}-{sequence:03d}",
        password=None,
        full_name=f"Claim {role} {sequence}",
        role_code=role,
        employee_no=(
            None if role == User.Role.CUSTOMER else f"CLAIM-EMP-{sequence:03d}"
        ),
        is_active=True,
        is_synthetic=synthetic,
    )
    if role == User.Role.CUSTOMER:
        CustomerProfile.objects.create(
            user=user,
            customer_no=f"CLAIM-CUSTOMER-{sequence:03d}",
            customer_name=f"합성 Claim 고객 {sequence}",
            phone=f"010-9000-{sequence:04d}",
            address_line1="미배정 대기열에 노출하면 안 되는 주소",
            # The current CustomerProfile schema is synthetic-only. A
            # non-synthetic User still proves that the queue's double marker
            # guard conceals mixed-classification rows.
            is_synthetic=True,
        )
    return user


def create_queue_item(
    sequence: int,
    *,
    owner: User | None = None,
    status: str = Inquiry.Status.CONSULTATION_REQUIRED,
    assigned_consultant: User | None = None,
    consultation_status: str = Consultation.Status.WAITING,
    consultation_consultant: User | None = None,
) -> tuple[Inquiry, Consultation]:
    owner = owner or create_user(sequence, role=User.Role.CUSTOMER)
    product = ProductModel.objects.create(
        model_code=f"CLAIM-MODEL-{sequence:03d}",
        model_name=f"Claim 제품 {sequence}",
        features={"secret_detail": "must-not-leak"},
        is_supported_mvp=True,
        is_active=True,
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"CLAIM-CONTRACT-{sequence:03d}",
        customer=owner.customer_profile,
        product_model=product,
        serial_no=f"CLAIM-SERIAL-{sequence:03d}",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 8, 1),
        installation_address="미배정 대기열에 노출하면 안 되는 설치 주소",
    )
    inquiry = Inquiry.objects.create(
        inquiry_code=f"CLAIM-INQ-{sequence:03d}",
        subscription=subscription,
        initiated_by=owner,
        assigned_user=assigned_consultant,
        assigned_role_code=(
            Inquiry.AssignedRole.CONSULTANT
            if assigned_consultant is not None
            else Inquiry.AssignedRole.NONE
        ),
        channel_code=Inquiry.Channel.MOBILE,
        raw_text=f"합성 미배정 상담 문의 {sequence}",
        risk_level_code=Inquiry.RiskLevel.CAUTION,
        priority_code=Inquiry.Priority.HIGH,
        status_code=status,
        state_version=4,
    )
    started_at = None
    if consultation_status == Consultation.Status.IN_PROGRESS:
        from django.utils import timezone

        started_at = timezone.now()
    consultation = Consultation.objects.create(
        consultation_code=f"CLAIM-CONSULTATION-{sequence:03d}",
        inquiry=inquiry,
        sequence=1,
        consultant=consultation_consultant,
        status=consultation_status,
        outcome=Consultation.Outcome.PENDING,
        state_version=4,
        idempotency_key=f"claim-request-{sequence:03d}",
        correlation_id=uuid4(),
        started_at=started_at,
        data_classification=(
            Consultation.DataClassification.SYNTHETIC
            if owner.is_synthetic
            else Consultation.DataClassification.OPERATIONAL
        ),
    )
    return inquiry, consultation


def client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def claim(
    *,
    actor: User,
    inquiry: Inquiry,
    state_version: int = 4,
    key: str = "claim-consultation-key",
    correlation_id=None,
):
    return client_for(actor).post(
        f"/api/v1/inquiries/{inquiry.public_id}/claim-consultation",
        {"state_version": state_version},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
        HTTP_X_CORRELATION_ID=str(correlation_id or uuid4()),
    )


def test_unassigned_queue_returns_only_claimable_synthetic_projection():
    consultant = create_user(1, role=User.Role.CONSULTANT)
    other_consultant = create_user(2, role=User.Role.CONSULTANT)
    visible, _ = create_queue_item(10)
    assigned, _ = create_queue_item(
        11,
        assigned_consultant=other_consultant,
        consultation_status=Consultation.Status.ASSIGNED,
        consultation_consultant=other_consultant,
    )
    wrong_state, _ = create_queue_item(
        12,
        status=Inquiry.Status.AI_GUIDANCE,
    )
    real_owner = create_user(
        13,
        role=User.Role.CUSTOMER,
        synthetic=False,
    )
    nonsynthetic, _ = create_queue_item(13, owner=real_owner)

    response = client_for(consultant).get(QUEUE_PATH)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["page_info"] == {"page": 1, "size": 20, "total": 1}
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["inquiry_id"] == str(visible.public_id)
    assert item["status"] == Inquiry.Status.CONSULTATION_REQUIRED
    assert item["state_version"] == 4
    assert item["current_assignee_type"] == "NONE"
    assert [action["code"] for action in item["allowed_actions"]] == [
        "CLAIM_CONSULTATION"
    ]
    serialized = str(item)
    for secret in (
        visible.subscription.contract_no,
        visible.subscription.serial_no,
        visible.subscription.installation_address,
        visible.subscription.customer.address_line1,
        "secret_detail",
        str(assigned.public_id),
        str(wrong_state.public_id),
        str(nonsynthetic.public_id),
    ):
        assert secret not in serialized

    assigned_list = client_for(consultant).get("/api/v1/inquiries")
    assert assigned_list.status_code == 200
    assert assigned_list.json()["data"]["items"] == []


def test_queue_auth_role_and_query_boundaries():
    consultant = create_user(20, role=User.Role.CONSULTANT)
    customer = create_user(21, role=User.Role.CUSTOMER)

    assert APIClient().get(QUEUE_PATH).status_code == 401
    assert client_for(customer).get(QUEUE_PATH).status_code == 403

    consultant.is_active = False
    consultant.save(update_fields=["is_active", "updated_at"])
    assert client_for(consultant).get(QUEUE_PATH).status_code == 403
    consultant.is_active = True
    consultant.save(update_fields=["is_active", "updated_at"])

    client = client_for(consultant)
    for query in (
        {"status": Inquiry.Status.CONSULTATION_REQUIRED},
        {"assignee": "NONE"},
        {"page": 0},
        {"size": 101},
        {"risk_level": "unknown"},
        {"priority": "CRITICAL"},
        {"sort": "UNKNOWN"},
        {"from": "2026-08-10", "to": "2026-08-09"},
    ):
        response = client.get(QUEUE_PATH, query)
        assert response.status_code == 422, query
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_claim_assigns_both_rows_without_starting_consultation():
    consultant = create_user(30, role=User.Role.CONSULTANT)
    inquiry, consultation = create_queue_item(30)
    correlation_id = uuid4()

    response = claim(
        actor=consultant,
        inquiry=inquiry,
        key="claim-success-030",
        correlation_id=correlation_id,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["inquiry_id"] == str(inquiry.public_id)
    assert data["status"] == Inquiry.Status.CONSULTATION_REQUIRED
    assert data["state_version"] == 5
    assert data["idempotent_replay"] is False
    assert data["resource"] is None
    assert [action["code"] for action in data["allowed_actions"]] == [
        "START_CONSULTATION"
    ]

    inquiry.refresh_from_db()
    consultation.refresh_from_db()
    assert inquiry.assigned_user == consultant
    assert inquiry.assigned_role_code == Inquiry.AssignedRole.CONSULTANT
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 5
    assert consultation.consultant == consultant
    assert consultation.status == Consultation.Status.ASSIGNED
    assert consultation.state_version == 5
    assert consultation.started_at is None
    assert consultation.completed_at is None
    assert consultation.correlation_id == correlation_id

    history = TransitionHistory.objects.get(
        inquiry=inquiry,
        event_code="CLAIM_CONSULTATION",
    )
    assert history.from_state == Inquiry.Status.CONSULTATION_REQUIRED
    assert history.to_state == Inquiry.Status.CONSULTATION_REQUIRED
    assert history.state_version == 5
    assert history.actor == consultant
    assert history.correlation_id == correlation_id
    assert IdempotencyRecord.objects.filter(
        actor=consultant,
        operation_id="claimConsultation",
        idempotency_key="claim-success-030",
    ).count() == 1

    queue = client_for(consultant).get(QUEUE_PATH)
    assigned_list = client_for(consultant).get("/api/v1/inquiries")
    detail = client_for(consultant).get(
        f"/api/v1/inquiries/{inquiry.public_id}"
    )
    assert (
        queue.status_code
        == assigned_list.status_code
        == detail.status_code
        == 200
    )
    assert queue.json()["data"]["items"] == []
    assert [
        item["inquiry_id"]
        for item in assigned_list.json()["data"]["items"]
    ] == [str(inquiry.public_id)]


def test_claim_replay_and_same_key_different_payload_conflict():
    consultant = create_user(40, role=User.Role.CONSULTANT)
    inquiry, _consultation = create_queue_item(40)
    key = "claim-replay-040"

    created = claim(actor=consultant, inquiry=inquiry, key=key)
    replayed = claim(actor=consultant, inquiry=inquiry, key=key)
    conflicted = claim(
        actor=consultant,
        inquiry=inquiry,
        state_version=5,
        key=key,
    )

    assert created.status_code == replayed.status_code == 200
    assert replayed.json()["data"]["idempotent_replay"] is True
    assert conflicted.status_code == 409
    assert conflicted.json()["error"]["code"] == "DUPLICATE-EVENT-01"
    inquiry.refresh_from_db()
    assert inquiry.state_version == 5
    assert TransitionHistory.objects.filter(
        inquiry=inquiry,
        event_code="CLAIM_CONSULTATION",
    ).count() == 1
    assert IdempotencyRecord.objects.filter(
        actor=consultant,
        operation_id="claimConsultation",
    ).count() == 1


def test_claim_stale_version_returns_current_snapshot_without_writes():
    consultant = create_user(50, role=User.Role.CONSULTANT)
    inquiry, consultation = create_queue_item(50)

    response = claim(
        actor=consultant,
        inquiry=inquiry,
        state_version=3,
        key="claim-stale-050",
    )

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "STATE-CONFLICT-01"
    assert error["details"] == {
        "current_status": Inquiry.Status.CONSULTATION_REQUIRED,
        "current_state_version": 4,
        "allowed_actions": ["CLAIM_CONSULTATION"],
    }
    inquiry.refresh_from_db()
    consultation.refresh_from_db()
    assert inquiry.assigned_user is None
    assert inquiry.state_version == 4
    assert consultation.consultant is None
    assert consultation.status == Consultation.Status.WAITING
    assert not TransitionHistory.objects.filter(inquiry=inquiry).exists()
    assert not IdempotencyRecord.objects.filter(
        operation_id="claimConsultation"
    ).exists()


def test_claim_conceals_nonclaimable_objects_and_rejects_bad_actor_or_input():
    consultant = create_user(60, role=User.Role.CONSULTANT)
    other_consultant = create_user(61, role=User.Role.CONSULTANT)
    customer = create_user(62, role=User.Role.CUSTOMER)
    inquiry, _consultation = create_queue_item(60)
    path = f"/api/v1/inquiries/{inquiry.public_id}/claim-consultation"

    unauthenticated = APIClient().post(
        path,
        {"state_version": 4},
        format="json",
    )
    assert unauthenticated.status_code == 401
    assert claim(actor=customer, inquiry=inquiry).status_code == 403
    missing_headers = client_for(consultant).post(
        path,
        {"state_version": 4},
        format="json",
    )
    assert missing_headers.status_code == 422
    unknown_query = client_for(consultant).post(
        f"{path}?unexpected=1",
        {"state_version": 4},
        format="json",
        HTTP_IDEMPOTENCY_KEY="claim-unknown-query",
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )
    assert unknown_query.status_code == 422

    assert claim(
        actor=consultant,
        inquiry=inquiry,
        key="claim-winner-060",
    ).status_code == 200
    other_inquiry, _other_consultation = create_queue_item(63)
    assert claim(
        actor=other_consultant,
        inquiry=other_inquiry,
        key="claim-other-winner-063",
    ).status_code == 200
    lost = claim(
        actor=other_consultant,
        inquiry=inquiry,
        state_version=5,
        key="claim-loser-060",
    )
    missing = client_for(other_consultant).post(
        f"/api/v1/inquiries/{uuid4()}/claim-consultation",
        {"state_version": 4},
        format="json",
        HTTP_IDEMPOTENCY_KEY="claim-missing-060",
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )
    assert lost.status_code == missing.status_code == 404
    assert lost.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert missing.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    cross_target_key_reuse = claim(
        actor=consultant,
        inquiry=other_inquiry,
        state_version=5,
        key="claim-winner-060",
    )
    assert cross_target_key_reuse.status_code == 404
    assert (
        cross_target_key_reuse.json()["error"]["code"]
        == "RESOURCE_NOT_FOUND"
    )


def test_claim_late_failure_rolls_back_assignment_history_and_idempotency(
    monkeypatch,
):
    consultant = create_user(70, role=User.Role.CONSULTANT)
    inquiry, consultation = create_queue_item(70)

    def fail_completion(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("private-claim-late-error")

    monkeypatch.setattr(
        WorkflowRepository,
        "complete_idempotency_record",
        fail_completion,
    )
    response = claim(
        actor=consultant,
        inquiry=inquiry,
        key="claim-late-rollback-070",
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private-claim-late-error" not in response.content.decode()
    inquiry.refresh_from_db()
    consultation.refresh_from_db()
    assert inquiry.assigned_user is None
    assert inquiry.assigned_role_code == Inquiry.AssignedRole.NONE
    assert inquiry.state_version == 4
    assert consultation.consultant is None
    assert consultation.status == Consultation.Status.WAITING
    assert consultation.state_version == 4
    assert not TransitionHistory.objects.filter(inquiry=inquiry).exists()
    assert not IdempotencyRecord.objects.filter(
        operation_id="claimConsultation"
    ).exists()


def test_claim_and_start_consultation_remain_two_separate_actions():
    consultant = create_user(80, role=User.Role.CONSULTANT)
    inquiry, consultation = create_queue_item(80)

    claimed = claim(
        actor=consultant,
        inquiry=inquiry,
        key="claim-before-start-080",
    )

    assert claimed.status_code == 200
    inquiry.refresh_from_db()
    consultation.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 5
    assert consultation.status == Consultation.Status.ASSIGNED
    assert consultation.started_at is None

    started = client_for(consultant).post(
        f"/api/v1/inquiries/{inquiry.public_id}/start-consultation",
        {"state_version": 5},
        format="json",
        HTTP_IDEMPOTENCY_KEY="start-after-claim-080",
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )

    assert started.status_code == 200
    inquiry.refresh_from_db()
    consultation.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_IN_PROGRESS
    assert inquiry.state_version == 6
    assert consultation.status == Consultation.Status.IN_PROGRESS
    assert consultation.state_version == 6
    assert consultation.started_at is not None
    assert list(
        TransitionHistory.objects.filter(inquiry=inquiry)
        .order_by("state_version")
        .values_list("event_code", flat=True)
    ) == ["CLAIM_CONSULTATION", "START_CONSULTATION"]
