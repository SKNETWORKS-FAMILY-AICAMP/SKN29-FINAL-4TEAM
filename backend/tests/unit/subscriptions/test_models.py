"""CustomerSubscription 필드·제약·삭제 정책 검증."""

from datetime import date
from uuid import UUID

import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from apps.accounts.models import CustomerProfile, User
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db


def create_customer(sequence: int = 1) -> CustomerProfile:
    user = User.objects.create_user(
        id=f"DEMO-USR-{sequence + 200:03d}",
        username=f"TEST-CUSTOMER-{sequence:03d}",
        password=None,
        full_name=f"테스트 고객 {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    return CustomerProfile.objects.create(
        id=f"DEMO-CUS-{sequence + 200:03d}",
        user=user,
        customer_no=f"TEST-CUSTOMER-NO-{sequence:03d}",
        customer_name=f"테스트 고객 {sequence}",
    )


def create_product(sequence: int = 1) -> ProductModel:
    return ProductModel.objects.create(
        model_code=f"TEST-SUB-PMD-{sequence:03d}",
        model_name=f"구독 테스트 제품 {sequence}",
    )


def create_subscription(sequence: int = 1, **overrides):
    values = {
        "contract_no": f"TEST-SUB-{sequence:03d}",
        "customer": create_customer(sequence),
        "product_model": create_product(sequence),
        "serial_no": f"TEST-SERIAL-{sequence:03d}",
        "started_on": date(2026, 1, sequence),
    }
    values.update(overrides)
    return CustomerSubscription.objects.create(**values)


def test_subscription_uses_three_layer_identifier_and_defaults():
    subscription = create_subscription()

    assert isinstance(subscription.pk, int)
    assert isinstance(subscription.public_id, UUID)
    assert subscription.contract_no == "TEST-SUB-001"
    assert (
        subscription.management_type_code
        == CustomerSubscription.ManagementType.VISIT_CARE
    )
    assert subscription.status_code == CustomerSubscription.Status.ACTIVE


def test_active_and_suspended_subscriptions_cannot_share_serial():
    first = create_subscription()

    with pytest.raises(IntegrityError), transaction.atomic():
        create_subscription(
            sequence=2,
            serial_no=first.serial_no,
            status_code=CustomerSubscription.Status.SUSPENDED,
        )

    cancelled = create_subscription(
        sequence=3,
        serial_no=first.serial_no,
        status_code=CustomerSubscription.Status.CANCELLED,
        ended_on=date(2026, 2, 1),
    )
    assert cancelled.serial_no == first.serial_no


def test_subscription_period_and_terminal_status_are_constrained():
    with pytest.raises(IntegrityError), transaction.atomic():
        create_subscription(
            ended_on=date(2025, 12, 31),
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_subscription(
            sequence=2,
            status_code=CustomerSubscription.Status.EXPIRED,
            ended_on=None,
        )


def test_subscription_code_values_are_database_constrained():
    with pytest.raises(IntegrityError), transaction.atomic():
        create_subscription(management_type_code="UNSUPPORTED")

    with pytest.raises(IntegrityError), transaction.atomic():
        create_subscription(sequence=2, status_code="UNKNOWN")


def test_customer_and_product_deletion_are_protected():
    subscription = create_subscription()

    with pytest.raises(ProtectedError):
        subscription.customer.delete()

    with pytest.raises(ProtectedError):
        subscription.product_model.delete()


def test_subscription_indexes_are_declared():
    indexes = {
        index.name: tuple(index.fields)
        for index in CustomerSubscription._meta.indexes
    }

    assert indexes == {
        "ix_sub_customer_status": ("customer", "status_code"),
        "ix_sub_next_care": ("next_care_on",),
        "ix_sub_product_model": ("product_model",),
    }
