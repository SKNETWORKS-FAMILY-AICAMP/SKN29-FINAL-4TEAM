"""QA seed checks for the consultant inquiry read integration slice."""

from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.management.commands.seed_demo_consultant_inquiry import (
    DEMO_CONSULTANT_USERNAME,
    DEMO_CUSTOMER_NO,
    DEMO_INQUIRY_PUBLIC_ID,
    DEMO_INQUIRY_SCENARIO_CODE,
)
from apps.inquiries.models import Inquiry, SymptomAssessment


pytestmark = pytest.mark.django_db


def test_demo_consultant_inquiry_seed_requires_demo_accounts():
    with pytest.raises(CommandError, match="seed_demo_accounts"):
        call_command("seed_demo_consultant_inquiry")


def test_demo_consultant_inquiry_seed_is_idempotent_and_preserves_identity():
    call_command("seed_demo_accounts")
    first_output = StringIO()
    second_output = StringIO()

    call_command("seed_demo_consultant_inquiry", stdout=first_output)
    first = Inquiry.objects.get(scenario_code=DEMO_INQUIRY_SCENARIO_CODE)
    first_identity = (first.pk, first.public_id, first.inquiry_code)

    call_command("seed_demo_consultant_inquiry", stdout=second_output)
    second = Inquiry.objects.get(scenario_code=DEMO_INQUIRY_SCENARIO_CODE)

    assert Inquiry.objects.filter(
        scenario_code=DEMO_INQUIRY_SCENARIO_CODE
    ).count() == 1
    assert (second.pk, second.public_id, second.inquiry_code) == first_identity
    assert second.public_id == DEMO_INQUIRY_PUBLIC_ID
    assert second.assigned_user.username == DEMO_CONSULTANT_USERNAME
    assert second.assigned_role_code == Inquiry.AssignedRole.CONSULTANT
    assert second.subscription.customer.customer_no == DEMO_CUSTOMER_NO
    assert second.subscription.customer.phone == "010-0000-0000"
    assert second.subscription.customer.is_synthetic is True
    assert second.initiated_by.is_synthetic is True
    assert SymptomAssessment.objects.filter(
        inquiry=second,
        assessment_version=1,
    ).count() == 1
    assert "created=1" in first_output.getvalue()
    assert "updated=1" in second_output.getvalue()


def test_demo_consultant_can_read_seeded_list_and_detail(settings):
    settings.DEMO_LOGIN_ENABLED = True
    settings.DEMO_LOGIN_CODES = frozenset(
        {"DEMO-CUSTOMER-001", DEMO_CONSULTANT_USERNAME}
    )
    call_command("seed_demo_accounts")
    call_command("seed_demo_consultant_inquiry")

    client = APIClient()
    login = client.post(
        "/api/v1/auth/demo-login",
        {"demo_user_code": DEMO_CONSULTANT_USERNAME},
        format="json",
    )
    assert login.status_code == 200
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {login.json()['data']['access_token']}"
    )

    inquiry_list = client.get("/api/v1/inquiries")
    assert inquiry_list.status_code == 200
    list_payload = inquiry_list.json()
    assert list_payload["data"]["page_info"]["total"] == 1
    assert list_payload["data"]["items"][0]["inquiry_id"] == str(
        DEMO_INQUIRY_PUBLIC_ID
    )

    detail = client.get(f"/api/v1/inquiries/{DEMO_INQUIRY_PUBLIC_ID}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["data"]["customer"] == {
        "is_synthetic": True,
        "display_name": "합성 상담조회 고객 001",
        "phone": "010-****-0000",
        "phone_masked": "010-****-0000",
        "contact_phone": None,
    }
    assert detail_payload["metadata"]["correlation_id"] == detail[
        "X-Correlation-ID"
    ]

    hidden = client.get(f"/api/v1/inquiries/{uuid4()}")
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    invalid_query = client.get("/api/v1/inquiries", {"unknown": "1"})
    assert invalid_query.status_code == 422
    assert invalid_query.json()["error"]["code"] == "VALIDATION_ERROR"

    customer_login = APIClient().post(
        "/api/v1/auth/demo-login",
        {"demo_user_code": "DEMO-CUSTOMER-001"},
        format="json",
    )
    customer_client = APIClient()
    customer_client.credentials(
        HTTP_AUTHORIZATION=(
            f"Bearer {customer_login.json()['data']['access_token']}"
        )
    )
    forbidden = customer_client.get("/api/v1/inquiries")
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"
