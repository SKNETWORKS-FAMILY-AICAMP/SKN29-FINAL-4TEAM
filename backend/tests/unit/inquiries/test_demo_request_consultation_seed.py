"""Official Mobile REQUEST_CONSULTATION fixture tests."""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.consultations.models import Consultation
from apps.inquiries.management.commands.seed_demo_request_consultation import (
    DEMO_CUSTOMER_USERNAME,
    DEMO_INQUIRY_PUBLIC_ID,
    DEMO_INITIAL_STATE_VERSION,
)
from apps.inquiries.models import Inquiry


pytestmark = pytest.mark.django_db


def prepare_dependencies() -> None:
    call_command("seed_demo_accounts", stdout=StringIO())
    call_command("seed_demo_products", stdout=StringIO())
    call_command("seed_demo_subscriptions", stdout=StringIO())


def test_seed_is_idempotent_before_the_fixture_is_consumed():
    prepare_dependencies()
    first = StringIO()
    second = StringIO()

    call_command("seed_demo_request_consultation", "--json", stdout=first)
    call_command("seed_demo_request_consultation", "--json", stdout=second)

    assert json.loads(first.getvalue()) == json.loads(second.getvalue())
    payload = json.loads(first.getvalue())
    assert payload["demo_user_code"] == DEMO_CUSTOMER_USERNAME
    assert payload["inquiry_id"] == str(DEMO_INQUIRY_PUBLIC_ID)
    assert payload["status_code"] == Inquiry.Status.AI_GUIDANCE
    assert payload["state_version"] == DEMO_INITIAL_STATE_VERSION
    assert Inquiry.objects.filter(public_id=DEMO_INQUIRY_PUBLIC_ID).count() == 1


def test_consumed_fixture_is_not_silently_reset():
    prepare_dependencies()
    call_command("seed_demo_request_consultation", stdout=StringIO())
    owner = User.objects.get(username=DEMO_CUSTOMER_USERNAME)
    client = APIClient()
    client.force_authenticate(owner)
    response = client.post(
        (
            f"/api/v1/inquiries/{DEMO_INQUIRY_PUBLIC_ID}"
            "/request-consultation"
        ),
        {"state_version": DEMO_INITIAL_STATE_VERSION},
        format="json",
        HTTP_IDEMPOTENCY_KEY="seed-consumption-test-001",
        HTTP_X_CORRELATION_ID="11111111-1111-4111-8111-111111111111",
    )

    assert response.status_code == 200
    assert Consultation.objects.filter(
        inquiry__public_id=DEMO_INQUIRY_PUBLIC_ID
    ).count() == 1
    with pytest.raises(CommandError, match="이미 소비"):
        call_command("seed_demo_request_consultation", stdout=StringIO())
