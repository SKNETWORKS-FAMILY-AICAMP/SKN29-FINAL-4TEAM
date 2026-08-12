"""Official CONS-04 customer-search fixture tests."""

import json
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.inquiries.management.commands.seed_demo_cons04_phone_inquiry import (
    DEMO_CUSTOMER_PHONE,
    DEMO_SUBSCRIPTION_PUBLIC_ID,
)


pytestmark = pytest.mark.django_db

SEARCH_PATH = "/api/v1/consultant/customer-subscriptions/search"


def prepare_fixture() -> dict:
    call_command("seed_demo_accounts", stdout=StringIO())
    call_command("seed_demo_products", stdout=StringIO())
    output = StringIO()
    call_command("seed_demo_cons04_phone_inquiry", "--json", stdout=output)
    return json.loads(output.getvalue())


def test_seed_is_idempotent_and_publishes_stable_search_values():
    first = prepare_fixture()
    second = StringIO()
    call_command("seed_demo_cons04_phone_inquiry", "--json", stdout=second)

    assert first == json.loads(second.getvalue())
    assert first["subscription_id"] == str(DEMO_SUBSCRIPTION_PUBLIC_ID)
    assert first["search_query_phone"] == "1204"
    assert first["phone_expected_masked"] == "010-****-1204"


def test_name_and_phone_search_return_masked_same_subscription():
    fixture = prepare_fixture()
    consultant = User.objects.get(username="DEMO-CONSULTANT-001")
    client = APIClient()
    client.force_authenticate(consultant)

    by_name = client.post(
        SEARCH_PATH,
        {"query": fixture["search_query_name"]},
        format="json",
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )
    by_phone = client.post(
        SEARCH_PATH,
        {"query": fixture["search_query_phone"]},
        format="json",
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )

    assert by_name.status_code == by_phone.status_code == 200
    name_item = by_name.data["data"]["items"][0]
    phone_item = by_phone.data["data"]["items"][0]
    assert name_item["subscription_id"] == fixture["subscription_id"]
    assert phone_item["subscription_id"] == fixture["subscription_id"]
    assert name_item["phone_masked"] == "010-****-1204"
    assert phone_item["phone_masked"] == "010-****-1204"
    assert DEMO_CUSTOMER_PHONE not in str(by_name.data)
    assert DEMO_CUSTOMER_PHONE not in str(by_phone.data)
