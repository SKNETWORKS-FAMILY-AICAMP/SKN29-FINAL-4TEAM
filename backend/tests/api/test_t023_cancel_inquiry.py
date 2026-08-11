"""Runtime and contract parity tests for representative CANCEL_INQUIRY."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Barrier, local
from unittest.mock import patch
from uuid import UUID

import pytest
import yaml
from django.contrib.auth.models import Permission
from django.db import connection, connections
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.api.serializers import (
    CancelInquiryResponseSerializer,
    CancelInquirySerializer,
)
from apps.inquiries.models import Inquiry
from apps.inquiries.repositories.inquiry_repository import InquiryRepository
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
        "allowed_actions": [],
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
            "change_reason",
        )
    )
    assert history == [
        ("START_INQUIRY", None, "DRAFT", 1, None),
        (
            "CANCEL_INQUIRY",
            "DRAFT",
            "CANCELLED",
            2,
            "CUSTOMER_REQUEST | Customer changed plans.",
        ),
    ]
    cancel_history = TransitionHistory.objects.get(
        inquiry=inquiry,
        event_code="CANCEL_INQUIRY",
    )
    assert cancel_history.actor == owner
    assert str(cancel_history.correlation_id) == payload["metadata"][
        "correlation_id"
    ]
    assert cancel_history.idempotency_key == "t023-cancel-success"
    cancel_record = IdempotencyRecord.objects.get(
        actor=owner,
        operation_id="cancelInquiry",
        idempotency_key="t023-cancel-success",
    )
    assert cancel_record.response_status == 200
    assert cancel_record.resource_public_id == inquiry.public_id
    assert "id" not in cancel_record.response_body


@pytest.mark.parametrize(
    "reason_detail",
    [None, "", "   ", "__OMITTED__"],
)
def test_cancel_history_uses_reason_code_without_separator_when_detail_empty(
    reason_detail,
):
    owner = create_user(101)
    client, inquiry = create_inquiry(owner, 101)

    body = cancel_body(reason_detail=reason_detail)
    if reason_detail == "__OMITTED__":
        body.pop("reason_detail")
    response = post_cancel(
        client,
        inquiry,
        body,
        key=f"t023-empty-reason-{reason_detail!r}",
    )

    assert response.status_code == 200
    history = TransitionHistory.objects.get(
        inquiry=inquiry,
        event_code="CANCEL_INQUIRY",
    )
    assert history.change_reason == "CUSTOMER_REQUEST"


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
    assert TransitionHistory.objects.get(
        inquiry=inquiry,
        event_code="CANCEL_INQUIRY",
    ).change_reason == "CUSTOMER_REQUEST | No longer needed"
    assert TransitionHistory.objects.get(
        inquiry=inquiry,
        event_code="CANCEL_INQUIRY",
    ).change_reason == "CUSTOMER_REQUEST | No longer needed"
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


def test_cancel_owner_scope_and_unsupported_role_are_enforced():
    owner = create_user(6)
    _owner_client, inquiry = create_inquiry(owner, 6)
    other_customer = create_user(7)
    non_customer = create_user(8, role=User.Role.TECHNICIAN)

    owner_scope_response = post_cancel(
        authenticated_client(other_customer),
        inquiry,
        cancel_body(),
        key="t023-owner-scope",
    )
    role_response = post_cancel(
        authenticated_client(non_customer),
        inquiry,
        cancel_body(),
        key="t023-role-technician",
    )

    assert owner_scope_response.status_code == 404
    assert owner_scope_response.json()["error"]["code"] == (
        "RESOURCE_NOT_FOUND"
    )
    assert role_response.status_code == 403
    assert role_response.json()["error"]["code"] == "FORBIDDEN"
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.DRAFT
    assert TransitionHistory.objects.filter(inquiry=inquiry).count() == 1
    assert not IdempotencyRecord.objects.filter(
        resource_public_id=inquiry.public_id,
        operation_id="cancelInquiry",
    ).exists()


@pytest.mark.parametrize(
    "initial_state,initial_version",
    [
        (Inquiry.Status.DRAFT, 1),
        (Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS, 2),
    ],
)
@pytest.mark.parametrize("actor_kind", ["OWNER", "CONSULTANT", "OPERATOR"])
def test_cancel_supports_all_approved_roles_and_states(
    initial_state,
    initial_version,
    actor_kind,
):
    owner = create_user(90 + initial_version)
    _owner_client, inquiry = create_inquiry(owner, 90 + initial_version)
    actor = owner
    if actor_kind == "CONSULTANT":
        actor = create_user(100 + initial_version, role=User.Role.CONSULTANT)
        inquiry.assigned_user = actor
        inquiry.assigned_role_code = Inquiry.AssignedRole.CONSULTANT
    elif actor_kind == "OPERATOR":
        actor = create_user(110 + initial_version, role=User.Role.OPERATOR)
        actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="inquiries",
                codename="cancel_inquiry",
            )
        )

    inquiry.status_code = initial_state
    inquiry.state_version = initial_version
    inquiry.save(
        update_fields=[
            "assigned_user",
            "assigned_role_code",
            "status_code",
            "state_version",
            "updated_at",
        ]
    )

    response = post_cancel(
        authenticated_client(actor),
        inquiry,
        cancel_body(state_version=initial_version),
        key=f"t023-approved-{actor_kind.lower()}-{initial_version}",
    )

    assert response.status_code == 200, response.json()
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CANCELLED
    assert inquiry.state_version == initial_version + 1
    cancel_history = TransitionHistory.objects.get(
        inquiry=inquiry,
        event_code="CANCEL_INQUIRY",
    )
    assert cancel_history.from_state == initial_state
    assert cancel_history.to_state == Inquiry.Status.CANCELLED
    assert cancel_history.state_version == initial_version + 1


def test_cancel_rejects_unassigned_consultant_and_unprivileged_operator():
    owner = create_user(120)
    _owner_client, inquiry = create_inquiry(owner, 120)
    consultant = create_user(121, role=User.Role.CONSULTANT)
    operator = create_user(122, role=User.Role.OPERATOR)

    unassigned = post_cancel(
        authenticated_client(consultant),
        inquiry,
        cancel_body(),
        key="t023-unassigned-consultant",
    )
    unprivileged = post_cancel(
        authenticated_client(operator),
        inquiry,
        cancel_body(),
        key="t023-unprivileged-operator",
    )

    assert unassigned.status_code == 404
    assert unassigned.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert unprivileged.status_code == 403
    assert unprivileged.json()["error"]["code"] == "FORBIDDEN"
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.DRAFT
    assert inquiry.state_version == 1


def test_anonymous_cancel_is_rejected_without_side_effects():
    owner = create_user(81)
    _owner_client, inquiry = create_inquiry(owner, 81)

    response = post_cancel(
        APIClient(),
        inquiry,
        cancel_body(),
        key="t023-anonymous",
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.DRAFT
    assert TransitionHistory.objects.filter(inquiry=inquiry).count() == 1
    assert not IdempotencyRecord.objects.filter(
        resource_public_id=inquiry.public_id,
        operation_id="cancelInquiry",
    ).exists()


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
    assert inquiry.cancellation_reason_detail is None
    assert TransitionHistory.objects.filter(inquiry=inquiry).count() == 1
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="cancelInquiry",
    ).count() == 0


def test_cancel_rolls_back_when_response_serialization_fails(monkeypatch):
    owner = create_user(11)
    client, inquiry = create_inquiry(owner, 11)

    def fail_serialization(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("private-response-serialization-error")

    monkeypatch.setattr(
        CancelInquiryResponseSerializer,
        "to_representation",
        fail_serialization,
    )

    response = post_cancel(
        client,
        inquiry,
        cancel_body(),
        key="t023-response-rollback",
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private-response-serialization-error" not in response.content.decode(
        "utf-8"
    )
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.DRAFT
    assert inquiry.state_version == 1
    assert inquiry.cancelled_at is None
    assert inquiry.cancellation_reason_code is None
    assert inquiry.cancellation_reason_detail is None
    assert TransitionHistory.objects.filter(inquiry=inquiry).count() == 1
    assert not IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="cancelInquiry",
        idempotency_key="t023-response-rollback",
    ).exists()


def concurrent_cancel(
    *,
    actor_id: int,
    inquiry_id: UUID,
    state_version: int,
    key: str,
    barrier: Barrier,
) -> tuple[int, dict]:
    connections.close_all()
    try:
        actor = User.objects.get(pk=actor_id)
        client = authenticated_client(actor)
        barrier.wait(timeout=10)
        response = client.post(
            f"/api/v1/inquiries/{inquiry_id}/cancel",
            cancel_body(state_version=state_version),
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        return response.status_code, response.json()
    finally:
        connections.close_all()


def cancellable_lock_barrier(barrier: Barrier):
    """Force both PostgreSQL requests to contend for the inquiry row lock."""

    original = InquiryRepository.lock_cancellable_inquiry
    thread_state = local()

    def synchronized_lock(*args, **kwargs):
        if not getattr(thread_state, "lock_attempted", False):
            thread_state.lock_attempted = True
            barrier.wait(timeout=10)
        return original(*args, **kwargs)

    return patch.object(
        InquiryRepository,
        "lock_cancellable_inquiry",
        side_effect=synchronized_lock,
    )


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_cancel_same_key_is_one_write_and_one_replay():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    owner = create_user(130)
    _client, inquiry = create_inquiry(owner, 130)
    barrier = Barrier(2)
    lock_barrier = Barrier(2)
    with cancellable_lock_barrier(lock_barrier), ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                concurrent_cancel,
                actor_id=owner.pk,
                inquiry_id=inquiry.public_id,
                state_version=1,
                key="t023-concurrent-same-key",
                barrier=barrier,
            )
            for _ in range(2)
        ]
        results = [future.result(timeout=30) for future in futures]

    assert sorted(status for status, _payload in results) == [200, 200]
    assert sorted(
        payload["data"]["idempotent_replay"] for _status, payload in results
    ) == [False, True]
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CANCELLED
    assert inquiry.state_version == 2
    assert TransitionHistory.objects.filter(
        inquiry=inquiry,
        event_code="CANCEL_INQUIRY",
    ).count() == 1
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="cancelInquiry",
    ).count() == 1


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_cancel_new_keys_have_one_version_winner():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    owner = create_user(131)
    _client, inquiry = create_inquiry(owner, 131)
    barrier = Barrier(2)
    lock_barrier = Barrier(2)
    keys = ("t023-concurrent-key-a", "t023-concurrent-key-b")
    with cancellable_lock_barrier(lock_barrier), ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                concurrent_cancel,
                actor_id=owner.pk,
                inquiry_id=inquiry.public_id,
                state_version=1,
                key=key,
                barrier=barrier,
            )
            for key in keys
        ]
        results = [future.result(timeout=30) for future in futures]

    assert sorted(status for status, _payload in results) == [200, 409]
    conflict = next(payload for status, payload in results if status == 409)
    assert conflict["error"]["code"] == "STATE-CONFLICT-01"
    assert conflict["error"]["details"] == {
        "current_status": Inquiry.Status.CANCELLED,
        "current_state_version": 2,
        "allowed_actions": [],
    }
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CANCELLED
    assert inquiry.state_version == 2
    assert TransitionHistory.objects.filter(
        inquiry=inquiry,
        event_code="CANCEL_INQUIRY",
    ).count() == 1
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="cancelInquiry",
    ).count() == 1


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
