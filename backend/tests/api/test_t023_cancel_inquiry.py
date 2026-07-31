"""Runtime and contract parity tests for representative CANCEL_INQUIRY."""

from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
import yaml
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.api.serializers import CancelInquirySerializer
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import IdempotencyRecord, TransitionHistory
from apps.workflow.repositories.workflow_repository import (
    WorkflowRepository,
)


pytestmark = pytest.mark.django_db
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CANCELLATION_CODES_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "codes"
    / "inquiry-cancellation-reasons.yaml"
)
CANCEL_REQUEST_SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "api"
    / "components"
    / "schemas"
    / "workflow"
    / "CancelInquiryRequest.yaml"
)
WORKFLOW_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "api"
    / "paths"
    / "workflow.yaml"
)


def create_user(sequence: int, *, role: str = "CUSTOMER") -> User:
    employee_no = (
        None
        if role == User.Role.CUSTOMER
        else f"T023-EMP-{sequence:03d}"
    )
    user = User.objects.create_user(
        username=f"T023-{role}-{sequence:03d}",
        password=None,
        full_name=f"T023 {role} {sequence}",
        role_code=role,
        employee_no=employee_no,
    )
    if role == User.Role.CUSTOMER:
        CustomerProfile.objects.create(
            user=user,
            customer_no=f"T023-CUS-{sequence:03d}",
            customer_name=f"T023 customer {sequence}",
        )
    return user


def create_subscription(
    owner: User,
    sequence: int,
) -> CustomerSubscription:
    product = ProductModel.objects.create(
        model_code=f"T023-PMD-{sequence:03d}",
        model_name=f"T023 product {sequence}",
    )
    return CustomerSubscription.objects.create(
        contract_no=f"T023-SUB-{sequence:03d}",
        customer=owner.customer_profile,
        product_model=product,
        serial_no=f"T023-SERIAL-{sequence:03d}",
        started_on=date(2026, 7, 1),
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def create_inquiry(
    owner: User,
    sequence: int,
) -> tuple[APIClient, Inquiry]:
    subscription = create_subscription(owner, sequence)
    client = authenticated_client(owner)
    response = client.post(
        "/api/v1/inquiries",
        {
            "subscription_id": str(subscription.public_id),
            "channel_code": "WEB",
            "raw_text": "Cancel-flow inquiry",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"t023-start-{sequence}",
    )
    assert response.status_code == 201
    inquiry = Inquiry.objects.get(
        public_id=response.json()["data"]["inquiry_id"]
    )
    return client, inquiry


def cancel_body(
    *,
    state_version: int = 1,
    reason_code: str = "CUSTOMER_REQUEST",
    reason_detail: str | None = "No longer needed",
) -> dict:
    return {
        "state_version": state_version,
        "reason_code": reason_code,
        "reason_detail": reason_detail,
    }


def post_cancel(
    client: APIClient,
    inquiry: Inquiry,
    body: dict,
    *,
    key: str | None,
):
    headers = (
        {"HTTP_IDEMPOTENCY_KEY": key}
        if key is not None
        else {}
    )
    return client.post(
        f"/api/v1/inquiries/{inquiry.public_id}/cancel",
        body,
        format="json",
        **headers,
    )


def test_cancel_draft_inquiry_updates_state_reason_and_history():
    owner = create_user(1)
    client, inquiry = create_inquiry(owner, 1)

    response = post_cancel(
        client,
        inquiry,
        cancel_body(reason_detail="  Customer changed plans.  "),
        key="t023-cancel-success",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] is None
    assert payload["data"] == {
        "inquiry_id": str(inquiry.public_id),
        "state": "CANCELLED",
        "state_version": 2,
        "idempotent_replay": False,
    }
    assert UUID(payload["data"]["inquiry_id"])

    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CANCELLED
    assert inquiry.state_version == 2
    assert inquiry.cancelled_at is not None
    assert inquiry.cancellation_reason_code == "CUSTOMER_REQUEST"
    assert inquiry.cancellation_reason_detail == "Customer changed plans."

    history = list(
        TransitionHistory.objects.filter(inquiry=inquiry)
        .order_by("state_version")
        .values_list(
            "event_code",
            "from_state",
            "to_state",
            "state_version",
        )
    )
    assert history == [
        ("START_INQUIRY", None, "DRAFT", 1),
        ("CANCEL_INQUIRY", "DRAFT", "CANCELLED", 2),
    ]
    cancel_record = IdempotencyRecord.objects.get(
        actor=owner,
        operation_id="cancelInquiry",
        idempotency_key="t023-cancel-success",
    )
    assert cancel_record.response_status == 200
    assert cancel_record.resource_public_id == inquiry.public_id
    assert "id" not in cancel_record.response_body


def test_same_key_same_stale_body_replays_before_version_check():
    owner = create_user(2)
    client, inquiry = create_inquiry(owner, 2)
    body = cancel_body(state_version=1)

    first = post_cancel(
        client,
        inquiry,
        body,
        key="t023-replay",
    )
    second = post_cancel(
        client,
        inquiry,
        body,
        key="t023-replay",
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["idempotent_replay"] is False
    assert second.json()["data"]["idempotent_replay"] is True
    assert second.json()["data"]["inquiry_id"] == (
        first.json()["data"]["inquiry_id"]
    )
    inquiry.refresh_from_db()
    assert inquiry.state_version == 2
    assert TransitionHistory.objects.filter(inquiry=inquiry).count() == 2
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="cancelInquiry",
    ).count() == 1


def test_same_key_different_hash_beats_already_changed_state():
    owner = create_user(3)
    client, inquiry = create_inquiry(owner, 3)

    first = post_cancel(
        client,
        inquiry,
        cancel_body(),
        key="t023-different-hash",
    )
    second = post_cancel(
        client,
        inquiry,
        cancel_body(reason_code="DUPLICATE_INQUIRY"),
        key="t023-different-hash",
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"] == {
        "code": "DUPLICATE-EVENT-01",
        "message": "동일 Idempotency-Key가 다른 요청에 재사용되었습니다.",
        "details": {},
    }
    inquiry.refresh_from_db()
    assert inquiry.state_version == 2
    assert TransitionHistory.objects.filter(inquiry=inquiry).count() == 2


def test_new_key_stale_version_returns_current_draft_snapshot():
    owner = create_user(4)
    client, inquiry = create_inquiry(owner, 4)

    response = post_cancel(
        client,
        inquiry,
        cancel_body(state_version=2),
        key="t023-stale-new-key",
    )

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "STATE-CONFLICT-01",
        "message": "다른 사용자가 문의 상태를 먼저 변경했습니다.",
        "details": {
            "current_status": "DRAFT",
            "current_state_version": 1,
            "allowed_actions": [
                "SUBMIT_SYMPTOM",
                "CANCEL_INQUIRY",
            ],
        },
    }
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.DRAFT
    assert inquiry.state_version == 1
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="cancelInquiry",
    ).count() == 0


