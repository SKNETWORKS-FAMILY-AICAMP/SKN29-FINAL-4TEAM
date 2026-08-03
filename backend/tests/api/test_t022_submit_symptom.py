"""Runtime tests for the approved T-022 SUBMIT_SYMPTOM Slice A."""

from datetime import date
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, local
from uuid import UUID
from unittest.mock import patch

import pytest
from django.db import connection, connections
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import Inquiry, SymptomEntry
from apps.products.models import ProductModel
from apps.questionnaires.models import QuestionnaireSession
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.engine.state_machine import InvalidStateTransition
from apps.workflow.models import IdempotencyRecord, TransitionHistory
from apps.workflow.repositories.workflow_repository import (
    WorkflowRepository,
)


pytestmark = pytest.mark.django_db


def create_user(sequence: int, *, role: str = "CUSTOMER") -> User:
    employee_no = (
        None
        if role == User.Role.CUSTOMER
        else f"T022S-EMP-{sequence:03d}"
    )
    user = User.objects.create_user(
        username=f"T022S-{role}-{sequence:03d}",
        password=None,
        full_name=f"T022 submit {role} {sequence}",
        role_code=role,
        employee_no=employee_no,
    )
    if role == User.Role.CUSTOMER:
        CustomerProfile.objects.create(
            user=user,
            customer_no=f"T022S-CUS-{sequence:03d}",
            customer_name=f"T022 submit customer {sequence}",
        )
    return user


