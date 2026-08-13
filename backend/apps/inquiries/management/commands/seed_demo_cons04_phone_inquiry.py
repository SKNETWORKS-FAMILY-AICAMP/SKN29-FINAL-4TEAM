"""Create the privacy-safe CONS-04 customer search fixture."""

from __future__ import annotations

from datetime import date
import json
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import CustomerProfile, User
from apps.products.management.commands.seed_demo_products import (
    DEMO_PRODUCT_MODEL_CODE,
)
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


DEMO_CUSTOMER_USERNAME = "DEMO-CONS04-CUSTOMER-001"
DEMO_CUSTOMER_NO = "DEMO-CONS04-CUSTOMER-001"
DEMO_CUSTOMER_NAME = "합성 전화문의 고객 001"
DEMO_CUSTOMER_PHONE = "010-0000-1204"
DEMO_SUBSCRIPTION_CONTRACT_NO = "DEMO-CONS04-PHONE-SUB-001"
DEMO_SUBSCRIPTION_PUBLIC_ID = UUID("c0a50412-3b89-5d39-8cd4-4c1d8c360401")


class Command(BaseCommand):
    help = (
        "CONS-04 이름·전화번호 일부 검색과 등록 공동 Smoke용 "
        "합성 ACTIVE 구독을 멱등하게 준비합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
            help="공개 Fixture Crosswalk만 JSON으로 출력합니다.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        del args
        product = self._product()
        user, _ = User.objects.update_or_create(
            username=DEMO_CUSTOMER_USERNAME,
            defaults={
                "full_name": DEMO_CUSTOMER_NAME,
                "email": "",
                "phone": DEMO_CUSTOMER_PHONE,
                "role_code": User.Role.CUSTOMER,
                "employee_no": None,
                "is_active": True,
                "is_staff": False,
                "is_synthetic": True,
            },
        )
        user.set_unusable_password()
        user.save(update_fields=["password", "updated_at"])
        customer, _ = CustomerProfile.objects.update_or_create(
            user=user,
            defaults={
                "customer_no": DEMO_CUSTOMER_NO,
                "customer_name": DEMO_CUSTOMER_NAME,
                "phone": DEMO_CUSTOMER_PHONE,
                "postal_code": "00000",
                "address_line1": "합성 CONS-04 검증 주소",
                "address_line2": "",
                "consent_version": "DEMO-CONS04-1",
                "is_synthetic": True,
                "deleted_at": None,
                "deleted_by": None,
            },
        )
        subscription_defaults = {
            "public_id": DEMO_SUBSCRIPTION_PUBLIC_ID,
            "customer": customer,
            "product_model": product,
            "serial_no": "DEMO-CONS04-PHONE-SERIAL-001",
            "management_type_code": (
                CustomerSubscription.ManagementType.VISIT_CARE
            ),
            "status_code": CustomerSubscription.Status.ACTIVE,
            "started_on": date(2026, 8, 1),
            "ended_on": None,
            "installed_at": None,
            "installed_on": date(2026, 8, 1),
            "installation_address": "합성 CONS-04 검증 주소",
            "next_care_on": None,
        }
        subscription, created = CustomerSubscription.objects.get_or_create(
            contract_no=DEMO_SUBSCRIPTION_CONTRACT_NO,
            defaults=subscription_defaults,
        )
        if subscription.public_id != DEMO_SUBSCRIPTION_PUBLIC_ID:
            raise CommandError(
                "Existing CONS-04 Fixture public_id conflicts."
            )
        if not created:
            for field_name, value in subscription_defaults.items():
                if field_name != "public_id":
                    setattr(subscription, field_name, value)
            subscription.full_clean()
            subscription.save(
                update_fields=[
                    *(
                        field_name
                        for field_name in subscription_defaults
                        if field_name != "public_id"
                    ),
                    "updated_at",
                ]
            )

        crosswalk = {
            "fixture": "cons04-phone-inquiry-v1",
            "consultant_demo_user_code": "DEMO-CONSULTANT-001",
            "customer_display_name": DEMO_CUSTOMER_NAME,
            "search_query_name": "전화문의 고객 001",
            "search_query_phone": "1204",
            "subscription_id": str(subscription.public_id),
            "subscription_status": subscription.status_code,
            "product_model_code": product.model_code,
            "phone_expected_masked": "010-****-1204",
        }
        rendered = json.dumps(
            crosswalk,
            ensure_ascii=False,
            sort_keys=True,
        )
        if options["json_output"]:
            self.stdout.write(rendered)
            return

        state = "created" if created else "updated"
        self.stdout.write(
            self.style.SUCCESS(
                "Demo CONS-04 phone inquiry fixture ready "
                f"({state}=1, subscription_id={subscription.public_id})"
            )
        )
        self.stdout.write(f"CONS04_PHONE_INQUIRY_CROSSWALK={rendered}")

    @staticmethod
    def _product() -> ProductModel:
        try:
            return ProductModel.objects.get(
                model_code=DEMO_PRODUCT_MODEL_CODE,
                is_active=True,
                is_supported_mvp=True,
            )
        except ProductModel.DoesNotExist as exc:
            raise CommandError(
                "seed_demo_products를 먼저 실행해야 합니다."
            ) from exc
