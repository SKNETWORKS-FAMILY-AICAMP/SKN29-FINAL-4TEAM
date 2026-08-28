"""CUSTOMER REQUEST_CONSULTATION Runtime and contract tests."""

from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import IdempotencyRecord, TransitionHistory


pytestmark = pytest.mark.django_db

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def create_user(*, sequence: int, role: str) -> User:
    return User.objects.create_user(
        username=f"REQUEST-CONSULTATION-{role}-{sequence:03d}",
        password=None,
        full_name=f"Request consultation {role} {sequence}",
        role_code=role,
        employee_no=(None if role == User.Role.CUSTOMER else f"RC-{sequence:03d}"),
        is_synthetic=True,
    )


def create_inquiry(
    *,
    sequence: int,
    status: str,
    state_version: int,
) -> tuple[User, Inquiry]:
    owner = create_user(sequence=sequence, role=User.Role.CUSTOMER)
    customer = CustomerProfile.objects.create(
        user=owner,
        customer_no=f"REQUEST-CONSULTATION-{sequence:03d}",
        customer_name=f"Synthetic request customer {sequence}",
        phone=f"010-1111-{sequence:04d}",
        is_synthetic=True,
    )
    product = ProductModel.objects.create(
        model_code=f"REQUEST-CONSULTATION-MODEL-{sequence:03d}",
        model_name=f"Synthetic request model {sequence}",
        is_supported_mvp=True,
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"REQUEST-CONSULTATION-CONTRACT-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"REQUEST-CONSULTATION-SERIAL-{sequence:03d}",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 8, 1),
    )
    inquiry = Inquiry.objects.create(
        subscription=subscription,
        initiated_by=owner,
        channel_code=Inquiry.Channel.MOBILE,
        raw_text="Synthetic customer requests a consultation.",
        status_code=status,
        state_version=state_version,
    )
    return owner, inquiry


def client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def endpoint(inquiry: Inquiry) -> str:
    return f"/api/v1/inquiries/{inquiry.public_id}/request-consultation"


def headers(*, key: str, correlation_id=None) -> dict[str, str]:
    return {
        "HTTP_IDEMPOTENCY_KEY": key,
        "HTTP_X_CORRELATION_ID": str(correlation_id or uuid4()),
    }