def create_subscription(
    owner: User,
    sequence: int,
) -> CustomerSubscription:
    product = ProductModel.objects.create(
        model_code=f"T022S-PMD-{sequence:03d}",
        model_name=f"T022 submit product {sequence}",
    )
    return CustomerSubscription.objects.create(
        contract_no=f"T022S-SUB-{sequence:03d}",
        customer=owner.customer_profile,
        product_model=product,
        serial_no=f"T022S-SERIAL-{sequence:03d}",
        started_on=date(2026, 7, 1),
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def create_inquiry(
    owner: User,
    sequence: int,
    *,
    raw_text: str = "필터 교체 후 출수량이 줄었습니다.",
    with_representative_symptom: bool = True,
) -> tuple[APIClient, Inquiry, CustomerSubscription]:
    subscription = create_subscription(owner, sequence)
    client = authenticated_client(owner)
    body = {
        "subscription_id": str(subscription.public_id),
        "channel_code": "WEB",
        "raw_text": raw_text,
    }
    if with_representative_symptom:
        body["representative_symptom_code"] = "LOW_FLOW"
    response = client.post(
        "/api/v1/inquiries",
        body,
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"t022s-start-{sequence}",
    )
    assert response.status_code == 201
    inquiry = Inquiry.objects.get(
        public_id=response.json()["data"]["inquiry_id"]
    )
    return client, inquiry, subscription


def post_submit(
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
        f"/api/v1/inquiries/{inquiry.public_id}/submit",
        body,
        format="json",
        **headers,
    )


def submit_history(inquiry: Inquiry):
    return TransitionHistory.objects.filter(
        inquiry=inquiry,
        event_code="SUBMIT_SYMPTOM",
    )


def submit_idempotency(actor: User):
    return IdempotencyRecord.objects.filter(
        actor=actor,
        operation_id="submitSymptom",
    )


def test_submit_transitions_once_and_preserves_saved_customer_input():
    owner = create_user(1)
    client, inquiry, _subscription = create_inquiry(owner, 1)
    original_raw_text = inquiry.raw_text
    symptom = SymptomEntry.objects.get(inquiry=inquiry)

    response = post_submit(
        client,
        inquiry,
        {"state_version": 1},
        key="t022s-submit-success",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] is None
    assert set(payload["data"]) == {
        "inquiry_id",
        "state",
        "state_version",
        "idempotent_replay",
        "allowed_actions",
    }
    assert payload["data"] == {
        "inquiry_id": str(inquiry.public_id),
        "state": "QUESTIONNAIRE_IN_PROGRESS",
        "state_version": 2,
        "idempotent_replay": False,
        "allowed_actions": [
            {
                "code": "SUBMIT_ANSWERS",
                "label": "추가 답변 제출",
                "operation_id": "submitFollowUpAnswers",
                "style": "PRIMARY",
                "requires_confirmation": False,
                "confirmation_message": None,
            },
            {
                "code": "CANCEL_INQUIRY",
                "label": "문의 취소",
                "operation_id": "cancelInquiry",
                "style": "DESTRUCTIVE",
                "requires_confirmation": True,
                "confirmation_message": "문의를 취소하시겠습니까?",
            },
        ],
    }
    assert UUID(payload["data"]["inquiry_id"])

    inquiry.refresh_from_db()
    symptom.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert inquiry.state_version == 2
    assert inquiry.raw_text == original_raw_text
    assert symptom.symptom_type_code == "LOW_FLOW"
    assert SymptomEntry.objects.filter(inquiry=inquiry).count() == 1
    assert QuestionnaireSession.objects.count() == 0

    history = submit_history(inquiry).get()
    assert history.from_state == Inquiry.Status.DRAFT
    assert history.to_state == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert history.state_version == 2
    assert history.actor == owner
    assert history.idempotency_key == "t022s-submit-success"

    record = submit_idempotency(owner).get()
    assert record.response_status == 200
    assert record.resource_public_id == inquiry.public_id
    assert record.response_body == payload["data"]
    assert record.completed_at is not None


def test_natural_language_only_inquiry_submits_without_symptom_overwrite():
    owner = create_user(12)
    client, inquiry, _subscription = create_inquiry(
        owner,
        12,
        raw_text="정수기에서 평소와 다른 소리가 납니다.",
        with_representative_symptom=False,
    )
    original_raw_text = inquiry.raw_text
    assert SymptomEntry.objects.filter(inquiry=inquiry).count() == 0

    response = post_submit(
        client,
        inquiry,
        {"state_version": 1},
        key="t022s-natural-language-only",
    )

    assert response.status_code == 200
    assert response.json()["data"]["state"] == (
        Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    )
    assert response.json()["data"]["state_version"] == 2
    inquiry.refresh_from_db()
    assert inquiry.raw_text == original_raw_text
    assert inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert inquiry.state_version == 2
    assert SymptomEntry.objects.filter(inquiry=inquiry).count() == 0
    assert submit_history(inquiry).count() == 1
    assert submit_idempotency(owner).count() == 1


def test_same_key_and_body_replays_without_duplicate_writes():
    owner = create_user(2)
    client, inquiry, _subscription = create_inquiry(owner, 2)
    body = {"state_version": 1}

    first = post_submit(
        client,
        inquiry,
        body,
        key="t022s-replay",
    )
    second = post_submit(
        client,
        inquiry,
        body,
        key="t022s-replay",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["idempotent_replay"] is False
    assert second.json()["data"]["idempotent_replay"] is True
    assert submit_history(inquiry).count() == 1
    assert submit_idempotency(owner).count() == 1
    inquiry.refresh_from_db()
    assert inquiry.state_version == 2


def test_same_key_different_body_conflicts_before_changed_state():
    owner = create_user(3)
    client, inquiry, _subscription = create_inquiry(owner, 3)

    first = post_submit(
        client,
        inquiry,
        {"state_version": 1},
        key="t022s-reused-key",
    )
    second = post_submit(
        client,
        inquiry,
        {"state_version": 2},
        key="t022s-reused-key",
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"] == {
        "code": "DUPLICATE-EVENT-01",
        "message": "동일 Idempotency-Key가 다른 요청에 재사용되었습니다.",
        "details": {},
    }
    assert submit_history(inquiry).count() == 1
    assert submit_idempotency(owner).count() == 1


def test_stale_version_and_wrong_current_state_return_latest_snapshot():
    owner = create_user(4)
    client, inquiry, _subscription = create_inquiry(owner, 4)

    stale = post_submit(
        client,
        inquiry,
        {"state_version": 2},
        key="t022s-stale",
    )
    assert stale.status_code == 409
    assert stale.json()["error"] == {
        "code": "STATE-CONFLICT-01",
        "message": "다른 사용자가 문의 상태를 먼저 변경했습니다.",
        "details": {
            "current_status": "DRAFT",
            "current_state_version": 1,
            "allowed_actions": ["SUBMIT_SYMPTOM", "CANCEL_INQUIRY"],
        },
    }

    succeeded = post_submit(
        client,
        inquiry,
        {"state_version": 1},
        key="t022s-transition",
    )
    wrong_state = post_submit(
        client,
        inquiry,
        {"state_version": 2},
        key="t022s-wrong-state",
    )

    assert succeeded.status_code == 200
    assert wrong_state.status_code == 409
    assert wrong_state.json()["error"]["details"] == {
        "current_status": "QUESTIONNAIRE_IN_PROGRESS",
        "current_state_version": 2,
        "allowed_actions": ["SUBMIT_ANSWERS", "CANCEL_INQUIRY"],
    }
    assert submit_history(inquiry).count() == 1
    assert submit_idempotency(owner).count() == 1


@pytest.mark.parametrize(
    "role",
    [
        User.Role.CONSULTANT,
        User.Role.TECHNICIAN,
        User.Role.OPERATOR,
    ],
)
def test_owner_scope_role_and_authentication_are_enforced(role):
    owner = create_user(5)
    owner_client, inquiry, _subscription = create_inquiry(owner, 5)
    other = create_user(6)
    non_customer = create_user(7, role=role)

    hidden = post_submit(
        authenticated_client(other),
        inquiry,
        {"state_version": 1},
        key="t022s-other-owner",
    )
    forbidden = post_submit(
        authenticated_client(non_customer),
        inquiry,
        {"state_version": 1},
        key=f"t022s-{role.lower()}",
    )
    anonymous = post_submit(
        APIClient(),
        inquiry,
        {"state_version": 1},
        key="t022s-anonymous",
    )

    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"
    assert anonymous.status_code == 401
    assert anonymous.json()["error"]["code"] == "AUTH_REQUIRED"
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.DRAFT
    assert submit_history(inquiry).count() == 0
    assert IdempotencyRecord.objects.filter(
        operation_id="submitSymptom"
    ).count() == 0
    assert owner_client is not None


@pytest.mark.parametrize(
    "body,key",
    [
        ({"state_version": 1}, None),
        ({"state_version": 1}, ""),
        ({"state_version": 1}, "x" * 129),
        ({}, "t022s-missing-version"),
        ({"state_version": 0}, "t022s-zero-version"),
        (
            {"state_version": 1, "raw_text": "overwrite"},
            "t022s-overwrite-attempt",
        ),
    ],
)
def test_header_and_body_validation_leave_no_submit_side_effects(
    body,
    key,
):
    sequence = 10 + len(str(key))
    owner = create_user(sequence)
    client, inquiry, _subscription = create_inquiry(owner, sequence)

    response = post_submit(client, inquiry, body, key=key)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.DRAFT
    assert inquiry.state_version == 1
    assert submit_history(inquiry).count() == 0
    assert submit_idempotency(owner).count() == 0


@pytest.mark.parametrize("raw_text", ["한", "x" * 2001])
def test_invalid_saved_raw_text_is_rejected_without_overwrite(raw_text):
    sequence = 40 + len(raw_text)
    owner = create_user(sequence)
    client, inquiry, _subscription = create_inquiry(
        owner,
        sequence,
        raw_text=raw_text,
        with_representative_symptom=False,
    )

    response = post_submit(
        client,
        inquiry,
        {"state_version": 1},
        key=f"t022s-invalid-saved-{sequence}",
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    inquiry.refresh_from_db()
    assert inquiry.raw_text == raw_text
    assert inquiry.status_code == Inquiry.Status.DRAFT
    assert submit_history(inquiry).count() == 0
    assert submit_idempotency(owner).count() == 0


def test_inactive_subscription_is_rejected_before_state_change():
    owner = create_user(8)
    client, inquiry, subscription = create_inquiry(owner, 8)
    subscription.status_code = CustomerSubscription.Status.SUSPENDED
    subscription.save(update_fields=["status_code", "updated_at"])

    response = post_submit(
        client,
        inquiry,
        {"state_version": 1},
        key="t022s-inactive-subscription",
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.DRAFT
    assert submit_history(inquiry).count() == 0
    assert submit_idempotency(owner).count() == 0


def test_late_failure_rolls_back_state_history_and_idempotency():
    owner = create_user(9)
    client, inquiry, _subscription = create_inquiry(owner, 9)
    original_raw_text = inquiry.raw_text

    with patch.object(
        WorkflowRepository,
        "complete_idempotency_record",
        side_effect=RuntimeError("forced late failure"),
    ):
        response = post_submit(
            client,
            inquiry,
            {"state_version": 1},
            key="t022s-late-failure",
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.DRAFT
    assert inquiry.state_version == 1
    assert inquiry.raw_text == original_raw_text
    assert submit_history(inquiry).count() == 0
    assert submit_idempotency(owner).count() == 0


def test_response_contract_failure_rolls_back_all_transition_writes():
    owner = create_user(10)
    client, inquiry, _subscription = create_inquiry(owner, 10)
    original_raw_text = inquiry.raw_text

    with patch(
        "apps.inquiries.api.views.SubmitSymptomResponseSerializer",
        side_effect=RuntimeError("forced response contract failure"),
    ):
        response = post_submit(
            client,
            inquiry,
            {"state_version": 1},
            key="t022s-response-contract-failure",
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.DRAFT
    assert inquiry.state_version == 1
    assert inquiry.raw_text == original_raw_text
    assert submit_history(inquiry).count() == 0
    assert submit_idempotency(owner).count() == 0


def test_state_contract_integrity_failure_is_not_exposed_as_retryable_409():
    owner = create_user(11)
    client, inquiry, _subscription = create_inquiry(owner, 11)

    with patch(
        "apps.inquiries.services.inquiry_transition_service."
        "StateMachine.resolve",
        side_effect=InvalidStateTransition(
            "forced ambiguous transition",
            reason="AMBIGUOUS_TRANSITION",
        ),
    ):
        response = post_submit(
            client,
            inquiry,
            {"state_version": 1},
            key="t022s-state-contract-integrity",
        )

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "INTERNAL_ERROR",
        "message": "요청 처리 중 오류가 발생했습니다.",
        "details": {},
    }
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.DRAFT
    assert inquiry.state_version == 1
    assert submit_history(inquiry).count() == 0
    assert submit_idempotency(owner).count() == 0


def concurrent_submit(
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
            f"/api/v1/inquiries/{inquiry_id}/submit",
            {"state_version": state_version},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        return response.status_code, response.json()
    finally:
        connections.close_all()


def first_idempotency_lookup_barrier(barrier: Barrier):
    """Force both PostgreSQL requests past the first empty key lookup."""

    original = WorkflowRepository.lock_idempotency_scope
    thread_state = local()

    def synchronized_lookup(*args, **kwargs):
        result = original(*args, **kwargs)
        if not getattr(thread_state, "first_lookup_done", False):
            thread_state.first_lookup_done = True
            assert result is None
            barrier.wait(timeout=10)
        return result

    return patch.object(
        WorkflowRepository,
        "lock_idempotency_scope",
        side_effect=synchronized_lookup,
    )


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_same_key_is_one_write_and_one_replay():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    owner = create_user(70)
    _client, inquiry, _subscription = create_inquiry(owner, 70)
    barrier = Barrier(2)
    lookup_barrier = Barrier(2)
    with first_idempotency_lookup_barrier(lookup_barrier), ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                concurrent_submit,
                actor_id=owner.pk,
                inquiry_id=inquiry.public_id,
                state_version=1,
                key="t022s-concurrent-same-key",
                barrier=barrier,
            )
            for _ in range(2)
        ]
        results = [future.result(timeout=30) for future in futures]

    assert sorted(status for status, _payload in results) == [200, 200]
    assert sorted(
        payload["data"]["idempotent_replay"]
        for _status, payload in results
    ) == [False, True]
    assert submit_history(inquiry).count() == 1
    assert submit_idempotency(owner).count() == 1
    inquiry.refresh_from_db()
    assert inquiry.state_version == 2


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_new_keys_allow_only_one_version_winner():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    owner = create_user(71)
    _client, inquiry, _subscription = create_inquiry(owner, 71)
    barrier = Barrier(2)
    lookup_barrier = Barrier(2)
    keys = (
        "t022s-concurrent-key-a",
        "t022s-concurrent-key-b",
    )
    with first_idempotency_lookup_barrier(lookup_barrier), ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                concurrent_submit,
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
    errors = [
        payload["error"]
        for status, payload in results
        if status == 409
    ]
    assert errors == [
        {
            "code": "STATE-CONFLICT-01",
            "message": "다른 사용자가 문의 상태를 먼저 변경했습니다.",
            "details": {
                "current_status": "QUESTIONNAIRE_IN_PROGRESS",
                "current_state_version": 2,
                "allowed_actions": ["SUBMIT_ANSWERS", "CANCEL_INQUIRY"],
            },
        }
    ]
    assert submit_history(inquiry).count() == 1
    assert submit_idempotency(owner).count() == 1
    inquiry.refresh_from_db()
    assert inquiry.state_version == 2