def test_new_key_on_cancelled_inquiry_returns_terminal_snapshot():
    owner = create_user(5)
    client, inquiry = create_inquiry(owner, 5)
    first = post_cancel(
        client,
        inquiry,
        cancel_body(),
        key="t023-first-cancel",
    )

    second = post_cancel(
        client,
        inquiry,
        cancel_body(state_version=2),
        key="t023-second-cancel",
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "STATE-CONFLICT-01"
    assert second.json()["error"]["details"] == {
        "current_status": "CANCELLED",
        "current_state_version": 2,
        "allowed_actions": [],
    }
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="cancelInquiry",
    ).count() == 1
    assert TransitionHistory.objects.filter(inquiry=inquiry).count() == 2


def test_cancel_owner_scope_and_role_are_enforced():
    owner = create_user(6)
    _owner_client, inquiry = create_inquiry(owner, 6)
    other_customer = create_user(7)
    consultant = create_user(8, role=User.Role.CONSULTANT)

    owner_scope_response = post_cancel(
        authenticated_client(other_customer),
        inquiry,
        cancel_body(),
        key="t023-owner-scope",
    )
    role_response = post_cancel(
        authenticated_client(consultant),
        inquiry,
        cancel_body(),
        key="t023-role",
    )

    assert owner_scope_response.status_code == 404
    assert owner_scope_response.json()["error"]["code"] == (
        "RESOURCE_NOT_FOUND"
    )
    assert role_response.status_code == 403
    assert role_response.json()["error"]["code"] == "FORBIDDEN"
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.DRAFT


def test_cancel_rejects_missing_header_and_unknown_reason():
    owner = create_user(9)
    client, inquiry = create_inquiry(owner, 9)

    missing_header = post_cancel(
        client,
        inquiry,
        cancel_body(),
        key=None,
    )
    invalid_reason = post_cancel(
        client,
        inquiry,
        cancel_body(reason_code="NOT_A_REASON"),
        key="t023-invalid-reason",
    )

    assert missing_header.status_code == 422
    assert invalid_reason.status_code == 422
    assert missing_header.json()["error"]["code"] == "VALIDATION_ERROR"
    assert invalid_reason.json()["error"]["code"] == "VALIDATION_ERROR"
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.DRAFT
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="cancelInquiry",
    ).count() == 0


def test_cancel_rolls_back_state_history_and_idempotency_on_late_failure(
    monkeypatch,
):
    owner = create_user(10)
    client, inquiry = create_inquiry(owner, 10)

    def fail_completion(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("private-database-error")

    monkeypatch.setattr(
        WorkflowRepository,
        "complete_idempotency_record",
        fail_completion,
    )
    response = post_cancel(
        client,
        inquiry,
        cancel_body(),
        key="t023-rollback",
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private-database-error" not in response.content.decode("utf-8")
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.DRAFT
    assert inquiry.state_version == 1
    assert inquiry.cancelled_at is None
    assert inquiry.cancellation_reason_code is None
    assert TransitionHistory.objects.filter(inquiry=inquiry).count() == 1
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="cancelInquiry",
    ).count() == 0


def test_cancellation_code_contract_serializer_and_openapi_are_identical():
    code_contract = yaml.safe_load(
        CANCELLATION_CODES_PATH.read_text(encoding="utf-8")
    )
    request_schema = yaml.safe_load(
        CANCEL_REQUEST_SCHEMA_PATH.read_text(encoding="utf-8")
    )
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    serializer = CancelInquirySerializer()
    serializer_codes = list(
        serializer.fields["reason_code"].choices.keys()
    )

    assert code_contract["status"] == "OWNER_BASELINE"
    assert code_contract["owner"] == "BACKEND"
    assert code_contract["codes"] == [
        "CUSTOMER_REQUEST",
        "DUPLICATE_INQUIRY",
        "ISSUE_RESOLVED",
        "OTHER",
    ]
    assert Inquiry.CancellationReason.values == code_contract["codes"]
    assert serializer_codes == code_contract["codes"]
    assert request_schema["properties"]["reason_code"]["enum"] == (
        code_contract["codes"]
    )
    assert request_schema["properties"]["reason_code"][
        "x-code-contract"
    ].endswith("inquiry-cancellation-reasons.yaml")
    operation = workflow["/inquiries/{id}/cancel"]["post"]
    assert set(operation["responses"]) == {
        "200",
        "400",
        "401",
        "403",
        "404",
        "409",
        "422",
    }
