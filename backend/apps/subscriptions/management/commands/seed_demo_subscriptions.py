"""Wave 2 Demo 고객 구독을 반복 실행 가능하게 적재한다."""

from datetime import date, datetime, timezone

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import CustomerProfile
from apps.products.management.commands.seed_demo_products import (
    DEMO_PRODUCT_MODEL_CODE,
)
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


DEMO_CUSTOMER_NO = "SYN-CUSTOMER-001"
DEMO_SUBSCRIPTION_CONTRACT_NO = "DEMO-SUB-001"


class Command(BaseCommand):
    help = "T-005 Wave 2 Demo CustomerSubscription을 update_or_create합니다."

    @transaction.atomic
    def handle(self, *args, **options):
        del args, options
        try:
            customer = CustomerProfile.objects.get(
                customer_no=DEMO_CUSTOMER_NO
            )
            product_model = ProductModel.objects.get(
                model_code=DEMO_PRODUCT_MODEL_CODE
            )
        except (CustomerProfile.DoesNotExist, ProductModel.DoesNotExist) as exc:
            raise CommandError(
                "seed_demo_accounts와 seed_demo_products를 먼저 "
                "실행해야 합니다."
            ) from exc

        subscription, created = (
            CustomerSubscription.objects.update_or_create(
                contract_no=DEMO_SUBSCRIPTION_CONTRACT_NO,
                defaults={
                    "customer": customer,
                    "product_model": product_model,
                    "serial_no": "SYN-JAC104D-0001",
                    "management_type_code": (
                        CustomerSubscription.ManagementType.VISIT_CARE
                    ),
                    "status_code": CustomerSubscription.Status.ACTIVE,
                    "started_on": date(2026, 1, 15),
                    "ended_on": None,
                    "installed_at": datetime(
                        2026,
                        1,
                        15,
                        0,
                        0,
                        tzinfo=timezone.utc,
                    ),
                    "installation_address": "합성 테스트 설치 주소",
                    "next_care_on": date(2026, 8, 4),
                },
            )
        )
        state = "created" if created else "updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo CustomerSubscription ready ({state}=1, "
                f"contract_no={subscription.contract_no})"
            )
        )
