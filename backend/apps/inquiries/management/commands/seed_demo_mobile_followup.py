"""Create the official synthetic fixture for Mobile follow-up API smoke."""

from __future__ import annotations

from datetime import date
import json
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.management.commands.seed_demo_accounts import (
    DEMO_CUSTOMER_NO,
)
from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import FollowUpAnswer, Inquiry, InquiryQA
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.subscriptions.repositories.subscription_repository import (
    SUPPORTED_PRODUCT_MODEL_CODE,
)


DEMO_CUSTOMER_USERNAME = "DEMO-CUSTOMER-001"
DEMO_SUBSCRIPTION_CONTRACT_NO = "DEMO-MOBILE-FOLLOWUP-SUB-001"
DEMO_SUBSCRIPTION_PUBLIC_ID = UUID(
    "d0a62011-3b89-5d39-8cd4-4c1d8c365101"
)
DEMO_INQUIRY_SCENARIO_CODE = "DEMO-MOBILE-FOLLOWUP-001"
DEMO_INQUIRY_CODE = "DEMO-INQ-MOBILE-FOLLOWUP-001"
DEMO_INQUIRY_PUBLIC_ID = UUID("d0a62011-3b89-5d39-8cd4-4c1d8c365102")
DEMO_INITIAL_STATE_VERSION = 2
DEMO_FREE_TEXT_QUESTION_CODE = "MOBILE-FOLLOWUP-FREE-TEXT-001"
DEMO_FREE_TEXT_QUESTION_PUBLIC_ID = UUID(
    "d0a62011-3b89-5d39-8cd4-4c1d8c365103"
)
DEMO_CHOICE_QUESTION_CODE = "MOBILE-FOLLOWUP-SINGLE-CHOICE-001"
DEMO_CHOICE_QUESTION_PUBLIC_ID = UUID(
    "d0a62011-3b89-5d39-8cd4-4c1d8c365104"
)
DEMO_CHOICE_OPTIONS = ["최근 교체함", "교체하지 않음", "모름"]