def test_request_from_ai_guidance_creates_waiting_consultation():
    owner, inquiry = create_inquiry(
        sequence=1,
        status=Inquiry.Status.AI_GUIDANCE,
        state_version=3,
    )
    correlation_id = uuid4()
    response = client_for(owner).post(
        endpoint(inquiry),
        {"state_version": 3},
        format="json",
        **headers(key="request-consultation-001", correlation_id=correlation_id),
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == str(correlation_id)
    assert response.data["metadata"]["correlation_id"] == str(correlation_id)
    data = response.data["data"]
    assert data["status"] == Inquiry.Status.CONSULTATION_REQUIRED
    assert data["state_version"] == 4
    assert data["idempotent_replay"] is False
    assert data["resource"] is None
    assert [item["code"] for item in data["allowed_actions"]] == [
        "REQUEST_CONSULTATION",
        "CANCEL_INQUIRY",
    ]

    inquiry.refresh_from_db()
    consultation = Consultation.objects.get(inquiry=inquiry)
    history = TransitionHistory.objects.get(inquiry=inquiry)
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 4
    assert consultation.sequence == 1
    assert consultation.consultant is None
    assert consultation.status == Consultation.Status.WAITING
    assert consultation.outcome == Consultation.Outcome.PENDING
    assert consultation.state_version == 4
    assert consultation.correlation_id == correlation_id
    assert consultation.data_classification == "synthetic"
    assert history.event_code == "REQUEST_CONSULTATION"
    assert history.from_state == Inquiry.Status.AI_GUIDANCE
    assert history.to_state == Inquiry.Status.CONSULTATION_REQUIRED
    assert history.state_version == 4


def test_same_key_replays_and_changed_request_conflicts():
    owner, inquiry = create_inquiry(
        sequence=2,
        status=Inquiry.Status.AI_GUIDANCE,
        state_version=3,
    )
    client = client_for(owner)
    request_headers = headers(key="request-consultation-replay-001")

    created = client.post(
        endpoint(inquiry),
        {"state_version": 3},
        format="json",
        **request_headers,
    )
    replayed = client.post(
        endpoint(inquiry),
        {"state_version": 3},
        format="json",
        **headers(key="request-consultation-replay-001"),
    )
    conflicted = client.post(
        endpoint(inquiry),
        {"state_version": 4},
        format="json",
        **headers(key="request-consultation-replay-001"),
    )

    assert created.status_code == replayed.status_code == 200
    assert created.data["data"]["idempotent_replay"] is False
    assert replayed.data["data"]["idempotent_replay"] is True
    assert created.data["data"]["state_version"] == 4
    assert replayed.data["data"]["state_version"] == 4
    assert conflicted.status_code == 409
    assert Consultation.objects.filter(inquiry=inquiry).count() == 1
    assert TransitionHistory.objects.filter(inquiry=inquiry).count() == 1
    assert IdempotencyRecord.objects.filter(
        operation_id="requestConsultation"
    ).count() == 1


def test_reconfirmation_reuses_the_waiting_consultation():
    owner, inquiry = create_inquiry(
        sequence=3,
        status=Inquiry.Status.CONSULTATION_REQUIRED,
        state_version=5,
    )
    client = client_for(owner)

    first = client.post(
        endpoint(inquiry),
        {"state_version": 5},
        format="json",
        **headers(key="request-consultation-confirm-001"),
    )
    second = client.post(
        endpoint(inquiry),
        {"state_version": 6},
        format="json",
        **headers(key="request-consultation-confirm-002"),
    )

    assert first.status_code == second.status_code == 200
    assert first.data["data"]["state_version"] == 6
    assert second.data["data"]["state_version"] == 7
    consultation = Consultation.objects.get(inquiry=inquiry)
    assert consultation.sequence == 1
    assert consultation.status == Consultation.Status.WAITING
    assert consultation.state_version == 7
    assert TransitionHistory.objects.filter(inquiry=inquiry).count() == 2


def test_completion_pending_re_request_creates_a_new_waiting_sequence():
    owner, inquiry = create_inquiry(
        sequence=4,
        status=Inquiry.Status.COMPLETION_PENDING,
        state_version=8,
    )
    consultant = create_user(sequence=40, role=User.Role.CONSULTANT)
    now = timezone.now()
    Consultation.objects.create(
        consultation_code=f"CONS-{uuid4().hex.upper()}",
        inquiry=inquiry,
        sequence=1,
        consultant=consultant,
        status=Consultation.Status.COMPLETED,
        outcome=Consultation.Outcome.COMPLETED_NO_VISIT,
        summary="Completed synthetic consultation.",
        state_version=8,
        idempotency_key="completed-consultation-001",
        correlation_id=uuid4(),
        created_at=now - timedelta(minutes=2),
        started_at=now - timedelta(minutes=1),
        completed_at=now,
        data_classification=Consultation.DataClassification.SYNTHETIC,
    )

    response = client_for(owner).post(
        endpoint(inquiry),
        {"state_version": 8},
        format="json",
        **headers(key="request-consultation-again-001"),
    )

    assert response.status_code == 200
    assert response.data["data"]["status"] == (
        Inquiry.Status.CONSULTATION_REQUIRED
    )
    assert response.data["data"]["state_version"] == 9
    consultations = list(
        Consultation.objects.filter(inquiry=inquiry).order_by("sequence")
    )
    assert [item.sequence for item in consultations] == [1, 2]
    assert consultations[0].status == Consultation.Status.COMPLETED
    assert consultations[1].status == Consultation.Status.WAITING
    assert consultations[1].consultant is None


def test_version_state_role_and_ownership_boundaries_fail_closed():
    owner, inquiry = create_inquiry(
        sequence=5,
        status=Inquiry.Status.AI_GUIDANCE,
        state_version=3,
    )
    other_owner, _ = create_inquiry(
        sequence=6,
        status=Inquiry.Status.AI_GUIDANCE,
        state_version=3,
    )
    consultant = create_user(sequence=50, role=User.Role.CONSULTANT)

    stale = client_for(owner).post(
        endpoint(inquiry),
        {"state_version": 2},
        format="json",
        **headers(key="request-consultation-stale-001"),
    )
    hidden = client_for(other_owner).post(
        endpoint(inquiry),
        {"state_version": 3},
        format="json",
        **headers(key="request-consultation-hidden-001"),
    )
    forbidden = client_for(consultant).post(
        endpoint(inquiry),
        {"state_version": 3},
        format="json",
        **headers(key="request-consultation-role-001"),
    )
    unauthenticated = APIClient().post(
        endpoint(inquiry),
        {"state_version": 3},
        format="json",
        **headers(key="request-consultation-auth-001"),
    )

    assert stale.status_code == 409
    assert stale.data["error"]["details"] == {
        "current_status": Inquiry.Status.AI_GUIDANCE,
        "current_state_version": 3,
        "allowed_actions": ["REQUEST_CONSULTATION"],
    }
    assert hidden.status_code == 404
    assert forbidden.status_code == 403
    assert unauthenticated.status_code == 401
    assert Consultation.objects.filter(inquiry=inquiry).count() == 0


def test_invalid_state_and_strict_payload_headers_return_safe_errors():
    owner, inquiry = create_inquiry(
        sequence=7,
        status=Inquiry.Status.DRAFT,
        state_version=1,
    )
    client = client_for(owner)

    invalid_state = client.post(
        endpoint(inquiry),
        {"state_version": 1},
        format="json",
        **headers(key="request-consultation-state-001"),
    )
    unknown = client.post(
        endpoint(inquiry),
        {"state_version": 1, "reason": "not contracted"},
        format="json",
        **headers(key="request-consultation-unknown-001"),
    )
    missing_idempotency = client.post(
        endpoint(inquiry),
        {"state_version": 1},
        format="json",
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )
    missing_correlation = client.post(
        endpoint(inquiry),
        {"state_version": 1},
        format="json",
        HTTP_IDEMPOTENCY_KEY="request-consultation-no-trace",
    )

    assert invalid_state.status_code == 409
    assert unknown.status_code == 422
    assert missing_idempotency.status_code == 422
    assert missing_correlation.status_code == 422
    assert Consultation.objects.filter(inquiry=inquiry).count() == 0


def test_openapi_and_action_crosswalk_publish_the_runtime():
    workflow = yaml.safe_load(
        (
            REPOSITORY_ROOT
            / "contracts/api/paths/workflow.yaml"
        ).read_text(encoding="utf-8")
    )
    operation = workflow[
        "/inquiries/{id}/request-consultation"
    ]["post"]
    assert operation["x-runtime-status"] == "IMPLEMENTED"
    assert operation["x-state-machine"] == {
        "event": "REQUEST_CONSULTATION",
        "transition_rules": ["TR-INQ-012", "TR-INQ-013", "TR-INQ-031"],
        "from_states": [
            "AI_GUIDANCE",
            "CONSULTATION_REQUIRED",
            "COMPLETION_PENDING",
        ],
        "to_state": "CONSULTATION_REQUIRED",
        "actor_role": "CUSTOMER",
    }

    crosswalk = yaml.safe_load(
        (
            REPOSITORY_ROOT
            / "contracts/api/action-operation-crosswalk.yaml"
        ).read_text(encoding="utf-8")
    )
    item = next(
        entry
        for entry in crosswalk["actions"]
        if entry["action"] == "REQUEST_CONSULTATION"
    )
    assert item["classification"] == "RUNTIME_IMPLEMENTED"
    assert item["runtime"]["implemented"] is True
    assert crosswalk["summary"]["RUNTIME_IMPLEMENTED"] == 18
    assert crosswalk["summary"]["OPENAPI_CONFIRMED"] == 2
