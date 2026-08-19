"""End-to-end Runtime checks for T-018 owner subscription reads."""

from __future__ import annotations

from datetime import date, datetime, timezone as datetime_timezone
from uuid import UUID, uuid4

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.care.models import CareRecord
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db

SUPPORTED_CODE = "WPUJAC104DWH"
SUPPORTED_CODES = (
    "WPUJAC104DWH",
    "WPUIAC425SNW",
    "WPUIAC606SNW",
)


def create_user(sequence: int, *, role_code=User.Role.CUSTOMER) -> User:
    employee_no = (
        None
        if role_code == User.Role.CUSTOMER
        else f"T018-EMP-{sequence:03d}"
    )
    user = User.objects.create_user(
        username=f"T018-{role_code}-{sequence:03d}",
        full_name=f"T018 {role_code} {sequence}",
        role_code=role_code,
        employee_no=employee_no,
        is_synthetic=True,
    )
    if role_code == User.Role.CUSTOMER:
        CustomerProfile.objects.create(
            user=user,
            customer_no=f"T018-CUSTOMER-{sequence:03d}",
            customer_name=f"T018 customer {sequence}",
            is_synthetic=True,
        )
    return user


def create_product(
    sequence: int,
    *,
    model_code: str = SUPPORTED_CODE,
    is_active: bool = True,
    is_supported_mvp: bool = True,
) -> ProductModel:
    return ProductModel.objects.create(
        model_code=model_code,
        model_name=f"T018 purifier {sequence}",
        generation_code="D",
        manufacturer="SK magic",
        is_supported_mvp=is_supported_mvp,
        is_active=is_active,
        features={"private": "must-not-leak"},
    )


def create_subscription(
    owner: User,
    product: ProductModel,
    sequence: int,
    *,
    status_code: str = CustomerSubscription.Status.ACTIVE,
    started_on: date = date(2026, 7, 1),
    public_id: UUID | None = None,
) -> CustomerSubscription:
    ended_on = (
        date(2026, 8, 1)
        if status_code
        in {
            CustomerSubscription.Status.CANCELLED,
            CustomerSubscription.Status.EXPIRED,
        }
        else None
    )
    return CustomerSubscription.objects.create(
        public_id=public_id or uuid4(),
        contract_no=f"T018-CONTRACT-{sequence:03d}",
        customer=owner.customer_profile,
        product_model=product,
        serial_no=f"T018-SERIAL-{sequence:03d}",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=status_code,
        started_on=started_on,
        ended_on=ended_on,
        next_care_on=date(2026, 9, 30),
        installation_address="must-not-leak",
    )


