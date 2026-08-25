"""CR-001 consultant customer search and phone inquiry Runtime tests."""

from datetime import date
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AIRun
from apps.inquiries.models import Inquiry, SymptomEntry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import IdempotencyRecord, TransitionHistory
from common.privacy import mask_person_name


pytestmark = pytest.mark.django_db

SEARCH_PATH = "/api/v1/consultant/customer-subscriptions/search"
REGISTER_PATH = "/api/v1/consultant/phone-inquiries"


def create_user(*, sequence: int, role: str, synthetic: bool = True) -> User:
    return User.objects.create_user(
        username=f"CONS04-{role}-{sequence:03d}",
        password=None,
        full_name=f"CONS04 {role} {sequence}",
        role_code=role,
        employee_no=(None if role == User.Role.CUSTOMER else f"EMP-{sequence:03d}"),
        is_synthetic=synthetic,
    )


def create_subscription(
    *,
    sequence: int,
    status: str = CustomerSubscription.Status.ACTIVE,
    user_synthetic: bool = True,
) -> CustomerSubscription:
    customer_user = create_user(
        sequence=sequence,
        role=User.Role.CUSTOMER,
        synthetic=user_synthetic,
    )
    customer = CustomerProfile.objects.create(
        user=customer_user,
        customer_no=f"CONS04-CUSTOMER-{sequence:03d}",
        customer_name=f"합성 전화 고객 {sequence}",
        phone=f"010-0000-{sequence:04d}",
        is_synthetic=True,
    )
    product = ProductModel.objects.create(
        model_code=f"CONS04-MODEL-{sequence:03d}",
        model_name=f"합성 전화 제품 {sequence}",
        is_supported_mvp=True,
    )
    return CustomerSubscription.objects.create(
        contract_no=f"CONS04-CONTRACT-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"CONS04-SERIAL-{sequence:03d}",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=status,
        started_on=date(2026, 8, 1),
        ended_on=(date(2026, 8, 10) if status != "ACTIVE" else None),
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def headers(*, key: str = "cons04-register-key") -> dict[str, str]:
    return {
        "HTTP_X_CORRELATION_ID": str(uuid4()),
        "HTTP_IDEMPOTENCY_KEY": key,
    }


def register_payload(subscription: CustomerSubscription) -> dict:
    return {
        "subscription_id": str(subscription.public_id),
        "raw_text": "전화로 접수한 합성 고객의 누수 문의입니다.",
        "representative_symptom_code": "LEAK",
        "priority_code": "HIGH",
    }


def test_search_returns_only_masked_synthetic_active_subscriptions():
    consultant = create_user(sequence=1, role=User.Role.CONSULTANT)
    active = create_subscription(sequence=11)
    create_subscription(
        sequence=12,
        status=CustomerSubscription.Status.CANCELLED,
    )
    create_subscription(sequence=13, user_synthetic=False)
    client = authenticated_client(consultant)

    by_name = client.post(
        SEARCH_PATH,
        {"query": "합성 전화 고객", "limit": 20},
        format="json",
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )
    by_phone = client.post(
        SEARCH_PATH,
        {"query": "0000-0011"},
        format="json",
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )

    assert by_name.status_code == 200
    assert by_phone.status_code == 200
    assert by_name.data["data"]["returned_count"] == 1
    assert by_phone.data["data"]["returned_count"] == 1
    item = by_name.data["data"]["items"][0]
    expected_display_name = mask_person_name(active.customer.customer_name)
    assert item == {
        "customer_id": str(active.customer.public_id),
        "customer_display_name": expected_display_name,
        "phone_masked": "010-****-0011",
        "subscription_id": str(active.public_id),
        "subscription_status": "ACTIVE",
        "management_type_code": "VISIT_CARE",
        "product_id": str(active.product_model.public_id),
        "product_model_code": active.product_model.model_code,
        "product_name": active.product_model.model_name,
    }
    assert expected_display_name != active.customer.customer_name
    assert active.customer.customer_name not in str(by_name.data)
    assert active.customer.customer_name not in str(by_phone.data)
    assert active.customer.phone not in str(by_name.data)


@pytest.mark.parametrize(
    ("payload", "expected_field"),
    [
        ({"query": "010"}, "query"),
        ({"query": "고", "extra": True}, "extra"),
    ],
)
def test_search_rejects_short_phone_and_unknown_fields(payload, expected_field):
    consultant = create_user(sequence=2, role=User.Role.CONSULTANT)
    response = authenticated_client(consultant).post(
        SEARCH_PATH,
        payload,
        format="json",
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )

    assert response.status_code == 422
    assert expected_field in response.data["error"]["details"]


def test_search_requires_consultant_and_strict_correlation_header():
    customer = create_user(sequence=3, role=User.Role.CUSTOMER)
    consultant = create_user(sequence=4, role=User.Role.CONSULTANT)

    forbidden = authenticated_client(customer).post(
        SEARCH_PATH,
        {"query": "합성"},
        format="json",
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )
    invalid_trace = authenticated_client(consultant).post(
        SEARCH_PATH,
        {"query": "합성"},
        format="json",
    )

    assert forbidden.status_code == 403
    assert invalid_trace.status_code == 422


def test_register_creates_assigned_phone_inquiry_and_history_without_ai():
    consultant = create_user(sequence=5, role=User.Role.CONSULTANT)
    subscription = create_subscription(sequence=21)
    correlation_id = uuid4()
    response = authenticated_client(consultant).post(
        REGISTER_PATH,
        register_payload(subscription),
        format="json",
        HTTP_X_CORRELATION_ID=str(correlation_id),
        HTTP_IDEMPOTENCY_KEY="cons04-create-001",
    )

    assert response.status_code == 201
    data = response.data["data"]
    inquiry = Inquiry.objects.get(public_id=data["inquiry_id"])
    symptom = SymptomEntry.objects.get(inquiry=inquiry)
    history = TransitionHistory.objects.get(inquiry=inquiry)
    assert inquiry.subscription == subscription
    assert inquiry.initiated_by == consultant
    assert inquiry.assigned_user == consultant
    assert inquiry.assigned_role_code == Inquiry.AssignedRole.CONSULTANT
    assert inquiry.channel_code == Inquiry.Channel.PHONE
    assert inquiry.priority_code == Inquiry.Priority.HIGH
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 1
    assert inquiry.source_correlation_id == correlation_id
    assert symptom.symptom_type_code == "LEAK"
    assert symptom.is_customer_confirmed is False
    assert history.event_code == "REGISTER_PHONE_INQUIRY"
    assert history.from_state is None
    assert history.to_state == Inquiry.Status.CONSULTATION_REQUIRED
    assert history.actor == consultant
    assert history.correlation_id == correlation_id
    assert [item["code"] for item in data["allowed_actions"]] == [
        "START_CONSULTATION"
    ]
    assert AIRun.objects.filter(inquiry=inquiry).count() == 0


def test_register_replays_same_request_and_rejects_key_reuse():
    consultant = create_user(sequence=6, role=User.Role.CONSULTANT)
    subscription = create_subscription(sequence=22)
    client = authenticated_client(consultant)
    payload = register_payload(subscription)
    request_headers = headers(key="cons04-replay-001")

    created = client.post(
        REGISTER_PATH,
        payload,
        format="json",
        **request_headers,
    )
    replayed = client.post(
        REGISTER_PATH,
        payload,
        format="json",
        **headers(key="cons04-replay-001"),
    )
    changed = dict(payload, priority_code="URGENT")
    conflicted = client.post(
        REGISTER_PATH,
        changed,
        format="json",
        **headers(key="cons04-replay-001"),
    )

    assert created.status_code == replayed.status_code == 201
    assert created.data["data"]["idempotent_replay"] is False
    assert replayed.data["data"]["idempotent_replay"] is True
    assert created.data["data"]["inquiry_id"] == replayed.data["data"]["inquiry_id"]
    assert Inquiry.objects.filter(subscription=subscription).count() == 1
    assert TransitionHistory.objects.filter(
        event_code="REGISTER_PHONE_INQUIRY"
    ).count() == 1
    assert IdempotencyRecord.objects.filter(
        operation_id="registerConsultantPhoneInquiry"
    ).count() == 1
    assert conflicted.status_code == 409


def test_register_masks_unavailable_subscription_and_role_boundaries():
    consultant = create_user(sequence=7, role=User.Role.CONSULTANT)
    customer = create_user(sequence=8, role=User.Role.CUSTOMER)
    inactive = create_subscription(
        sequence=23,
        status=CustomerSubscription.Status.CANCELLED,
    )

    hidden = authenticated_client(consultant).post(
        REGISTER_PATH,
        register_payload(inactive),
        format="json",
        **headers(key="cons04-hidden-001"),
    )
    forbidden = authenticated_client(customer).post(
        REGISTER_PATH,
        register_payload(inactive),
        format="json",
        **headers(key="cons04-role-001"),
    )

    assert hidden.status_code == 404
    assert forbidden.status_code == 403
    assert Inquiry.objects.count() == 0


def test_register_rejects_missing_headers_and_unknown_body_fields():
    consultant = create_user(sequence=9, role=User.Role.CONSULTANT)
    subscription = create_subscription(sequence=24)
    client = authenticated_client(consultant)
    payload = register_payload(subscription)

    no_idempotency = client.post(
        REGISTER_PATH,
        payload,
        format="json",
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )
    no_correlation = client.post(
        REGISTER_PATH,
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY="cons04-no-trace",
    )
    unknown = client.post(
        REGISTER_PATH,
        dict(payload, customer_name="do-not-trust"),
        format="json",
        **headers(key="cons04-unknown-001"),
    )

    assert no_idempotency.status_code == 422
    assert no_correlation.status_code == 422
    assert unknown.status_code == 422
    assert Inquiry.objects.count() == 0
