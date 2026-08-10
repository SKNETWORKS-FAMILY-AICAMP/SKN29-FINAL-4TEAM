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
    customer = CustomerProfile.objects.get(
        customer_no="DEMO-CUSTOMER-001"
    )
    assert isinstance(customer.pk, int)
    assert isinstance(customer.user_id, int)
    assert customer.legacy_id is None
    assert customer.user.legacy_id is None
    assert customer.public_id is not None
    assert customer.user.public_id is not None
    assert customer.is_synthetic is True
    assert customer.user.is_synthetic is True
    assert not User.objects.filter(
        username__startswith="DEMO-",
        is_synthetic=False,
    ).exists()
    assert customer.phone == ""
    assert customer.address_line1 == ""
    assert "created=4" in first_output.getvalue()
    assert "updated=4" in second_output.getvalue()


def test_demo_seed_upgrades_existing_customer_profile_business_key():
    call_command("seed_demo_accounts", stdout=StringIO())
    customer = User.objects.get(username="DEMO-CUSTOMER-001")
    profile = CustomerProfile.objects.get(user=customer)
    profile.customer_no = "SYN-CUSTOMER-001"
    profile.save(update_fields=["customer_no", "updated_at"])

    output = StringIO()
    call_command("seed_demo_accounts", stdout=output)

    profile.refresh_from_db()
    assert CustomerProfile.objects.filter(user=customer).count() == 1
    assert profile.customer_no == "DEMO-CUSTOMER-001"
    assert "updated=4" in output.getvalue()
