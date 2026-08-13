"""T-019 owner-only completed care history Runtime tests."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.care.models import CareRecord
from apps.care.services.care_history_service import CareHistoryService
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import IdempotencyRecord


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
