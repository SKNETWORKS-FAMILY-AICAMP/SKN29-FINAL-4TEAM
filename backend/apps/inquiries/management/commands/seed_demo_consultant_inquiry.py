"""Create an idempotent, privacy-safe consultant inquiry read scenario."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import Inquiry, SymptomAssessment
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


DEMO_CONSULTANT_USERNAME = "DEMO-CONSULTANT-001"
DEMO_CUSTOMER_USERNAME = "DEMO-CONSULTANT-READ-CUSTOMER-001"
DEMO_CUSTOMER_NO = "DEMO-CONSULTANT-READ-CUSTOMER-001"
DEMO_PRODUCT_MODEL_CODE = "DEMO-CONSULTANT-READ-PMD-001"
DEMO_SUBSCRIPTION_CONTRACT_NO = "DEMO-CONSULTANT-READ-SUB-001"
DEMO_INQUIRY_SCENARIO_CODE = "DEMO-CONSULTANT-READ-001"
DEMO_INQUIRY_CODE = "DEMO-INQ-CONSULTANT-READ-001"
DEMO_INQUIRY_PUBLIC_ID = UUID("4f829120-ecbb-5b30-9365-bf02f9044c3b")


class Command(BaseCommand):
    help = (
        "상담사 문의 목록·상세 공동 Smoke용 합성 문의를 "
        "반복 실행에 안전하게 준비합니다."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        del args, options
        try:
            consultant = User.objects.get(
                username=DEMO_CONSULTANT_USERNAME,
                role_code=User.Role.CONSULTANT,
                is_active=True,
                is_synthetic=True,
            )
        except User.DoesNotExist as exc:
            raise CommandError(
                "seed_demo_accounts를 먼저 실행해야 합니다."
            ) from exc

        customer_user, _ = User.objects.update_or_create(
            username=DEMO_CUSTOMER_USERNAME,
            defaults={
                "full_name": "합성 상담조회 고객 001",
                "email": "",
                "phone": "010-0000-0000",
                "role_code": User.Role.CUSTOMER,
                "employee_no": None,
                "is_active": True,
                "is_staff": False,
                "is_synthetic": True,
            },
        )
        customer_user.set_unusable_password()
        customer_user.save(update_fields=["password", "updated_at"])

        customer, _ = CustomerProfile.objects.update_or_create(
            user=customer_user,
            defaults={
                "customer_no": DEMO_CUSTOMER_NO,
                "customer_name": "합성 상담조회 고객 001",
                "phone": "010-0000-0000",
                "postal_code": "00000",
                "address_line1": "합성 검증용 주소",
                "address_line2": "",
                "consent_version": "DEMO-CONSULTANT-READ-1",
                "is_synthetic": True,
                "deleted_at": None,
                "deleted_by": None,
            },
        )

        product, _ = ProductModel.objects.update_or_create(
            model_code=DEMO_PRODUCT_MODEL_CODE,
            defaults={
                "model_name": "WaterBridge 상담조회 합성 정수기",
                "generation_code": "DEMO-G1",
                "manufacturer": "SK매직",
                "launched_on": date(2026, 1, 1),
                "discontinued_on": None,
                "features": {"synthetic": True, "read_smoke": True},
                "is_supported_mvp": True,
                "is_active": True,
            },
        )

        subscription, _ = CustomerSubscription.objects.update_or_create(
            contract_no=DEMO_SUBSCRIPTION_CONTRACT_NO,
            defaults={
                "customer": customer,
                "product_model": product,
                "serial_no": "DEMO-CONSULTANT-READ-SERIAL-001",
                "management_type_code": (
                    CustomerSubscription.ManagementType.VISIT_CARE
                ),
                "status_code": CustomerSubscription.Status.ACTIVE,
                "started_on": date(2026, 8, 1),
                "ended_on": None,
                "installed_at": None,
                "installation_address": "합성 검증용 설치 주소",
                "next_care_on": None,
            },
        )

        inquiry_defaults = {
            "public_id": DEMO_INQUIRY_PUBLIC_ID,
            "inquiry_code": DEMO_INQUIRY_CODE,
            "subscription": subscription,
            "initiated_by": customer_user,
            "assigned_user": consultant,
            "assigned_role_code": Inquiry.AssignedRole.CONSULTANT,
            "channel_code": Inquiry.Channel.WEB,
            "raw_text": "합성 문의: 정수기 출수량이 평소보다 감소했습니다.",
            "risk_level_code": Inquiry.RiskLevel.CAUTION,
            "usage_guidance_status": (
                Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION
            ),
            "evidence_ids": [],
            "evidence_mode": Inquiry.EvidenceMode.NO_EVIDENCE,
            "requires_fallback": True,
            "source_idempotency_key": "seed-demo-consultant-read-001",
            "status_code": Inquiry.Status.CONSULTATION_REQUIRED,
            "state_version": 1,
        }
        inquiry, created = Inquiry.objects.get_or_create(
            scenario_code=DEMO_INQUIRY_SCENARIO_CODE,
            defaults=inquiry_defaults,
        )
        if not created:
            stable_fields = {
                "subscription": subscription,
                "initiated_by": customer_user,
                "assigned_user": consultant,
                "assigned_role_code": Inquiry.AssignedRole.CONSULTANT,
                "channel_code": Inquiry.Channel.WEB,
                "raw_text": inquiry_defaults["raw_text"],
                "risk_level_code": Inquiry.RiskLevel.CAUTION,
                "usage_guidance_status": (
                    Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION
                ),
                "evidence_ids": [],
                "evidence_mode": Inquiry.EvidenceMode.NO_EVIDENCE,
                "requires_fallback": True,
            }
            for field_name, value in stable_fields.items():
                setattr(inquiry, field_name, value)
            inquiry.full_clean()
            inquiry.save(update_fields=[*stable_fields, "updated_at"])

        SymptomAssessment.objects.update_or_create(
            inquiry=inquiry,
            assessment_version=1,
            defaults={
                "ruleset_version": "demo-consultant-read-v1",
                "risk_level_code": SymptomAssessment.RiskLevel.CAUTION,
                "priority_code": "consultation_recommended",
                "usage_guidance_status": (
                    SymptomAssessment.UsageGuidanceStatus.PENDING_CONSULTATION
                ),
                "requires_consultation": True,
                "reason": "합성 상담사 조회 Smoke용 보수적 위험도",
                "rule_result": {
                    "synthetic": True,
                    "scenario": DEMO_INQUIRY_SCENARIO_CODE,
                },
                "assessed_by_type_code": "RULE",
                "ai_run": None,
            },
        )

        state = "created" if created else "updated"
        self.stdout.write(
            self.style.SUCCESS(
                "Demo consultant inquiry ready "
                f"({state}=1, consultant_login={DEMO_CONSULTANT_USERNAME}, "
                f"inquiry_id={inquiry.public_id})"
            )
        )
