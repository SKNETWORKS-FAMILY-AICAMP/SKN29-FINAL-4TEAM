"""T-018 synthetic customer subscription create/update Runtime tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier, local
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import connection, connections
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.care.models import CareRecord
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.subscriptions.repositories.subscription_repository import (
    SubscriptionRepository,
)
from apps.workflow.models import IdempotencyRecord
from apps.workflow.repositories.workflow_repository import WorkflowRepository


pytestmark = pytest.mark.django_db
SUPPORTED_CODE = "WPUJAC104DWH"


def create_customer(sequence: int, *, synthetic: bool = True) -> User:
    user = User.objects.create_user(
        username=f"T018-WRITE-{sequence:03d}",
        full_name=f"T018 write customer {sequence}",
        role_code=User.Role.CUSTOMER,
        is_synthetic=synthetic,
    )
    CustomerProfile.objects.create(
        user=user,
        customer_no=f"T018-WRITE-CUSTOMER-{sequence:03d}",
        customer_name=f"T018 write customer {sequence}",
        is_synthetic=True,
    )
    return user


def create_staff(sequence: int) -> User:
    return User.objects.create_user(
        username=f"T018-WRITE-STAFF-{sequence:03d}",
        full_name=f"T018 write staff {sequence}",
        role_code=User.Role.CONSULTANT,
        employee_no=f"T018-WRITE-EMP-{sequence:03d}",
        is_synthetic=True,
    )


def create_product(*, active: bool = True) -> ProductModel:
    return ProductModel.objects.create(
        model_code=SUPPORTED_CODE,
        model_name="T018 supported purifier",
        generation_code="D",
        manufacturer="SK magic",
        is_supported_mvp=True,
        is_active=active,
    )


def client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def write_headers(key: str) -> dict[str, str]:
    return {
        "HTTP_IDEMPOTENCY_KEY": key,
        "HTTP_X_CORRELATION_ID": str(uuid4()),
    }


def create_payload(**overrides):
    payload = {
        "model_code": SUPPORTED_CODE,
        "started_on": "2026-08-01",
        "management_type_code": "SELF_MANAGED",
        "last_care_on": "2026-08-05",
    }
    payload.update(overrides)
    return payload


def test_create_persists_subscription_and_last_care_without_private_fields():
    owner = create_customer(1)
    product = create_product()

    response = client_for(owner).post(
        "/api/v1/me/subscriptions",
        create_payload(),
        format="json",
        **write_headers("t018-create-001"),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["idempotent_replay"] is False
    assert data["status_code"] == "ACTIVE"
    assert data["started_on"] == "2026-08-01"
    assert data["last_care_on"] == "2026-08-05"
    assert data["product"]["model_code"] == SUPPORTED_CODE
    assert all(
        field not in str(data)
        for field in ("contract_no", "serial_no", "installation_address")
    )

    subscription = CustomerSubscription.objects.get(
        public_id=data["subscription_id"]
    )
    assert subscription.customer == owner.customer_profile
    assert subscription.product_model == product
    assert subscription.management_type_code == "SELF_MANAGED"
    assert subscription.contract_no.startswith("SYN-SUB-")
    assert subscription.serial_no.startswith("SYN-SERIAL-")
    care = CareRecord.objects.get(subscription=subscription)
    assert care.care_type_code == CareRecord.CareType.FILTER_REPLACEMENT
    assert care.status_code == CareRecord.Status.COMPLETED
    assert care.source_code == CareRecord.Source.IMPORT
    assert care.performed_on == date(2026, 8, 5)
    assert care.result_code == CareRecord.Result.FILTER_REPLACED


def test_create_replay_is_stable_and_different_payload_conflicts():
    owner = create_customer(1)
    create_product()
    client = client_for(owner)
    headers = write_headers("t018-create-replay")

    first = client.post(
        "/api/v1/me/subscriptions",
        create_payload(),
        format="json",
        **headers,
    )
    replay = client.post(
        "/api/v1/me/subscriptions",
        create_payload(),
        format="json",
        **headers,
    )
    conflict = client.post(
        "/api/v1/me/subscriptions",
        create_payload(management_type_code="VISIT_CARE"),
        format="json",
        **headers,
    )

    assert first.status_code == replay.status_code == 201
    assert replay.json()["data"]["idempotent_replay"] is True
    assert replay.json()["data"]["subscription_id"] == (
        first.json()["data"]["subscription_id"]
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "DUPLICATE-EVENT-01"
    assert CustomerSubscription.objects.count() == 1
    assert CareRecord.objects.count() == 1
    assert IdempotencyRecord.objects.count() == 1


def test_create_rejects_duplicate_active_and_unsupported_product():
    owner = create_customer(1)
    product = create_product()
    CustomerSubscription.objects.create(
        contract_no="T018-EXISTING",
        customer=owner.customer_profile,
        product_model=product,
        serial_no="T018-EXISTING-SERIAL",
        management_type_code="VISIT_CARE",
        status_code="ACTIVE",
        started_on=date(2026, 7, 1),
    )
    client = client_for(owner)

    duplicate = client.post(
        "/api/v1/me/subscriptions",
        create_payload(),
        format="json",
        **write_headers("t018-duplicate"),
    )
    unsupported = client.post(
        "/api/v1/me/subscriptions",
        create_payload(model_code="WPUIAC425SNW"),
        format="json",
        **write_headers("t018-unsupported"),
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == (
        "SUBSCRIPTION_ALREADY_ACTIVE"
    )
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "PRODUCT_NOT_SUPPORTED"
    assert CustomerSubscription.objects.count() == 1


def test_create_rejects_inactive_product_and_non_synthetic_customer():
    owner = create_customer(1)
    create_product(active=False)
    inactive = client_for(owner).post(
        "/api/v1/me/subscriptions",
        create_payload(),
        format="json",
        **write_headers("t018-inactive"),
    )
    assert inactive.status_code == 422
    assert inactive.json()["error"]["code"] == "PRODUCT_NOT_SUPPORTED"

    ProductModel.objects.all().delete()
    create_product(active=True)
    real_user = create_customer(2, synthetic=False)
    forbidden = client_for(real_user).post(
        "/api/v1/me/subscriptions",
        create_payload(),
        format="json",
        **write_headers("t018-real-customer"),
    )
    assert forbidden.status_code == 403


def test_patch_updates_allowlist_and_replays_without_extra_care_row():
    owner = create_customer(1)
    create_product()
    client = client_for(owner)
    created = client.post(
        "/api/v1/me/subscriptions",
        create_payload(last_care_on="2026-08-05"),
        format="json",
        **write_headers("t018-create-for-patch"),
    )
    subscription_id = created.json()["data"]["subscription_id"]
    headers = write_headers("t018-patch-001")
    payload = {
        "started_on": "2026-07-15",
        "management_type_code": "VISIT_CARE",
        "last_care_on": "2026-08-07",
    }

    first = client.patch(
        f"/api/v1/me/subscriptions/{subscription_id}",
        payload,
        format="json",
        **headers,
    )
    replay = client.patch(
        f"/api/v1/me/subscriptions/{subscription_id}",
        payload,
        format="json",
        **headers,
    )

    assert first.status_code == replay.status_code == 200
    assert first.json()["data"]["started_on"] == "2026-07-15"
    assert first.json()["data"]["management_type_code"] == "VISIT_CARE"
    assert first.json()["data"]["last_care_on"] == "2026-08-07"
    assert replay.json()["data"]["idempotent_replay"] is True
    assert CareRecord.objects.count() == 1


def test_patch_owner_role_and_hidden_resource_boundaries():
    owner = create_customer(1)
    other = create_customer(2)
    staff = create_staff(3)
    product = create_product()
    subscription = CustomerSubscription.objects.create(
        contract_no="T018-OWNER-BOUNDARY",
        customer=owner.customer_profile,
        product_model=product,
        serial_no="T018-OWNER-BOUNDARY-SERIAL",
        management_type_code="VISIT_CARE",
        status_code="ACTIVE",
        started_on=date(2026, 7, 1),
    )
    path = f"/api/v1/me/subscriptions/{subscription.public_id}"
    payload = {"management_type_code": "SELF_MANAGED"}

    assert APIClient().patch(path, payload, format="json").status_code == 401
    assert client_for(staff).patch(
        path,
        payload,
        format="json",
        **write_headers("t018-staff"),
    ).status_code == 403
    hidden = client_for(other).patch(
        path,
        payload,
        format="json",
        **write_headers("t018-other"),
    )
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"unknown": "value"},
        {"management_type_code": "INVALID"},
        {"started_on": "2099-01-01"},
        {"last_care_on": "2099-01-01"},
        {"started_on": "2026-08-10", "last_care_on": "2026-08-01"},
    ],
)
def test_write_validation_is_fail_closed(payload):
    owner = create_customer(1)
    create_product()
    response = client_for(owner).post(
        "/api/v1/me/subscriptions",
        payload,
        format="json",
        **write_headers(f"t018-invalid-{uuid4()}"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert CustomerSubscription.objects.count() == 0


def test_patch_rejects_started_on_after_existing_care_and_inactive_subscription():
    owner = create_customer(1)
    product = create_product()
    active = CustomerSubscription.objects.create(
        contract_no="T018-PATCH-DATE",
        customer=owner.customer_profile,
        product_model=product,
        serial_no="T018-PATCH-DATE-SERIAL",
        management_type_code="VISIT_CARE",
        status_code="ACTIVE",
        started_on=date(2026, 7, 1),
    )
    CareRecord.objects.create(
        care_code="T018-PATCH-DATE-CARE",
        subscription=active,
        care_type_code=CareRecord.CareType.FILTER_REPLACEMENT,
        status_code=CareRecord.Status.COMPLETED,
        performed_on=date(2026, 8, 1),
        result_code=CareRecord.Result.FILTER_REPLACED,
        source_code=CareRecord.Source.IMPORT,
    )
    inactive = CustomerSubscription.objects.create(
        contract_no="T018-PATCH-INACTIVE",
        customer=owner.customer_profile,
        product_model=product,
        serial_no="T018-PATCH-INACTIVE-SERIAL",
        management_type_code="VISIT_CARE",
        status_code="EXPIRED",
        started_on=date(2026, 7, 1),
        ended_on=date(2026, 8, 1),
    )
    client = client_for(owner)

    invalid_date = client.patch(
        f"/api/v1/me/subscriptions/{active.public_id}",
        {"started_on": "2026-08-02"},
        format="json",
        **write_headers("t018-patch-date"),
    )
    hidden_inactive = client.patch(
        f"/api/v1/me/subscriptions/{inactive.public_id}",
        {"management_type_code": "SELF_MANAGED"},
        format="json",
        **write_headers("t018-patch-inactive"),
    )

    assert invalid_date.status_code == 422
    assert hidden_inactive.status_code == 404
    active.refresh_from_db()
    assert active.started_on == date(2026, 7, 1)


def test_dates_use_current_business_day_boundary(monkeypatch):
    owner = create_customer(1)
    create_product()
    tomorrow = timezone.localdate() + timedelta(days=1)
    response = client_for(owner).post(
        "/api/v1/me/subscriptions",
        create_payload(started_on=tomorrow.isoformat(), last_care_on=None),
        format="json",
        **write_headers("t018-future-date"),
    )
    assert response.status_code == 422


def concurrent_create_subscription(
    *,
    actor_id: int,
    key: str,
    payload: dict,
    barrier: Barrier,
) -> tuple[int, dict]:
    """Issue one create request with a thread-local DB connection."""

    connections.close_all()
    try:
        actor = User.objects.get(pk=actor_id)
        client = client_for(actor)
        barrier.wait(timeout=10)
        response = client.post(
            "/api/v1/me/subscriptions",
            payload,
            format="json",
            **write_headers(key),
        )
        return response.status_code, response.json()
    finally:
        connections.close_all()


def concurrent_update_subscription(
    *,
    actor_id: int,
    subscription_id,
    key: str,
    payload: dict,
    barrier: Barrier,
) -> tuple[int, dict]:
    """Issue one partial update with a thread-local DB connection."""

    connections.close_all()
    try:
        actor = User.objects.get(pk=actor_id)
        client = client_for(actor)
        barrier.wait(timeout=10)
        response = client.patch(
            f"/api/v1/me/subscriptions/{subscription_id}",
            payload,
            format="json",
            **write_headers(key),
        )
        return response.status_code, response.json()
    finally:
        connections.close_all()


def customer_lock_barrier(barrier: Barrier):
    """Make both PostgreSQL requests contend for the customer row lock."""

    original = SubscriptionRepository.lock_synthetic_customer
    thread_state = local()

    def synchronized_lock(*args, **kwargs):
        if not getattr(thread_state, "lock_attempted", False):
            thread_state.lock_attempted = True
            barrier.wait(timeout=10)
        return original(*args, **kwargs)

    return patch.object(
        SubscriptionRepository,
        "lock_synthetic_customer",
        side_effect=synchronized_lock,
    )


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_create_same_key_is_one_write_and_one_replay():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    owner = create_customer(90)
    create_product()
    request_barrier = Barrier(2)
    lock_barrier = Barrier(2)
    with customer_lock_barrier(lock_barrier), ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                concurrent_create_subscription,
                actor_id=owner.pk,
                key="t018-concurrent-same-key",
                payload=create_payload(),
                barrier=request_barrier,
            )
            for _ in range(2)
        ]
        results = [future.result(timeout=30) for future in futures]

    assert sorted(status for status, _payload in results) == [201, 201]
    assert sorted(
        payload["data"]["idempotent_replay"]
        for _status, payload in results
    ) == [False, True]
    response_data = [payload["data"] for _status, payload in results]
    canonical_responses = [
        {
            key: value
            for key, value in data.items()
            if key != "idempotent_replay"
        }
        for data in response_data
    ]
    assert canonical_responses[0] == canonical_responses[1]
    subscription = CustomerSubscription.objects.get()
    assert all(
        data["subscription_id"] == str(subscription.public_id)
        for data in response_data
    )
    assert CareRecord.objects.count() == 1
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="createMySubscription",
        idempotency_key="t018-concurrent-same-key",
    ).count() == 1


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_same_key_different_payload_has_one_winner():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    owner = create_customer(91)
    create_product()
    request_barrier = Barrier(2)
    lock_barrier = Barrier(2)
    payloads = (
        create_payload(management_type_code="SELF_MANAGED"),
        create_payload(management_type_code="VISIT_CARE"),
    )
    with customer_lock_barrier(lock_barrier), ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                concurrent_create_subscription,
                actor_id=owner.pk,
                key="t018-concurrent-conflicting-payload",
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
        result_payload
        for _request_payload, (status, result_payload) in outcomes
        if status == 409
    )
    assert conflict["error"]["code"] == "DUPLICATE-EVENT-01"
    winner_request, (_status, winner_response) = next(
        outcome for outcome in outcomes if outcome[1][0] == 201
    )
    subscription = CustomerSubscription.objects.get()
    assert subscription.management_type_code == winner_request[
        "management_type_code"
    ]
    assert winner_response["data"]["subscription_id"] == str(
        subscription.public_id
    )
    assert winner_response["data"]["management_type_code"] == (
        winner_request["management_type_code"]
    )
    assert CareRecord.objects.count() == 1
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="createMySubscription",
        idempotency_key="t018-concurrent-conflicting-payload",
    ).count() == 1


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_new_keys_prevent_duplicate_active_product():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    owner = create_customer(92)
    create_product()
    request_barrier = Barrier(2)
    lock_barrier = Barrier(2)
    keys = ("t018-concurrent-key-a", "t018-concurrent-key-b")
    with customer_lock_barrier(lock_barrier), ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                concurrent_create_subscription,
                actor_id=owner.pk,
                key=key,
                payload=create_payload(),
                barrier=request_barrier,
            )
            for key in keys
        ]
        results = [future.result(timeout=30) for future in futures]

    assert sorted(status for status, _payload in results) == [201, 409]
    conflict = next(payload for status, payload in results if status == 409)
    assert conflict["error"]["code"] == "SUBSCRIPTION_ALREADY_ACTIVE"
    assert CustomerSubscription.objects.count() == 1
    assert CareRecord.objects.count() == 1
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="createMySubscription",
    ).count() == 1


def create_active_subscription(owner: User, product: ProductModel):
    return CustomerSubscription.objects.create(
        contract_no=f"T018-CONCURRENT-{uuid4().hex}",
        customer=owner.customer_profile,
        product_model=product,
        serial_no=f"T018-CONCURRENT-SERIAL-{uuid4().hex}",
        management_type_code="SELF_MANAGED",
        status_code="ACTIVE",
        started_on=date(2026, 8, 1),
    )


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_patch_same_key_is_one_write_and_one_replay():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    owner = create_customer(93)
    subscription = create_active_subscription(owner, create_product())
    request_barrier = Barrier(2)
    lock_barrier = Barrier(2)
    payload = {
        "management_type_code": "VISIT_CARE",
        "last_care_on": "2026-08-08",
    }
    with customer_lock_barrier(lock_barrier), ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                concurrent_update_subscription,
                actor_id=owner.pk,
                subscription_id=subscription.public_id,
                key="t018-concurrent-patch-same-key",
                payload=payload,
                barrier=request_barrier,
            )
            for _ in range(2)
        ]
        results = [future.result(timeout=30) for future in futures]

    assert sorted(status for status, _payload in results) == [200, 200]
    assert sorted(
        payload["data"]["idempotent_replay"]
        for _status, payload in results
    ) == [False, True]
    response_data = [payload["data"] for _status, payload in results]
    canonical_responses = [
        {
            key: value
            for key, value in data.items()
            if key != "idempotent_replay"
        }
        for data in response_data
    ]
    assert canonical_responses[0] == canonical_responses[1]
    subscription.refresh_from_db()
    assert all(
        data["subscription_id"] == str(subscription.public_id)
        for data in response_data
    )
    assert subscription.management_type_code == "VISIT_CARE"
    assert CareRecord.objects.filter(subscription=subscription).count() == 1
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="updateMySubscription",
        idempotency_key="t018-concurrent-patch-same-key",
    ).count() == 1


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_patch_same_key_different_payload_has_one_winner():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    owner = create_customer(94)
    subscription = create_active_subscription(owner, create_product())
    request_barrier = Barrier(2)
    lock_barrier = Barrier(2)
    payloads = (
        {"management_type_code": "VISIT_CARE"},
        {"started_on": "2026-07-15"},
    )
    with customer_lock_barrier(lock_barrier), ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                concurrent_update_subscription,
                actor_id=owner.pk,
                subscription_id=subscription.public_id,
                key="t018-concurrent-patch-conflict",
                payload=payload,
                barrier=request_barrier,
            )
            for payload in payloads
        ]
        outcomes = [
            (payload, future.result(timeout=30))
            for payload, future in zip(payloads, futures, strict=True)
        ]

    assert sorted(result[0] for _payload, result in outcomes) == [200, 409]
    conflict = next(
        result_payload
        for _request_payload, (status, result_payload) in outcomes
        if status == 409
    )
    assert conflict["error"]["code"] == "DUPLICATE-EVENT-01"
    winner_request, (_status, winner_response) = next(
        outcome for outcome in outcomes if outcome[1][0] == 200
    )
    subscription.refresh_from_db()
    expected_management_type = winner_request.get(
        "management_type_code", "SELF_MANAGED"
    )
    expected_started_on = date.fromisoformat(
        winner_request.get("started_on", "2026-08-01")
    )
    assert subscription.management_type_code == expected_management_type
    assert subscription.started_on == expected_started_on
    assert winner_response["data"]["management_type_code"] == (
        expected_management_type
    )
    assert winner_response["data"]["started_on"] == (
        expected_started_on.isoformat()
    )
    assert CareRecord.objects.filter(subscription=subscription).count() == 0
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="updateMySubscription",
        idempotency_key="t018-concurrent-patch-conflict",
    ).count() == 1


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_patch_new_keys_preserve_both_partial_updates():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    owner = create_customer(95)
    subscription = create_active_subscription(owner, create_product())
    request_barrier = Barrier(2)
    lock_barrier = Barrier(2)
    requests = (
        ("t018-concurrent-patch-key-a", {"started_on": "2026-07-15"}),
        (
            "t018-concurrent-patch-key-b",
            {"management_type_code": "VISIT_CARE"},
        ),
    )
    with customer_lock_barrier(lock_barrier), ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                concurrent_update_subscription,
                actor_id=owner.pk,
                subscription_id=subscription.public_id,
                key=key,
                payload=payload,
                barrier=request_barrier,
            )
            for key, payload in requests
        ]
        results = [future.result(timeout=30) for future in futures]

    assert sorted(status for status, _payload in results) == [200, 200]
    subscription.refresh_from_db()
    assert subscription.started_on == date(2026, 7, 15)
    assert subscription.management_type_code == "VISIT_CARE"
    assert IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="updateMySubscription",
    ).count() == 2


def test_create_rolls_back_subscription_care_and_idempotency_on_late_failure(
    monkeypatch,
):
    owner = create_customer(96)
    create_product()

    def fail_completion(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("private-t018-create-late-error")

    monkeypatch.setattr(
        WorkflowRepository,
        "complete_idempotency_record",
        fail_completion,
    )
    response = client_for(owner).post(
        "/api/v1/me/subscriptions",
        create_payload(),
        format="json",
        **write_headers("t018-create-rollback"),
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private-t018-create-late-error" not in response.content.decode()
    assert CustomerSubscription.objects.count() == 0
    assert CareRecord.objects.count() == 0
    assert IdempotencyRecord.objects.count() == 0


def test_patch_rolls_back_updates_care_and_idempotency_on_late_failure(
    monkeypatch,
):
    owner = create_customer(97)
    subscription = create_active_subscription(owner, create_product())

    def fail_completion(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("private-t018-patch-late-error")

    monkeypatch.setattr(
        WorkflowRepository,
        "complete_idempotency_record",
        fail_completion,
    )
    response = client_for(owner).patch(
        f"/api/v1/me/subscriptions/{subscription.public_id}",
        {
            "started_on": "2026-07-15",
            "management_type_code": "VISIT_CARE",
            "last_care_on": "2026-08-08",
        },
        format="json",
        **write_headers("t018-patch-rollback"),
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private-t018-patch-late-error" not in response.content.decode()
    subscription.refresh_from_db()
    assert subscription.started_on == date(2026, 8, 1)
    assert subscription.management_type_code == "SELF_MANAGED"
    assert CareRecord.objects.filter(subscription=subscription).count() == 0
    assert IdempotencyRecord.objects.count() == 0
