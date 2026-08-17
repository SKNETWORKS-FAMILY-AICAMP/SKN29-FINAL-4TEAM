"""T-019 owner-only completed care history Runtime tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier, local
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import connection, connections
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.care.models import CareRecord
from apps.care.repositories.care_history_repository import (
    CareHistoryRepository,
)
from apps.care.services.care_history_service import CareHistoryService
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import IdempotencyRecord
from apps.workflow.repositories.workflow_repository import WorkflowRepository


pytestmark = pytest.mark.django_db
SUPPORTED_CODE = "WPUJAC104DWH"


def create_user(sequence: int, *, role=User.Role.CUSTOMER) -> User:
    user = User.objects.create_user(
        username=f"T019-{role}-{sequence:03d}",
        full_name=f"T019 {role} {sequence}",
        role_code=role,
        employee_no=(None if role == User.Role.CUSTOMER else f"T019-E-{sequence:03d}"),
        is_synthetic=True,
    )
    if role == User.Role.CUSTOMER:
        CustomerProfile.objects.create(
            user=user,
            customer_no=f"T019-C-{sequence:03d}",
            customer_name=f"T019 customer {sequence}",
            is_synthetic=True,
        )
    return user


def create_product(
    sequence: int,
    *,
    model_code: str = SUPPORTED_CODE,
    active: bool = True,
) -> ProductModel:
    return ProductModel.objects.create(
        model_code=model_code,
        model_name=f"T019 purifier {sequence}",
        is_supported_mvp=model_code == SUPPORTED_CODE,
        is_active=active,
    )


def create_subscription(
    owner: User,
    product: ProductModel,
    sequence: int,
    *,
    status: str = CustomerSubscription.Status.ACTIVE,
) -> CustomerSubscription:
    return CustomerSubscription.objects.create(
        contract_no=f"T019-SUB-{sequence:03d}",
        customer=owner.customer_profile,
        product_model=product,
        serial_no=f"T019-SERIAL-{sequence:03d}",
        management_type_code=CustomerSubscription.ManagementType.SELF_MANAGED,
        status_code=status,
        started_on=date(2026, 7, 1),
        ended_on=(date(2026, 8, 1) if status in {"CANCELLED", "EXPIRED"} else None),
    )


def create_completed(
    subscription: CustomerSubscription,
    sequence: int,
    *,
    performed_on: date,
    care_type: str = CareRecord.CareType.FILTER_REPLACEMENT,
) -> CareRecord:
    return CareRecord.objects.create(
        care_code=f"T019-CARE-{sequence:03d}",
        subscription=subscription,
        care_type_code=care_type,
        status_code=CareRecord.Status.COMPLETED,
        performed_on=performed_on,
        result_code=(
            CareRecord.Result.FILTER_REPLACED
            if care_type == CareRecord.CareType.FILTER_REPLACEMENT
            else CareRecord.Result.NORMAL
        ),
        source_code=CareRecord.Source.IMPORT,
    )


def client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def headers(key: str) -> dict[str, str]:
    return {
        "HTTP_IDEMPOTENCY_KEY": key,
        "HTTP_X_CORRELATION_ID": str(uuid4()),
    }


def list_path(subscription: CustomerSubscription) -> str:
    return f"/api/v1/me/subscriptions/{subscription.public_id}/care-records"


def concurrent_create_care(
    *,
    actor_id: int,
    subscription_id,
    key: str,
    payload: dict,
    barrier: Barrier,
) -> tuple[int, dict]:
    """Issue one care create request with a thread-local DB connection."""

    connections.close_all()
    try:
        actor = User.objects.get(pk=actor_id)
        client = client_for(actor)
        barrier.wait(timeout=10)
        response = client.post(
            "/api/v1/me/subscriptions/"
            f"{subscription_id}/care-records",
            payload,
            format="json",
            **headers(key),
        )
        return response.status_code, response.json()
    finally:
        connections.close_all()


def customer_lock_barrier(barrier: Barrier):
    """Make both PostgreSQL requests contend for the customer row lock."""

    original = CareHistoryRepository.lock_customer
    thread_state = local()

    def synchronized_lock(*args, **kwargs):
        if not getattr(thread_state, "lock_attempted", False):
            thread_state.lock_attempted = True
            barrier.wait(timeout=10)
        return original(*args, **kwargs)

    return patch.object(
        CareHistoryRepository,
        "lock_customer",
        side_effect=synchronized_lock,
    )


def test_create_self_care_derives_safe_result_and_replays_once():
    owner = create_user(1)
    subscription = create_subscription(owner, create_product(1), 1)
    client = client_for(owner)
    request_headers = headers("t019-create-001")
    payload = {
        "care_type_code": "FILTER_REPLACEMENT",
        "performed_on": "2026-08-10",
    }

    first = client.post(
        list_path(subscription),
        payload,
        format="json",
        **request_headers,
    )
    replay = client.post(
        list_path(subscription),
        payload,
        format="json",
        **request_headers,
    )

    assert first.status_code == replay.status_code == 201
    assert first.json()["data"] == {
        "care_record_id": first.json()["data"]["care_record_id"],
        "subscription_id": str(subscription.public_id),
        "care_type_code": "FILTER_REPLACEMENT",
        "status_code": "COMPLETED",
        "performed_on": "2026-08-10",
        "result_code": "FILTER_REPLACED",
        "source_code": "CUSTOMER",
        "idempotent_replay": False,
    }
    assert replay.json()["data"]["idempotent_replay"] is True
    care = CareRecord.objects.get()
    assert care.performed_by == owner
    assert care.completed_at is not None
    assert care.inquiry_id is None and care.visit_id is None
    assert CareRecord.objects.count() == 1
    assert IdempotencyRecord.objects.count() == 1


def test_same_key_different_payload_conflicts_without_second_write():
    owner = create_user(1)
    subscription = create_subscription(owner, create_product(1), 1)
    client = client_for(owner)
    request_headers = headers("t019-create-conflict")
    first = client.post(
        list_path(subscription),
        {
            "care_type_code": "CLEANING",
            "performed_on": "2026-08-09",
        },
        format="json",
        **request_headers,
    )
    conflict = client.post(
        list_path(subscription),
        {
            "care_type_code": "CLEANING",
            "performed_on": "2026-08-10",
        },
        format="json",
        **request_headers,
    )
    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "DUPLICATE-EVENT-01"
    assert CareRecord.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_create_same_key_is_one_write_and_one_replay():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    owner = create_user(90)
    subscription = create_subscription(owner, create_product(90), 90)
    payload = {
        "care_type_code": "FILTER_REPLACEMENT",
        "performed_on": "2026-08-10",
    }
    request_barrier = Barrier(2)
    lock_barrier = Barrier(2)
    with customer_lock_barrier(lock_barrier), ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                concurrent_create_care,
                actor_id=owner.pk,
                subscription_id=subscription.public_id,
                key="t019-concurrent-same-key",
                payload=payload,
                barrier=request_barrier,
            )
            for _ in range(2)
        ]
        results = [future.result(timeout=30) for future in futures]

    assert sorted(status for status, _payload in results) == [201, 201]
    assert sorted(
        response["data"]["idempotent_replay"]
        for _status, response in results
    ) == [False, True]
    resource_ids = {
        response["data"]["care_record_id"]
        for _status, response in results
    }
    assert len(resource_ids) == 1
    assert CareRecord.objects.count() == 1
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="createMyCareRecord",
        idempotency_key="t019-concurrent-same-key",
    ).count() == 1


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_same_key_different_payload_has_one_winner():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    owner = create_user(91)
    subscription = create_subscription(owner, create_product(91), 91)
    payloads = (
        {
            "care_type_code": "FILTER_REPLACEMENT",
            "performed_on": "2026-08-09",
        },
        {
            "care_type_code": "CLEANING",
            "performed_on": "2026-08-10",
        },
    )
    request_barrier = Barrier(2)
    lock_barrier = Barrier(2)
    with customer_lock_barrier(lock_barrier), ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                concurrent_create_care,
                actor_id=owner.pk,
                subscription_id=subscription.public_id,
                key="t019-concurrent-conflicting-payload",
                payload=payload,
                barrier=request_barrier,
            )
            for payload in payloads
        ]
        outcomes = [
            (payload, future.result(timeout=30))
            for payload, future in zip(payloads, futures, strict=True)
        ]

    assert sorted(result[0] for _payload, result in outcomes) == [201, 409]
    conflict = next(
        response
        for _request, (status, response) in outcomes
        if status == 409
    )
    assert conflict["error"]["code"] == "DUPLICATE-EVENT-01"
    winner_request, (_status, winner_response) = next(
        outcome for outcome in outcomes if outcome[1][0] == 201
    )
    care = CareRecord.objects.get()
    assert care.care_type_code == winner_request["care_type_code"]
    assert care.performed_on == date.fromisoformat(
        winner_request["performed_on"]
    )
    assert winner_response["data"]["care_record_id"] == str(care.public_id)
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="createMyCareRecord",
        idempotency_key="t019-concurrent-conflicting-payload",
    ).count() == 1


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_new_keys_preserve_both_care_records():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    owner = create_user(92)
    subscription = create_subscription(owner, create_product(92), 92)
    requests = (
        (
            "t019-concurrent-key-a",
            {
                "care_type_code": "FILTER_REPLACEMENT",
                "performed_on": "2026-08-09",
            },
        ),
        (
            "t019-concurrent-key-b",
            {
                "care_type_code": "CLEANING",
                "performed_on": "2026-08-10",
            },
        ),
    )
    request_barrier = Barrier(2)
    lock_barrier = Barrier(2)
    with customer_lock_barrier(lock_barrier), ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                concurrent_create_care,
                actor_id=owner.pk,
                subscription_id=subscription.public_id,
                key=key,
                payload=payload,
                barrier=request_barrier,
            )
            for key, payload in requests
        ]
        results = [future.result(timeout=30) for future in futures]

    assert [status for status, _payload in results] == [201, 201]
    assert CareRecord.objects.filter(subscription=subscription).count() == 2
    assert set(
        CareRecord.objects.filter(subscription=subscription).values_list(
            "care_type_code",
            flat=True,
        )
    ) == {"FILTER_REPLACEMENT", "CLEANING"}
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="createMyCareRecord",
    ).count() == 2


def test_list_returns_completed_only_ordered_and_paginated():
    owner = create_user(1)
    subscription = create_subscription(owner, create_product(1), 1)
    older = create_completed(subscription, 1, performed_on=date(2026, 8, 1))
    newer = create_completed(
        subscription,
        2,
        performed_on=date(2026, 8, 10),
        care_type=CareRecord.CareType.CLEANING,
    )
    CareRecord.objects.create(
        care_code="T019-SCHEDULED",
        subscription=subscription,
        care_type_code=CareRecord.CareType.PERIODIC_CHECK,
        status_code=CareRecord.Status.SCHEDULED,
        scheduled_on=date(2026, 8, 20),
    )

    response = client_for(owner).get(f"{list_path(subscription)}?page=1&size=1")
    second = client_for(owner).get(f"{list_path(subscription)}?page=2&size=1")

    assert response.status_code == second.status_code == 200
    assert response.json()["data"]["total"] == 2
    assert response.json()["data"]["items"][0]["care_record_id"] == str(newer.public_id)
    assert second.json()["data"]["items"][0]["care_record_id"] == str(older.public_id)
    assert "summary" not in str(response.json()["data"])


def test_detail_and_list_hide_owner_status_and_product_scope():
    owner = create_user(1)
    other = create_user(2)
    supported = create_product(1)
    unsupported = create_product(2, model_code="OTHER-MODEL")
    active = create_subscription(owner, supported, 1)
    other_sub = create_subscription(other, supported, 2)
    inactive = create_subscription(owner, supported, 3, status="EXPIRED")
    wrong_product = create_subscription(owner, unsupported, 4)
    care = create_completed(active, 1, performed_on=date(2026, 8, 10))
    other_care = create_completed(other_sub, 2, performed_on=date(2026, 8, 10))
    client = client_for(owner)

    detail = client.get(f"{list_path(active)}/{care.public_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["care_record_id"] == str(care.public_id)

    hidden_paths = (
        f"{list_path(active)}/{other_care.public_id}",
        list_path(other_sub),
        list_path(inactive),
        list_path(wrong_product),
        f"/api/v1/me/subscriptions/{uuid4()}/care-records",
    )
    for path in hidden_paths:
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_create_masks_other_inactive_unsupported_and_unknown_subscriptions():
    owner = create_user(10)
    other = create_user(11)
    supported = create_product(10)
    unsupported = create_product(11, model_code="OTHER-MODEL")
    hidden_subscriptions = (
        create_subscription(other, supported, 10),
        create_subscription(owner, supported, 11, status="EXPIRED"),
        create_subscription(owner, unsupported, 12),
    )
    paths = [list_path(subscription) for subscription in hidden_subscriptions]
    paths.append(f"/api/v1/me/subscriptions/{uuid4()}/care-records")
    client = client_for(owner)

    for sequence, path in enumerate(paths, start=1):
        response = client.post(
            path,
            {
                "care_type_code": "CLEANING",
                "performed_on": "2026-08-10",
            },
            format="json",
            **headers(f"t019-hidden-write-{sequence}"),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    assert CareRecord.objects.count() == 0
    assert IdempotencyRecord.objects.count() == 0


def test_create_rolls_back_care_and_idempotency_on_late_failure(monkeypatch):
    owner = create_user(12)
    subscription = create_subscription(owner, create_product(12), 12)

    def fail_completion(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("private-t019-late-error")

    monkeypatch.setattr(
        WorkflowRepository,
        "complete_idempotency_record",
        fail_completion,
    )
    response = client_for(owner).post(
        list_path(subscription),
        {
            "care_type_code": "CLEANING",
            "performed_on": "2026-08-10",
        },
        format="json",
        **headers("t019-create-rollback"),
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private-t019-late-error" not in response.content.decode()
    assert CareRecord.objects.count() == 0
    assert IdempotencyRecord.objects.count() == 0


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"unknown": "value"},
        {"care_type_code": "VISIT_SERVICE", "performed_on": "2026-08-10"},
        {"care_type_code": "PERIODIC_CHECK", "performed_on": "2026-08-10"},
        {"care_type_code": "CLEANING", "performed_on": "2026-06-30"},
    ],
)
def test_create_validation_and_self_care_allowlist(payload):
    owner = create_user(1)
    subscription = create_subscription(owner, create_product(1), 1)
    response = client_for(owner).post(
        list_path(subscription),
        payload,
        format="json",
        **headers(f"t019-invalid-{uuid4()}"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert CareRecord.objects.count() == 0


def test_future_date_missing_key_role_and_unknown_query_are_rejected():
    owner = create_user(1)
    staff = create_user(2, role=User.Role.CONSULTANT)
    subscription = create_subscription(owner, create_product(1), 1)
    path = list_path(subscription)
    future = (timezone.localdate() + timedelta(days=1)).isoformat()

    assert APIClient().get(path).status_code == 401
    assert client_for(staff).get(path).status_code == 403
    assert client_for(owner).get(f"{path}?status=COMPLETED").status_code == 422
    missing_key = client_for(owner).post(
        path,
        {"care_type_code": "CLEANING", "performed_on": "2026-08-10"},
        format="json",
    )
    assert missing_key.status_code == 422
    future_response = client_for(owner).post(
        path,
        {"care_type_code": "CLEANING", "performed_on": future},
        format="json",
        **headers("t019-future"),
    )
    assert future_response.status_code == 422


def test_ai_projection_returns_recent_five_safe_completed_rows():
    owner = create_user(1)
    subscription = create_subscription(owner, create_product(1), 1)
    for sequence in range(1, 8):
        care = create_completed(
            subscription,
            sequence,
            performed_on=date(2026, 8, sequence),
        )
        CareRecord.objects.filter(pk=care.pk).update(
            summary=f"private summary {sequence}"
        )

    result = CareHistoryService.recent_completed_context(
        subscription=subscription,
    )

    assert len(result) == 5
    assert [item["performed_on"] for item in result] == [
        "2026-08-07",
        "2026-08-06",
        "2026-08-05",
        "2026-08-04",
        "2026-08-03",
    ]
    assert set(result[0]) == {
        "care_type_code",
        "performed_on",
        "result_code",
    }
    assert "private" not in str(result)


def test_assigned_consultant_projection_masks_unassigned_inquiry():
    owner = create_user(1)
    assigned = create_user(2, role=User.Role.CONSULTANT)
    unassigned = create_user(3, role=User.Role.CONSULTANT)
    subscription = create_subscription(owner, create_product(1), 1)
    inquiry = Inquiry.objects.create(
        subscription=subscription,
        initiated_by=owner,
        assigned_user=assigned,
        assigned_role_code=Inquiry.AssignedRole.CONSULTANT,
        channel_code=Inquiry.Channel.WEB,
        raw_text="synthetic T-019 assigned projection",
    )
    create_completed(
        subscription,
        1,
        performed_on=date(2026, 8, 10),
    )

    result = CareHistoryService.assigned_inquiry_context(
        actor=assigned,
        inquiry_public_id=inquiry.public_id,
    )

    assert result == [
        {
            "care_type_code": "FILTER_REPLACEMENT",
            "performed_on": "2026-08-10",
            "result_code": "FILTER_REPLACED",
        }
    ]
    with pytest.raises(NotFound):
        CareHistoryService.assigned_inquiry_context(
            actor=unassigned,
            inquiry_public_id=inquiry.public_id,
        )