def create_completed_care(
    subscription: CustomerSubscription,
    owner: User,
    sequence: int,
    *,
    performed_on: date | None,
    completed_at: datetime | None,
    source_code: str,
) -> CareRecord:
    is_import = source_code == CareRecord.Source.IMPORT
    return CareRecord.objects.create(
        care_code=f"T018-CARE-{sequence:03d}",
        subscription=subscription,
        care_type_code=CareRecord.CareType.PERIODIC_CHECK,
        status_code=CareRecord.Status.COMPLETED,
        performed_on=performed_on,
        result_code=(CareRecord.Result.NORMAL if is_import else None),
        completed_at=completed_at,
        performed_by=(None if is_import else owner),
        source_code=source_code,
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def assert_safe_summary(item: dict) -> None:
    assert set(item) == {
        "subscription_id",
        "status_code",
        "management_type_code",
        "started_on",
        "last_care_on",
        "next_care_on",
        "product",
    }
    assert set(item["product"]) == {
        "product_model_id",
        "model_code",
        "model_name",
        "generation_code",
        "manufacturer",
    }
    serialized = str(item)
    for forbidden in (
        "contract_no",
        "serial_no",
        "installation_address",
        "features",
        "customer_name",
    ):
        assert forbidden not in serialized


def test_list_and_detail_expose_three_supported_models_and_hide_candidate():
    owner = create_user(20)
    expected_subscriptions = []
    for sequence, model_code in enumerate(SUPPORTED_CODES, start=20):
        product = create_product(sequence, model_code=model_code)
        expected_subscriptions.append(
            create_subscription(owner, product, sequence)
        )
    candidate_product = create_product(
        30,
        model_code="WPU-CANDIDATE-ONLY",
        is_supported_mvp=False,
    )
    candidate = create_subscription(owner, candidate_product, 30)
    client = authenticated_client(owner)

    response = client.get("/api/v1/me/subscriptions")
    assert response.status_code == 200
    assert {
        item["product"]["model_code"]
        for item in response.json()["data"]["items"]
    } == set(SUPPORTED_CODES)

    for subscription in expected_subscriptions:
        detail = client.get(
            f"/api/v1/me/subscriptions/{subscription.public_id}"
        )
        assert detail.status_code == 200
        assert detail.json()["data"]["product"]["model_code"] == (
            subscription.product_model.model_code
        )
    assert client.get(
        f"/api/v1/me/subscriptions/{candidate.public_id}"
    ).status_code == 404


def test_list_filters_orders_paginates_and_projects_last_care(
    django_assert_num_queries,
):
    owner = create_user(1)
    product = create_product(1)
    older = create_subscription(
        owner,
        product,
        1,
        started_on=date(2026, 7, 1),
    )
    first_tie = create_subscription(
        owner,
        product,
        2,
        started_on=date(2026, 8, 1),
        public_id=UUID("20000000-0000-4000-8000-000000000001"),
    )
    second_tie = create_subscription(
        owner,
        product,
        3,
        started_on=date(2026, 8, 1),
        public_id=UUID("20000000-0000-4000-8000-000000000002"),
    )
    create_completed_care(
        first_tie,
        owner,
        1,
        performed_on=date(2026, 7, 30),
        completed_at=datetime(
            2026,
            8,
            5,
            0,
            0,
            tzinfo=datetime_timezone.utc,
        ),
        source_code=CareRecord.Source.IMPORT,
    )
    create_completed_care(
        first_tie,
        owner,
        2,
        performed_on=None,
        completed_at=datetime(
            2026,
            7,
            31,
            16,
            0,
            tzinfo=datetime_timezone.utc,
        ),
        source_code=CareRecord.Source.CUSTOMER,
    )
    CareRecord.objects.create(
        care_code="T018-CARE-SCHEDULED",
        subscription=first_tie,
        care_type_code=CareRecord.CareType.PERIODIC_CHECK,
        status_code=CareRecord.Status.SCHEDULED,
        scheduled_on=date(2026, 8, 7),
    )

    with django_assert_num_queries(3):
        response = authenticated_client(owner).get(
            "/api/v1/me/subscriptions?page=1&size=2"
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["size"] == 2
    assert [item["subscription_id"] for item in data["items"]] == [
        str(first_tie.public_id),
        str(second_tie.public_id),
    ]
    assert data["items"][0]["last_care_on"] == "2026-08-01"
    assert data["items"][1]["last_care_on"] is None
    assert_safe_summary(data["items"][0])

    second_page = authenticated_client(owner).get(
        "/api/v1/me/subscriptions?page=2&size=2"
    )
    assert second_page.status_code == 200
    assert second_page.json()["data"]["items"][0][
        "subscription_id"
    ] == str(older.public_id)


def test_list_hides_wrong_owner_status_model_and_deleted_profile():
    owner = create_user(1)
    other = create_user(2)
    supported = create_product(1)
    unsupported = create_product(2, model_code="OTHER-MODEL")
    visible = create_subscription(owner, supported, 1)
    create_subscription(
        owner,
        supported,
        2,
        status_code=CustomerSubscription.Status.SUSPENDED,
    )
    create_subscription(owner, unsupported, 3)
    create_subscription(other, supported, 5)

    response = authenticated_client(owner).get("/api/v1/me/subscriptions")

    assert response.status_code == 200
    assert [
        item["subscription_id"]
        for item in response.json()["data"]["items"]
    ] == [str(visible.public_id)]

    CustomerProfile.objects.filter(pk=owner.customer_profile.pk).update(
        deleted_at=timezone.now()
    )
    deleted_response = authenticated_client(owner).get(
        "/api/v1/me/subscriptions"
    )
    assert deleted_response.status_code == 200
    assert deleted_response.json()["data"]["items"] == []


def test_detail_returns_exact_projection_and_owner_scoped_404s():
    owner = create_user(1)
    other = create_user(2)
    supported = create_product(1)
    unsupported = create_product(2, model_code="OTHER-MODEL")
    visible = create_subscription(owner, supported, 1)
    other_owned = create_subscription(other, supported, 2)
    suspended = create_subscription(
        owner,
        supported,
        3,
        status_code=CustomerSubscription.Status.SUSPENDED,
    )
    wrong_model = create_subscription(owner, unsupported, 4)

    client = authenticated_client(owner)
    response = client.get(
        f"/api/v1/me/subscriptions/{visible.public_id}"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == {
        "subscription_id",
        "status_code",
        "management_type_code",
        "started_on",
        "ended_on",
        "last_care_on",
        "next_care_on",
        "product",
    }
    assert data["subscription_id"] == str(visible.public_id)
    assert data["ended_on"] is None
    assert_safe_summary({key: value for key, value in data.items() if key != "ended_on"})

    hidden_ids = (
        other_owned.public_id,
        suspended.public_id,
        wrong_model.public_id,
        uuid4(),
    )
    for subscription_id in hidden_ids:
        hidden_response = client.get(
            f"/api/v1/me/subscriptions/{subscription_id}"
        )
        assert hidden_response.status_code == 404
        assert hidden_response.json()["error"]["code"] == (
            "RESOURCE_NOT_FOUND"
        )

    invalid_uuid = client.get("/api/v1/me/subscriptions/not-a-uuid")
    assert invalid_uuid.status_code == 404


def test_inactive_supported_product_is_hidden_from_list_and_detail():
    owner = create_user(1)
    inactive_product = create_product(1, is_active=False)
    subscription = create_subscription(owner, inactive_product, 1)
    client = authenticated_client(owner)

    list_response = client.get("/api/v1/me/subscriptions")
    detail_response = client.get(
        f"/api/v1/me/subscriptions/{subscription.public_id}"
    )

    assert list_response.status_code == 200
    assert list_response.json()["data"]["items"] == []
    assert detail_response.status_code == 404


def test_authentication_role_and_query_validation_boundaries():
    owner = create_user(1)
    consultant = create_user(2, role_code=User.Role.CONSULTANT)
    visible = create_subscription(owner, create_product(1), 1)

    assert APIClient().get("/api/v1/me/subscriptions").status_code == 401
    assert authenticated_client(consultant).get(
        "/api/v1/me/subscriptions"
    ).status_code == 403

    owner.is_active = False
    assert authenticated_client(owner).get(
        "/api/v1/me/subscriptions"
    ).status_code == 403
    owner.is_active = True

    owner_client = authenticated_client(owner)
    invalid_paths = (
        "/api/v1/me/subscriptions?status_code=ACTIVE",
        "/api/v1/me/subscriptions?page=0",
        "/api/v1/me/subscriptions?page=abc",
        "/api/v1/me/subscriptions?size=101",
        f"/api/v1/me/subscriptions/{visible.public_id}?expand=product",
    )
    for path in invalid_paths:
        response = owner_client.get(path)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
