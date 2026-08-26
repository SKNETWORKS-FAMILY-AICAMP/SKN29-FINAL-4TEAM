"""Forward and reverse proof for the Inquiry priority column."""

from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
import pytest

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


OLD_TARGET = [("inquiries", "0012_alter_inquiry_options")]
NEW_TARGET = [("inquiries", "0013_inquiry_priority_code")]
LATEST_TARGET = [
    ("inquiries", "0015_humanreview")
]


@pytest.mark.django_db(transaction=True)
def test_0012_to_0013_backfills_normal_and_enforces_priority_constraint(
    request,
):
    MigrationExecutor(connection).migrate(NEW_TARGET)
    request.addfinalizer(
        lambda: MigrationExecutor(connection).migrate(LATEST_TARGET)
    )
    user = User.objects.create_user(
        username="CONS04-MIGRATION-CUSTOMER",
        password=None,
        full_name="CONS04 migration customer",
        role_code="CUSTOMER",
        is_synthetic=True,
    )
    customer = CustomerProfile.objects.create(
        user=user,
        customer_no="CONS04-MIGRATION-CUS",
        customer_name="합성 Migration 고객",
        is_synthetic=True,
    )
    product = ProductModel.objects.create(
        model_code="CONS04-MIGRATION-MODEL",
        model_name="합성 Migration 제품",
    )
    subscription = CustomerSubscription.objects.create(
        contract_no="CONS04-MIGRATION-CONTRACT",
        customer=customer,
        product_model=product,
        serial_no="CONS04-MIGRATION-SERIAL",
        started_on=date(2026, 8, 1),
    )
    inquiry = Inquiry.objects.create(
        subscription=subscription,
        initiated_by=user,
        channel_code="PHONE",
        raw_text="Migration 우선순위 기본값 검증",
        status_code="CONSULTATION_REQUIRED",
        state_version=1,
    )

    try:
        executor = MigrationExecutor(connection)
        executor.migrate(OLD_TARGET)
        old_apps = executor.loader.project_state(OLD_TARGET).apps
        OldInquiry = old_apps.get_model("inquiries", "Inquiry")
        assert "priority_code" not in {
            field.name for field in OldInquiry._meta.fields
        }
        assert OldInquiry.objects.filter(pk=inquiry.pk).exists()

        executor = MigrationExecutor(connection)
        executor.migrate(NEW_TARGET)
        new_apps = executor.loader.project_state(NEW_TARGET).apps
        NewInquiry = new_apps.get_model("inquiries", "Inquiry")
        migrated = NewInquiry.objects.get(pk=inquiry.pk)
        assert migrated.priority_code == "NORMAL"

        migrated.priority_code = "URGENT"
        migrated.save(update_fields=["priority_code"])
        migrated.refresh_from_db()
        assert migrated.priority_code == "URGENT"

        executor = MigrationExecutor(connection)
        executor.migrate(OLD_TARGET)
        reversed_apps = executor.loader.project_state(OLD_TARGET).apps
        ReversedInquiry = reversed_apps.get_model("inquiries", "Inquiry")
        assert "priority_code" not in {
            field.name for field in ReversedInquiry._meta.fields
        }
        assert ReversedInquiry.objects.filter(pk=inquiry.pk).exists()
    finally:
        MigrationExecutor(connection).migrate(LATEST_TARGET)
