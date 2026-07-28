"""T-017 합성 Demo Seed의 Upsert 재실행 안전성 검증."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.accounts.models import CustomerProfile, User


pytestmark = pytest.mark.django_db


def test_demo_seed_is_idempotent_and_contains_no_real_profile_data():
    first_output = StringIO()
    second_output = StringIO()

    call_command("seed_demo_accounts", stdout=first_output)
    call_command("seed_demo_accounts", stdout=second_output)

    assert User.objects.filter(username__startswith="DEMO-").count() == 4
    assert CustomerProfile.objects.count() == 1
    customer = CustomerProfile.objects.get(pk="DEMO-CUS-001")
    assert customer.user_id == "DEMO-USR-001"
    assert customer.is_synthetic is True
    assert customer.phone == ""
    assert customer.address_line1 == ""
    assert "created=4" in first_output.getvalue()
    assert "updated=4" in second_output.getvalue()
