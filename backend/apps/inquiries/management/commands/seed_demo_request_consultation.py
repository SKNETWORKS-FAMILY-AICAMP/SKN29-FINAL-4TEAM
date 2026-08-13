"""Create the official synthetic Mobile REQUEST_CONSULTATION fixture."""

from __future__ import annotations

import json
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.management.commands.seed_demo_accounts import (
    DEMO_CUSTOMER_NO,
)
from apps.accounts.models import CustomerProfile, User
from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry
from apps.subscriptions.management.commands.seed_demo_subscriptions import (
    DEMO_SUBSCRIPTION_CONTRACT_NO,
)
from apps.subscriptions.models import CustomerSubscription


DEMO_CUSTOMER_USERNAME = "DEMO-CUSTOMER-001"
DEMO_INQUIRY_SCENARIO_CODE = "DEMO-MOBILE-REQUEST-CONSULTATION-001"
DEMO_INQUIRY_CODE = "DEMO-INQ-MOBILE-REQUEST-CONSULTATION-001"
DEMO_INQUIRY_PUBLIC_ID = UUID("d0a62012-3b89-5d39-8cd4-4c1d8c366201")
DEMO_INITIAL_STATE_VERSION = 3


class Command(BaseCommand):
    help = (
        "DEMO-CUSTOMER-001용 Mobile REQUEST_CONSULTATION Fixture를 "
        "소비 전까지 멱등하게 준비합니다."
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
        owner, subscription = self._dependencies()
        inquiry, created = Inquiry.objects.get_or_create(
            scenario_code=DEMO_INQUIRY_SCENARIO_CODE,
            defaults={
                "public_id": DEMO_INQUIRY_PUBLIC_ID,
                "inquiry_code": DEMO_INQUIRY_CODE,
                "subscription": subscription,
                "initiated_by": owner,
                "assigned_user": None,
                "assigned_role_code": Inquiry.AssignedRole.NONE,
                "channel_code": Inquiry.Channel.MOBILE,
                "raw_text": (
                    "합성 Mobile 상담 요청 Fixture: 안전 안내 후 상담을 요청합니다."
                ),
                "risk_level_code": Inquiry.RiskLevel.CAUTION,
                "priority_code": Inquiry.Priority.NORMAL,
                "usage_guidance_status": Inquiry.UsageGuidanceStatus.NORMAL,
                "evidence_ids": [],
                "evidence_mode": Inquiry.EvidenceMode.EXACT_MODEL,
                "requires_fallback": False,
                "source_idempotency_key": (
                    "seed-demo-mobile-request-consultation-001"
                ),
                "status_code": Inquiry.Status.AI_GUIDANCE,
                "state_version": DEMO_INITIAL_STATE_VERSION,
            },
        )
        if not created:
            self._assert_unconsumed(
                inquiry=inquiry,
                owner=owner,
                subscription=subscription,
            )

        crosswalk = {
            "fixture": "mobile-request-consultation-v1",
            "demo_user_code": DEMO_CUSTOMER_USERNAME,
            "subscription_id": str(subscription.public_id),
            "inquiry_id": str(inquiry.public_id),
            "status_code": inquiry.status_code,
            "state_version": inquiry.state_version,
            "operation_id": "requestConsultation",
            "method": "POST",
            "path": (
                f"/api/v1/inquiries/{inquiry.public_id}/request-consultation"
            ),
        }
        rendered = json.dumps(
            crosswalk,
            ensure_ascii=False,
            sort_keys=True,
        )
        if options["json_output"]:
            self.stdout.write(rendered)
            return

        state = "created" if created else "verified"
        self.stdout.write(
            self.style.SUCCESS(
                "Demo Mobile consultation request fixture ready "
                f"({state}=1, inquiry_id={inquiry.public_id})"
            )
        )
        self.stdout.write(f"MOBILE_REQUEST_CONSULTATION_CROSSWALK={rendered}")

    @staticmethod
    def _dependencies() -> tuple[User, CustomerSubscription]:
        try:
            owner = User.objects.get(
                username=DEMO_CUSTOMER_USERNAME,
                role_code=User.Role.CUSTOMER,
                is_active=True,
                is_synthetic=True,
            )
            customer = CustomerProfile.objects.get(
                user=owner,
                customer_no=DEMO_CUSTOMER_NO,
                is_synthetic=True,
                deleted_at__isnull=True,
            )
            subscription = CustomerSubscription.objects.get(
                contract_no=DEMO_SUBSCRIPTION_CONTRACT_NO,
                customer=customer,
                status_code=CustomerSubscription.Status.ACTIVE,
            )
        except (
            User.DoesNotExist,
            CustomerProfile.DoesNotExist,
            CustomerSubscription.DoesNotExist,
        ) as exc:
            raise CommandError(
                "seed_demo_accounts, seed_demo_products, "
                "seed_demo_subscriptions를 먼저 실행해야 합니다."
            ) from exc
        return owner, subscription

    @staticmethod
    def _assert_unconsumed(
        *,
        inquiry: Inquiry,
        owner: User,
        subscription: CustomerSubscription,
    ) -> None:
        identity_matches = (
            inquiry.public_id == DEMO_INQUIRY_PUBLIC_ID
            and inquiry.inquiry_code == DEMO_INQUIRY_CODE
            and inquiry.initiated_by_id == owner.pk
            and inquiry.subscription_id == subscription.pk
        )
        unconsumed = (
            inquiry.status_code == Inquiry.Status.AI_GUIDANCE
            and inquiry.state_version == DEMO_INITIAL_STATE_VERSION
            and not Consultation.objects.filter(inquiry=inquiry).exists()
        )
        if not identity_matches:
            raise CommandError(
                "Existing Mobile consultation Fixture identity conflicts."
            )
        if not unconsumed:
            raise CommandError(
                "Mobile consultation Fixture가 이미 소비되었습니다. "
                "이력을 되돌리지 말고 새 격리 DB에서 다시 생성하세요."
            )