class Command(BaseCommand):
    help = (
        "DEMO-CUSTOMER-001용 Mobile 고객문의 3 API Smoke Fixture를 "
        "멱등하게 준비합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
            help="UUID Crosswalk만 JSON으로 출력합니다.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        del args
        customer_user, customer = self._customer()
        product = self._supported_product()
        subscription = self._subscription(
            customer=customer,
            product=product,
        )
        inquiry, created = self._inquiry(
            customer_user=customer_user,
            subscription=subscription,
        )
        questions = self._questions(inquiry)
        crosswalk = self._crosswalk(
            customer=customer,
            subscription=subscription,
            inquiry=inquiry,
            questions=questions,
        )

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
                "Demo Mobile follow-up fixture ready "
                f"({state}=1, inquiry_id={inquiry.public_id})"
            )
        )
        self.stdout.write(f"MOBILE_FOLLOWUP_CROSSWALK={rendered}")

    @staticmethod
    def _customer() -> tuple[User, CustomerProfile]:
        try:
            user = User.objects.get(
                username=DEMO_CUSTOMER_USERNAME,
                role_code=User.Role.CUSTOMER,
                is_active=True,
                is_synthetic=True,
            )
            customer = CustomerProfile.objects.get(
                user=user,
                customer_no=DEMO_CUSTOMER_NO,
                is_synthetic=True,
                deleted_at__isnull=True,
            )
        except (User.DoesNotExist, CustomerProfile.DoesNotExist) as exc:
            raise CommandError(
                "seed_demo_accounts를 먼저 실행해야 합니다."
            ) from exc
        return user, customer

    @staticmethod
    def _supported_product() -> ProductModel:
        product, created = ProductModel.objects.get_or_create(
            model_code=SUPPORTED_PRODUCT_MODEL_CODE,
            defaults={
                "model_name": "WaterBridge Mobile Smoke 정수기",
                "generation_code": "DEMO-G1",
                "manufacturer": "SK매직",
                "launched_on": date(2026, 1, 1),
                "discontinued_on": None,
                "features": {
                    "fixture": DEMO_INQUIRY_SCENARIO_CODE,
                    "synthetic": True,
                },
                "is_supported_mvp": True,
                "is_active": True,
            },
        )
        if not created and (
            not product.is_active or not product.is_supported_mvp
        ):
            raise CommandError(
                f"{SUPPORTED_PRODUCT_MODEL_CODE} 제품이 활성 지원 상태가 아닙니다."
            )
        return product

    @staticmethod
    def _subscription(
        *,
        customer: CustomerProfile,
        product: ProductModel,
    ) -> CustomerSubscription:
        defaults = {
            "public_id": DEMO_SUBSCRIPTION_PUBLIC_ID,
            "customer": customer,
            "product_model": product,
            "serial_no": "DEMO-MOBILE-FOLLOWUP-SERIAL-001",
            "management_type_code": (
                CustomerSubscription.ManagementType.VISIT_CARE
            ),
            "status_code": CustomerSubscription.Status.ACTIVE,
            "started_on": date(2026, 8, 1),
            "ended_on": None,
            "installed_at": None,
            "installed_on": date(2026, 8, 1),
            "installation_address": "합성 Mobile Smoke 설치 주소",
            "next_care_on": date(2026, 8, 20),
        }
        subscription, created = CustomerSubscription.objects.get_or_create(
            contract_no=DEMO_SUBSCRIPTION_CONTRACT_NO,
            defaults=defaults,
        )
        if not created:
            Command._assert_identity(
                "subscription public_id",
                subscription.public_id,
                DEMO_SUBSCRIPTION_PUBLIC_ID,
            )
            Command._assert_identity(
                "subscription customer",
                subscription.customer_id,
                customer.pk,
            )
            Command._assert_identity(
                "subscription product",
                subscription.product_model_id,
                product.pk,
            )
            for field_name, value in defaults.items():
                if field_name == "public_id":
                    continue
                setattr(subscription, field_name, value)
            subscription.full_clean()
            subscription.save(
                update_fields=[
                    *(key for key in defaults if key != "public_id"),
                    "updated_at",
                ]
            )
        return subscription

    @staticmethod
    def _inquiry(
        *,
        customer_user: User,
        subscription: CustomerSubscription,
    ) -> tuple[Inquiry, bool]:
        defaults = {
            "public_id": DEMO_INQUIRY_PUBLIC_ID,
            "inquiry_code": DEMO_INQUIRY_CODE,
            "subscription": subscription,
            "initiated_by": customer_user,
            "assigned_user": None,
            "assigned_role_code": Inquiry.AssignedRole.NONE,
            "channel_code": Inquiry.Channel.MOBILE,
            "raw_text": "합성 문의: 출수량이 줄고 필터 상태를 확인하고 싶습니다.",
            "risk_level_code": None,
            "usage_guidance_status": None,
            "evidence_ids": [],
            "evidence_mode": None,
            "requires_fallback": False,
            "source_idempotency_key": "seed-demo-mobile-followup-001",
            "status_code": Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS,
            "state_version": DEMO_INITIAL_STATE_VERSION,
        }
        inquiry, created = Inquiry.objects.get_or_create(
            scenario_code=DEMO_INQUIRY_SCENARIO_CODE,
            defaults=defaults,
        )
        if created:
            return inquiry, True

        Command._assert_identity(
            "inquiry public_id",
            inquiry.public_id,
            DEMO_INQUIRY_PUBLIC_ID,
        )
        Command._assert_identity(
            "inquiry code",
            inquiry.inquiry_code,
            DEMO_INQUIRY_CODE,
        )
        Command._assert_identity(
            "inquiry subscription",
            inquiry.subscription_id,
            subscription.pk,
        )
        Command._assert_identity(
            "inquiry owner",
            inquiry.initiated_by_id,
            customer_user.pk,
        )
        if (
            inquiry.status_code
            != Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
            or inquiry.state_version != DEMO_INITIAL_STATE_VERSION
            or FollowUpAnswer.objects.filter(
                question__inquiry=inquiry
            ).exists()
        ):
            raise CommandError(
                "Mobile follow-up Fixture가 이미 소비되었습니다. "
                "답변 원장을 삭제하지 말고 새 격리 DB에서 다시 생성하세요."
            )

        stable_fields = {
            key: value
            for key, value in defaults.items()
            if key not in {"public_id", "inquiry_code"}
        }
        for field_name, value in stable_fields.items():
            setattr(inquiry, field_name, value)
        inquiry.full_clean()
        inquiry.save(update_fields=[*stable_fields, "updated_at"])
        return inquiry, False

    @staticmethod
    def _questions(inquiry: Inquiry) -> list[InquiryQA]:
        specs = (
            {
                "public_id": DEMO_FREE_TEXT_QUESTION_PUBLIC_ID,
                "sequence_no": 1,
                "question_code": DEMO_FREE_TEXT_QUESTION_CODE,
                "question_text": (
                    "증상이 언제 시작되었고 지금도 지속되는지 알려주세요."
                ),
                "answer_type_code": "FREE_TEXT",
                "answer_payload": None,
            },
            {
                "public_id": DEMO_CHOICE_QUESTION_PUBLIC_ID,
                "sequence_no": 2,
                "question_code": DEMO_CHOICE_QUESTION_CODE,
                "question_text": "필터를 최근에 교체하셨나요?",
                "answer_type_code": "SINGLE_CHOICE",
                "answer_payload": {
                    "question_options": DEMO_CHOICE_OPTIONS,
                    "target_field": "filter_replacement",
                },
            },
        )
        expected_codes = {spec["question_code"] for spec in specs}
        unexpected = inquiry.qa_entries.exclude(
            question_code__in=expected_codes
        ).exists()
        if unexpected:
            raise CommandError(
                "Fixture 문의에 예상하지 않은 질문이 있습니다. "
                "새 격리 DB를 사용하세요."
            )

        questions = []
        for spec in specs:
            question, created = InquiryQA.objects.get_or_create(
                inquiry=inquiry,
                question_code=spec["question_code"],
                defaults={
                    **spec,
                    "asked_by_type_code": "RULE",
                },
            )
            if not created:
                Command._assert_identity(
                    f"question {spec['question_code']} public_id",
                    question.public_id,
                    spec["public_id"],
                )
                if hasattr(question, "customer_answer"):
                    raise CommandError(
                        "Mobile follow-up Fixture가 이미 소비되었습니다. "
                        "새 격리 DB를 사용하세요."
                    )
                for field_name in (
                    "sequence_no",
                    "question_text",
                    "answer_type_code",
                    "answer_payload",
                ):
                    setattr(question, field_name, spec[field_name])
                question.asked_by_type_code = "RULE"
                question.source_ai_run = None
                question.full_clean()
                question.save(
                    update_fields=[
                        "sequence_no",
                        "question_text",
                        "answer_type_code",
                        "answer_payload",
                        "asked_by_type_code",
                        "source_ai_run",
                        "updated_at",
                    ]
                )
            questions.append(question)
        return questions

    @staticmethod
    def _crosswalk(
        *,
        customer: CustomerProfile,
        subscription: CustomerSubscription,
        inquiry: Inquiry,
        questions: list[InquiryQA],
    ) -> dict:
        return {
            "fixture": "mobile-followup-v1",
            "demo_user_code": DEMO_CUSTOMER_USERNAME,
            "customer_id": str(customer.public_id),
            "product_model_code": SUPPORTED_PRODUCT_MODEL_CODE,
            "subscription_id": str(subscription.public_id),
            "inquiry_id": str(inquiry.public_id),
            "state_version": inquiry.state_version,
            "questions": [
                {
                    "question_code": question.question_code,
                    "question_id": str(question.public_id),
                    "question_type": question.answer_type_code,
                }
                for question in questions
            ],
        }

    @staticmethod
    def _assert_identity(label: str, actual, expected) -> None:
        if actual != expected:
            raise CommandError(
                f"Existing {label} conflicts with the official Fixture."
            )
