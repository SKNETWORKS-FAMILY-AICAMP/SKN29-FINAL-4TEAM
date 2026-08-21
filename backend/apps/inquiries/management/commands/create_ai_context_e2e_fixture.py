"""Create one run-scoped JAC104 Inquiry Context E2E fixture."""

from __future__ import annotations

import hashlib
import json
import re
from uuid import UUID, uuid5

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.accounts.models import User
from apps.audit.models import AIRun
from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry, SymptomEntry
from apps.inquiries.services.inquiry_service import InquiryService
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


CANONICAL_CONTRACT_NO = "SUB-SYN-0001"
CANONICAL_MODEL_CODE = "WPUJAC104DWH"
FIXTURE_SCOPE = "BACKEND_AI_CONTEXT_G1_ISOLATED_E2E"
FIXTURE_NAMESPACE = UUID("f4c180e6-245e-4dbd-a34c-29f21f2bb9c6")
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class Command(BaseCommand):
    help = (
        "공식 db-smoke JAC104 구독을 사용해 고유 run_id마다 "
        "Backend AI Context 검증용 새 합성 문의를 준비합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument("--run-id", required=True)
        parser.add_argument(
            "--apply",
            action="store_true",
            help="확인된 격리 DB에 신규 문의를 생성합니다.",
        )
        parser.add_argument("--confirm-database")
        parser.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        del args
        run_id = self._validate_run_id(options["run_id"])
        owner, subscription, product = self._dependencies()

        if not options["apply"]:
            self._render(
                {
                    "fixture_readiness": "READY_FOR_APPLY",
                    "fixture_scope": FIXTURE_SCOPE,
                    "known_blocker": "NONE",
                    "model_code": product.model_code,
                    "run_id": run_id,
                    "source_contract_no": CANONICAL_CONTRACT_NO,
                },
                json_output=options["json_output"],
            )
            return

        self._confirm_postgresql_database(options.get("confirm_database"))
        identity = self._identity(run_id)
        outcome = InquiryService.create(
            actor=owner,
            validated_data={
                "subscription_id": subscription.public_id,
                "channel_code": Inquiry.Channel.MOBILE,
                "raw_text": "정수기 출수량이 평소보다 줄었습니다.",
                "representative_symptom_code": "LOW_FLOW",
                "questionnaire_session_id": None,
            },
            idempotency_key=identity["idempotency_key"],
            correlation_id=identity["correlation_id"],
        )
        inquiry = Inquiry.objects.select_for_update().get(
            public_id=outcome.data["inquiry_id"]
        )
        tracking_updates: list[str] = []
        if inquiry.scenario_code is None:
            inquiry.scenario_code = identity["scenario_code"]
            tracking_updates.append("scenario_code")
        if inquiry.source_idempotency_key is None:
            inquiry.source_idempotency_key = identity["idempotency_key"]
            tracking_updates.append("source_idempotency_key")
        if inquiry.source_correlation_id is None:
            inquiry.source_correlation_id = identity["correlation_id"]
            tracking_updates.append("source_correlation_id")
        if tracking_updates:
            inquiry.save(update_fields=[*tracking_updates, "updated_at"])
        self._assert_unconsumed(
            inquiry=inquiry,
            owner=owner,
            subscription=subscription,
            identity=identity,
        )

        result = {
            "allowed_actions": [
                item["code"] for item in outcome.data["allowed_actions"]
            ],
            "created": not outcome.data["idempotent_replay"],
            "fixture_readiness": "READY_FOR_CONTEXT_E2E",
            "fixture_scope": FIXTURE_SCOPE,
            "inquiry_code": inquiry.inquiry_code,
            "inquiry_id": str(inquiry.public_id),
            "known_blocker": "NONE",
            "model_code": product.model_code,
            "request_correlation_id": str(identity["correlation_id"]),
            "run_id": run_id,
            "state_version": inquiry.state_version,
            "status": inquiry.status_code,
        }
        self._render(result, json_output=options["json_output"])

    @staticmethod
    def _validate_run_id(raw_value: str) -> str:
        value = raw_value.strip()
        if not RUN_ID_PATTERN.fullmatch(value):
            raise CommandError(
                "run_id는 1~64자의 영문자·숫자·점·밑줄·하이픈만 "
                "사용해야 합니다."
            )
        return value

    @staticmethod
    def _dependencies() -> tuple[User, CustomerSubscription, ProductModel]:
        try:
            subscription = CustomerSubscription.objects.select_related(
                "customer__user",
                "product_model",
            ).get(contract_no=CANONICAL_CONTRACT_NO)
        except CustomerSubscription.DoesNotExist as exc:
            raise CommandError(
                "import_synthetic_handoff --profile db-smoke를 먼저 "
                "실행해야 합니다."
            ) from exc

        owner = subscription.customer.user
        product = subscription.product_model
        valid = (
            owner.role_code == User.Role.CUSTOMER
            and owner.is_active
            and owner.is_synthetic
            and subscription.customer.is_synthetic
            and subscription.customer.deleted_at is None
            and subscription.status_code == CustomerSubscription.Status.ACTIVE
            and product.model_code == CANONICAL_MODEL_CODE
            and product.is_active
            and product.is_supported_mvp
        )
        if not valid:
            raise CommandError(
                "공식 db-smoke JAC104 고객·구독·제품 경계가 일치하지 않습니다."
            )
        return owner, subscription, product

    @staticmethod
    def _confirm_postgresql_database(expected_name: str | None) -> None:
        if connection.vendor != "postgresql":
            return
        actual = str(connection.settings_dict.get("NAME") or "")
        if not expected_name:
            raise CommandError(
                "PostgreSQL apply에는 --confirm-database가 필요합니다."
            )
        if actual != expected_name:
            raise CommandError(
                "연결된 PostgreSQL DB가 --confirm-database와 다릅니다."
            )

    @staticmethod
    def _identity(run_id: str) -> dict[str, object]:
        digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
        return {
            "scenario_code": f"SYN-AI-CONTEXT-{digest[:24]}",
            "idempotency_key": f"ai-context-e2e-{digest}",
            "correlation_id": uuid5(
                FIXTURE_NAMESPACE,
                f"correlation/{run_id}",
            ),
        }

    @staticmethod
    def _assert_unconsumed(
        *,
        inquiry: Inquiry,
        owner: User,
        subscription: CustomerSubscription,
        identity: dict[str, object],
    ) -> None:
        identity_matches = (
            inquiry.scenario_code == identity["scenario_code"]
            and inquiry.initiated_by_id == owner.pk
            and inquiry.subscription_id == subscription.pk
            and inquiry.source_idempotency_key == identity["idempotency_key"]
            and inquiry.source_correlation_id == identity["correlation_id"]
        )
        unconsumed = (
            inquiry.status_code == Inquiry.Status.DRAFT
            and inquiry.state_version == 1
            and SymptomEntry.objects.filter(
                inquiry=inquiry,
                symptom_type_code="LOW_FLOW",
                is_customer_confirmed=True,
            ).count()
            == 1
            and not AIRun.objects.filter(inquiry=inquiry).exists()
            and not Consultation.objects.filter(inquiry=inquiry).exists()
        )
        if not identity_matches:
            raise CommandError("Existing AI Context Fixture identity conflicts.")
        if not unconsumed:
            raise CommandError(
                "AI Context Fixture가 이미 소비되었습니다. 이력을 되돌리지 "
                "말고 새 run_id를 사용하세요."
            )

    def _render(self, payload: dict, *, json_output: bool) -> None:
        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if json_output:
            self.stdout.write(rendered)
            return
        self.stdout.write(
            self.style.SUCCESS(
                "AI Context E2E fixture result: "
                f"{payload['fixture_readiness']}"
            )
        )
        self.stdout.write(f"AI_CONTEXT_E2E_CROSSWALK={rendered}")
