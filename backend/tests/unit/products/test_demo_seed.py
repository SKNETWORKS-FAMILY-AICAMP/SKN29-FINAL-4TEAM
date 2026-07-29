"""ProductModel Demo Seed 멱등성 검증."""

from django.core.management import call_command

import pytest

from apps.products.management.commands.seed_demo_products import (
    DEMO_PRODUCT_MODEL_CODE,
)
from apps.products.models import ProductModel


pytestmark = pytest.mark.django_db


def test_demo_product_seed_preserves_internal_and_public_ids():
    call_command("seed_demo_products")
    first = ProductModel.objects.get(
        model_code=DEMO_PRODUCT_MODEL_CODE
    )
    first_identity = (first.pk, first.public_id)

    call_command("seed_demo_products")
    second = ProductModel.objects.get(
        model_code=DEMO_PRODUCT_MODEL_CODE
    )

    assert ProductModel.objects.count() == 1
    assert (second.pk, second.public_id) == first_identity
    assert second.is_supported_mvp is True
    assert second.is_active is True
