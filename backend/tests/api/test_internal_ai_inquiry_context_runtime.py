"""Runtime contract for the read-only Backend-to-AI Inquiry Context."""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import FollowUpAnswer, Inquiry, InquiryQA, SymptomEntry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db
TOKEN = "test-protected-ai-context-token"


def create_fixture(
    *,
    sequence: int = 1,
    model_code: str = "WPUJAC104DWH",
    features: dict | None = None,
):
    customer_user = User.objects.create_user(
        username=f"AI-CONTEXT-CUSTOMER-{sequence}",
        password=None,
        full_name="Synthetic private customer",
        phone="010-9876-5432",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    customer = CustomerProfile.objects.create(
        user=customer_user,
        customer_no=f"AI-CONTEXT-CUS-{sequence}",
        customer_name="Never expose this customer",
        phone="010-1234-5678",
        address_line1="Never expose this address",
        is_synthetic=True,
    )
    product = ProductModel.objects.create(
        model_code=model_code,
        model_name=f"Synthetic {model_code}",
        generation_code="D" if model_code == "WPUJAC104DWH" else "ICE",
        manufacturer="SK매직",
        features=features
        or {
            "model_family": "WPU-JAC104",
            "water_modes": ["AMBIENT", "COLD", "COLD"],
            "supported_functions": ["FILTER_STATUS", "FILTER_STATUS"],
            "internal_note": "must not be exposed",
        },
        is_supported_mvp=True,
        is_active=True,
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"AI-CONTEXT-CONTRACT-{sequence}",
        customer=customer,
        product_model=product,
        serial_no=f"AI-CONTEXT-SERIAL-{sequence}",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 8, 1),
        installation_address="Never expose installation address",
    )
    inquiry = Inquiry.objects.create(
        subscription=subscription,
        initiated_by=customer_user,
        channel_code=Inquiry.Channel.MOBILE,
        raw_text="정수기 출수량이 줄었습니다.",
        status_code=Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS,
        state_version=3,
    )
    SymptomEntry.objects.create(
        inquiry=inquiry,
        symptom_type_code="LOW_FLOW",
        structured_payload={},
        is_customer_confirmed=True,
    )
    question = InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=1,
        question_code="WATER_VALVE_OPEN",
        question_text="원수 밸브가 열려 있나요?",
        answer_type_code="FREE_TEXT",
        asked_by_type_code="RULE",
    )
    FollowUpAnswer.objects.create(
        question=question,
        answered_by=customer_user,
        answer_text="예, 열려 있습니다.",
        accepted_state_version=3,
    )
    return inquiry, subscription, product


def get_context(
    inquiry_id,
    *,
    token: str = TOKEN,
    correlation_id: UUID | None = None,
    query: str = "",
):
    correlation_id = correlation_id or uuid4()
    return APIClient().get(
        f"/api/v1/internal/ai/inquiries/{inquiry_id}/context{query}",
        HTTP_X_AI_HANDOFF_TOKEN=token,
        HTTP_X_CORRELATION_ID=str(correlation_id),
    )


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_context_returns_product_inquiry_and_answers_without_writing():
    inquiry, subscription, product = create_fixture()
    correlation_id = uuid4()

    with CaptureQueriesContext(connection) as queries:
        response = get_context(
            inquiry.public_id,
            correlation_id=correlation_id,
        )

    assert response.status_code == 200
    assert len(queries) == 2
    assert all(
        not query["sql"].lstrip().upper().startswith(
            ("INSERT", "UPDATE", "DELETE")
        )
        for query in queries
    )
    assert response.headers["X-Correlation-ID"] == str(correlation_id)
    assert response.json()["metadata"]["correlation_id"] == str(correlation_id)

    data = response.json()["data"]
    assert data == {
        "inquiry_id": str(inquiry.public_id),
        "inquiry_code": inquiry.inquiry_code,
        "status_code": Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS,
        "state_version": 3,
        "correlation_id": str(correlation_id),
        "product_context": {
            "subscription_id": str(subscription.public_id),
            "subscription_status_code": CustomerSubscription.Status.ACTIVE,
            "management_type_code": (
                CustomerSubscription.ManagementType.VISIT_CARE
            ),
            "product_model_id": str(product.public_id),
            "model_code": "WPUJAC104DWH",
            "model_name": "Synthetic WPUJAC104DWH",
            "product_family": "DIRECT_WATER_PURIFIER",
            "generation_code": "D",
            "manufacturer": "SK매직",
            "features": {
                "model_family": "WPU-JAC104",
                "water_modes": ["AMBIENT", "COLD"],
                "supported_functions": ["FILTER_STATUS"],
            },
        },
        "inquiry_context": {
            "customer_query": "정수기 출수량이 줄었습니다.",
            "symptom_type": "LOW_FLOW",
            "selected_symptoms": ["LOW_FLOW"],
            "previous_answers": [
                {
                    "question_id": "WATER_VALVE_OPEN",
                    "answer_text": "예, 열려 있습니다.",
                }
            ],
        },
    }

    serialized = response.content.decode("utf-8")
    for forbidden in (
        "Never expose this customer",
        "010-1234-5678",
        "Never expose this address",
        "AI-CONTEXT-CONTRACT-1",
        "AI-CONTEXT-SERIAL-1",
        "Never expose installation address",
        "internal_note",
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("model_code", "expected_family"),
    [
        ("WPUJAC104DWH", "DIRECT_WATER_PURIFIER"),
        ("WPUIAC425SNW", "ICE_WATER_PURIFIER"),
        ("WPUIAC606SNW", "ICE_WATER_PURIFIER"),
        ("UNKNOWN-MODEL", "UNKNOWN"),
    ],
)
@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_context_uses_exact_subscription_product_identity(
    model_code,
    expected_family,
):
    inquiry, _subscription, _product = create_fixture(
        sequence={
            "WPUJAC104DWH": 10,
            "WPUIAC425SNW": 11,
            "WPUIAC606SNW": 12,
            "UNKNOWN-MODEL": 13,
        }[model_code],
        model_code=model_code,
        features={},
    )

    response = get_context(inquiry.public_id)

    assert response.status_code == 200
    product = response.json()["data"]["product_context"]
    assert product["model_code"] == model_code
    assert product["product_family"] == expected_family


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_context_fails_closed_for_token_object_and_query_boundaries():
    inquiry, _subscription, _product = create_fixture(sequence=20)

    missing_token = get_context(inquiry.public_id, token="")
    wrong_token = get_context(inquiry.public_id, token="wrong-token")
    missing_object = get_context(uuid4())
    unknown_query = get_context(inquiry.public_id, query="?customer_id=1")

    assert missing_token.status_code == 403
    assert missing_token.json()["error"]["code"] == "FORBIDDEN"
    assert wrong_token.status_code == 403
    assert wrong_token.json()["error"]["code"] == "FORBIDDEN"
    assert missing_object.status_code == 404
    assert missing_object.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert unknown_query.status_code == 422
    assert unknown_query.json()["error"]["code"] == "VALIDATION_ERROR"


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_context_requires_caller_correlation_header():
    inquiry, _subscription, _product = create_fixture(sequence=30)

    response = APIClient().get(
        f"/api/v1/internal/ai/inquiries/{inquiry.public_id}/context",
        HTTP_X_AI_HANDOFF_TOKEN=TOKEN,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "X-Correlation-ID" in response.json()["error"]["details"]
