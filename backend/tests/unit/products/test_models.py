"""ProductModel 필드와 데이터베이스 제약 검증."""

from datetime import date
from uuid import UUID

import pytest
from django.apps import apps
from django.db import IntegrityError, transaction

from apps.products.models import ProductModel


pytestmark = pytest.mark.django_db


def create_product(**overrides) -> ProductModel:
    sequence = ProductModel.objects.count() + 1
    values = {
        "model_code": f"TEST-PMD-{sequence:03d}",
        "model_name": f"테스트 제품 {sequence}",
    }
    values.update(overrides)
    return ProductModel.objects.create(**values)


def test_product_model_is_registered_with_three_layer_identifier():
    product = create_product()

    assert apps.get_model("products", "ProductModel") is ProductModel
    assert ProductModel._meta.db_table == "catalog_product_model"
    assert isinstance(product.pk, int)
    assert isinstance(product.public_id, UUID)
    assert product.model_code == "TEST-PMD-001"
    assert product.manufacturer == "SK매직"
    assert product.features == {}


def test_model_code_and_public_id_are_unique():
    product = create_product()

    with pytest.raises(IntegrityError), transaction.atomic():
        create_product(model_code=product.model_code)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_product(public_id=product.public_id)


def test_discontinued_date_cannot_precede_launch_date():
    with pytest.raises(IntegrityError), transaction.atomic():
        create_product(
            launched_on=date(2026, 2, 1),
            discontinued_on=date(2026, 1, 31),
        )


def test_supported_active_index_is_declared():
    indexes = {
        index.name: tuple(index.fields)
        for index in ProductModel._meta.indexes
    }

    assert indexes["ix_product_supported_active"] == (
        "is_supported_mvp",
        "is_active",
    )
