"""CustomerSubscription Demo Seed 멱등성 검증."""

from django.core.management import call_command

import pytest

from apps.subscriptions.management.commands.seed_demo_subscriptions import (
    DEMO_SUBSCRIPTION_CONTRACT_NO,
)
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db


def test_demo_subscription_seed_preserves_internal_and_public_ids():
    call_command("seed_demo_accounts")
    call_command("seed_demo_products")
    call_command("seed_demo_subscriptions")
    first = CustomerSubscription.objects.get(
        contract_no=DEMO_SUBSCRIPTION_CONTRACT_NO
    )
    first_identity = (first.pk, first.public_id)

    call_command("seed_demo_accounts")
    call_command("seed_demo_products")
    call_command("seed_demo_subscriptions")
    second = CustomerSubscription.objects.get(
        contract_no=DEMO_SUBSCRIPTION_CONTRACT_NO
    )

    assert CustomerSubscription.objects.count() == 1
    assert (second.pk, second.public_id) == first_identity
    assert second.customer.customer_no == "DEMO-CUSTOMER-001"
    assert second.product_model.model_code == "DEMO-PMD-001"
