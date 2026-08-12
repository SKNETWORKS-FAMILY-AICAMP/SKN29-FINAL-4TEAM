"""T-018 synthetic customer subscription create/update Runtime tests."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.care.models import CareRecord
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import IdempotencyRecord


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
