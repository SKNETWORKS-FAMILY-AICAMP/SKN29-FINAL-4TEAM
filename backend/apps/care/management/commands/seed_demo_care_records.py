"""Wave 2 Demo 케어 이력 3건을 반복 실행 가능하게 적재한다."""

from datetime import date, datetime, timezone

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.care.models import CareRecord
from apps.subscriptions.management.commands.seed_demo_subscriptions import (
    DEMO_SUBSCRIPTION_CONTRACT_NO,
)
from apps.subscriptions.models import CustomerSubscription


DEMO_CARE_CODES = (
    "DEMO-CAR-001",
    "DEMO-CAR-002",
    "DEMO-CAR-003",
)
DEMO_TECHNICIAN_USERNAME = "DEMO-TECHNICIAN-001"


class Command(BaseCommand):
    help = "T-005 Wave 2 Demo CareRecord 3건을 update_or_create합니다."

    @transaction.atomic
    def handle(self, *args, **options):
        del args, options
        try:
            subscription = CustomerSubscription.objects.get(
                contract_no=DEMO_SUBSCRIPTION_CONTRACT_NO
            )
            technician = User.objects.get(
                username=DEMO_TECHNICIAN_USERNAME,
                role_code=User.Role.TECHNICIAN,
            )
        except (
            CustomerSubscription.DoesNotExist,
            User.DoesNotExist,
        ) as exc:
            raise CommandError(
                "seed_demo_accounts, seed_demo_products, "
                "seed_demo_subscriptions를 먼저 실행해야 합니다."
            ) from exc

        records = (
            {
                "care_code": DEMO_CARE_CODES[0],
                "care_type_code": (
                    CareRecord.CareType.FILTER_REPLACEMENT
                ),
                "status_code": CareRecord.Status.SCHEDULED,
                "scheduled_on": date(2026, 8, 4),
                "completed_at": None,
                "cancelled_at": None,
                "cancellation_reason": None,
                "summary": None,
                "performed_by": None,
                "source_code": CareRecord.Source.SYSTEM,
            },
            {
                "care_code": DEMO_CARE_CODES[1],
                "care_type_code": CareRecord.CareType.PERIODIC_CHECK,
                "status_code": CareRecord.Status.COMPLETED,
                "scheduled_on": date(2026, 5, 4),
                "completed_at": datetime(
                    2026,
                    5,
                    4,
                    1,
                    30,
                    tzinfo=timezone.utc,
                ),
                "cancelled_at": None,
                "cancellation_reason": None,
                "summary": "합성 정기 점검 완료",
                "performed_by": technician,
                "source_code": CareRecord.Source.TECHNICIAN,
            },
            {
                "care_code": DEMO_CARE_CODES[2],
                "care_type_code": CareRecord.CareType.CLEANING,
                "status_code": CareRecord.Status.CANCELLED,
                "scheduled_on": date(2026, 7, 4),
                "completed_at": None,
                "cancelled_at": datetime(
                    2026,
                    6,
                    29,
                    3,
                    0,
                    tzinfo=timezone.utc,
                ),
                "cancellation_reason": "합성 고객 일정 변경",
                "summary": None,
                "performed_by": None,
                "source_code": CareRecord.Source.CUSTOMER,
            },
        )

        created_count = 0
        for record in records:
            care_code = record["care_code"]
            defaults = {
                "subscription": subscription,
                "visit_result_public_id": None,
                **{
                    key: value
                    for key, value in record.items()
                    if key != "care_code"
                },
            }
            _, created = CareRecord.objects.update_or_create(
                care_code=care_code,
                defaults=defaults,
            )
            created_count += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                "Demo CareRecord ready "
                f"(created={created_count}, updated={3 - created_count})"
            )
        )
