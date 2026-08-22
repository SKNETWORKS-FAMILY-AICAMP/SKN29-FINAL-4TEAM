"""Prepare one run-scoped product-expansion inquiry for isolated E2E."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from uuid import UUID, uuid5

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.accounts.management.commands.seed_demo_accounts import (
    DEMO_CUSTOMER_NO,
)
from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AIRun
from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry, SymptomEntry
from apps.inquiries.services.inquiry_service import InquiryService
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


DEMO_CUSTOMER_USERNAME = "DEMO-CUSTOMER-001"
FIXTURE_SCOPE = "PRODUCT_EXPANSION_G1_G5_ISOLATED_E2E"
FIXTURE_NAMESPACE = UUID("e1e777e0-9c04-4e93-978a-6503bd4f08b9")
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SUPPORTED_CANDIDATE_MODEL_CODES = {
    "WPUIAC425SNW",
    "WPUIAC606SNW",
}
REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
CANDIDATE_FILE = (
    REPOSITORY_ROOT
    / "data"
    / "synthetic"
    / "candidates"
    / "product_expansion_e2e_cases.json"
)
MANUAL_SCENARIO_FILE = (
    REPOSITORY_ROOT
    / "data"
    / "config"
    / "synthetic"
    / "manual_3model_candidate_scenarios.json"
)
APPROVED_PRODUCT_VALIDATION_SCENARIOS = {
    "SYN-IAC425-101": {
        "case_name": "IAC425_GENERAL",
        "model_code": "WPUIAC425SNW",
        "topic_code": "symptom_cold_lock",
        "risk_level": "caution",
        "usage_guidance_status": "PENDING_CONSULTATION",
    },
    "SYN-IAC425-108": {
        "case_name": "IAC425_LEAK",
        "model_code": "WPUIAC425SNW",
        "topic_code": "symptom_leak",
        "risk_level": "danger",
        "usage_guidance_status": "TOTAL_STOP",
    },
    "SYN-IAC606-101": {
        "case_name": "IAC606_GENERAL",
        "model_code": "WPUIAC606SNW",
        "topic_code": "symptom_cold_lock",
        "risk_level": "caution",
        "usage_guidance_status": "PENDING_CONSULTATION",
    },
    "SYN-IAC606-107": {
        "case_name": "IAC606_LEAK",
        "model_code": "WPUIAC606SNW",
        "topic_code": "symptom_leak",
        "risk_level": "danger",
        "usage_guidance_status": "TOTAL_STOP",
    },
}
ISOLATED_DATABASE_NAMES = {"waterbridge_team_integration"}


class Command(BaseCommand):
    help = (
        "신규 정수기 모델 후보 Case를 검증하고, 고유 run_id마다 "
        "격리 E2E용 구독·문의 Crosswalk를 준비합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument("--model-code", required=True)
        parser.add_argument("--run-id", required=True)
        parser.add_argument(
            "--scenario-id",
            choices=tuple(sorted(APPROVED_PRODUCT_VALIDATION_SCENARIOS)),
            help=(
                "승인된 MVP 제품 미승인 일반·누수 Case를 선택합니다. "
                "생략하면 기존 모델별 단일 후보를 사용합니다."
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="검증을 통과한 격리 DB에 구독·문의를 생성합니다.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 생성 경로를 실행한 뒤 Transaction을 Rollback합니다.",
        )
        parser.add_argument(
            "--enable-candidate-product",
            action="store_true",
            help=(
                "격리 통합 DB에서만 후보 ProductModel의 공개 API 지원 Flag를 "
                "활성화합니다."
            ),
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
        model_code = self._validate_model_code(options["model_code"])
        run_id = self._validate_run_id(options["run_id"])
        scenario_id = options.get("scenario_id")
        apply = bool(options["apply"])
        dry_run = bool(options["dry_run"])
        enable_candidate = bool(options["enable_candidate_product"])
        if apply and dry_run:
            raise CommandError("--apply와 --dry-run은 동시에 사용할 수 없습니다.")
        if enable_candidate and not apply:
            raise CommandError(
                "--enable-candidate-product는 --apply와 함께 사용해야 합니다."
            )

        candidate = self._load_candidate(
            model_code,
            scenario_id=scenario_id,
        )
        owner, customer = self._customer()
        product = self._product(candidate)
        blockers = self._readiness_blockers(product=product)

        if not apply and not dry_run:
            result = self._readiness_result(
                candidate=candidate,
                product=product,
                run_id=run_id,
                blockers=blockers,
            )
            self._render(result, json_output=options["json_output"])
            return

        if enable_candidate:
            self._confirm_isolated_database(options.get("confirm_database"))
            product.is_supported_mvp = True
            product.full_clean()
            product.save(update_fields=["is_supported_mvp", "updated_at"])
            blockers = self._readiness_blockers(product=product)
        elif apply:
            self._confirm_postgresql_database(
                options.get("confirm_database")
            )

        if blockers:
            raise CommandError(
                "Product expansion E2E Fixture is not ready: "
                + ",".join(blockers)
            )

        result = self._create_fixture(
            candidate=candidate,
            owner=owner,
            customer=customer,
            product=product,
            run_id=run_id,
            dry_run=dry_run,
            identity_scenario_id=scenario_id,
        )
        if dry_run:
            transaction.set_rollback(True)
        self._render(result, json_output=options["json_output"])

    @staticmethod
    def _validate_model_code(raw_value: str) -> str:
        value = raw_value.strip().upper()
        if value not in SUPPORTED_CANDIDATE_MODEL_CODES:
            raise CommandError(
                "model_code는 WPUIAC425SNW 또는 WPUIAC606SNW여야 합니다."
            )
        return value

    @staticmethod
    def _validate_run_id(raw_value: str) -> str:
        value = raw_value.strip()
        if not RUN_ID_PATTERN.fullmatch(value):
            raise CommandError(
                "run_id는 1~64자의 영문자·숫자·점·밑줄·하이픈만 "
                "사용해야 합니다."
            )
        return value

    @classmethod
    def _load_candidate(
        cls,
        model_code: str,
        *,
        scenario_id: str | None = None,
    ) -> dict:
        candidate = cls._load_base_candidate(model_code)
        if scenario_id is None:
            return candidate
        return cls._load_product_validation_scenario(
            base_candidate=candidate,
            model_code=model_code,
            scenario_id=scenario_id,
        )

    @staticmethod
    def _load_base_candidate(model_code: str) -> dict:
        try:
            payload = json.loads(CANDIDATE_FILE.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CommandError(
                "Product expansion E2E candidate file을 읽을 수 없습니다."
            ) from exc
        if not isinstance(payload, list):
            raise CommandError("Product expansion E2E candidate root는 배열이어야 합니다.")

        matches = [
            item
            for item in payload
            if isinstance(item, dict)
            and item.get("product", {}).get("exact_sales_code") == model_code
        ]
        if len(matches) != 1:
            raise CommandError(
                f"{model_code} E2E candidate는 정확히 1건이어야 합니다."
            )
        candidate = matches[0]
        Command._validate_candidate_contract(candidate, model_code=model_code)
        return candidate

    @classmethod
    def _load_product_validation_scenario(
        cls,
        *,
        base_candidate: dict,
        model_code: str,
        scenario_id: str,
    ) -> dict:
        policy = APPROVED_PRODUCT_VALIDATION_SCENARIOS.get(scenario_id)
        if policy is None:
            raise CommandError("승인되지 않은 제품 미승인 E2E scenario_id입니다.")
        if policy["model_code"] != model_code:
            raise CommandError("scenario_id와 model_code가 일치하지 않습니다.")

        try:
            payload = json.loads(
                MANUAL_SCENARIO_FILE.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CommandError(
                "3모델 합성 Scenario 파일을 읽을 수 없습니다."
            ) from exc
        scenarios = payload.get("scenarios") if isinstance(payload, dict) else None
        if not isinstance(scenarios, list):
            raise CommandError("3모델 합성 Scenario root가 올바르지 않습니다.")
        matches = [
            item
            for item in scenarios
            if isinstance(item, dict) and item.get("scenario_id") == scenario_id
        ]
        if len(matches) != 1:
            raise CommandError(f"{scenario_id} Scenario는 정확히 1건이어야 합니다.")

        scenario = matches[0]
        cls._validate_product_validation_scenario(
            scenario,
            policy=policy,
        )
        expected_groups = scenario["retrieval_expectation"][
            "expected_evidence_group_ids"
        ]
        candidate = deepcopy(base_candidate)
        candidate.update(
            {
                "case_id": scenario_id,
                "runtime_status": scenario["runtime_profiles"]["mvp"][
                    "current_runtime"
                ]["verification_status"],
                "inquiry": {
                    "original_text": scenario["request"]["raw_symptom"],
                    "topic_code": scenario["topic_code"],
                },
                "safety": {
                    "risk_level": policy["risk_level"],
                    "requires_consultation": True,
                    "usage_guidance_status": policy[
                        "usage_guidance_status"
                    ],
                },
                "expected_outcome": {
                    "resolution_mode": "CONSULTANT_HANDOFF",
                },
                "product_validation_expectation": {
                    "case_name": policy["case_name"],
                    "fallback_reason_code": (
                        "RUNTIME_PRODUCT_NOT_APPROVED"
                    ),
                    "runtime_evidence_count": 0,
                    "vector_call_count": 0,
                    "provider_call_count": 0,
                },
            }
        )
        candidate["evidence"] = {
            **candidate["evidence"],
            "exact_sales_code": model_code,
            "evidence_group_id": expected_groups[0],
        }
        return candidate

    @staticmethod
    def _validate_product_validation_scenario(
        scenario: dict,
        *,
        policy: dict,
    ) -> None:
        request = scenario.get("request", {})
        product = scenario.get("product", {})
        retrieval = scenario.get("retrieval_expectation", {})
        current_runtime = (
            scenario.get("runtime_profiles", {})
            .get("mvp", {})
            .get("current_runtime", {})
        )
        ai = current_runtime.get("ai", {})
        expected_groups = retrieval.get("expected_evidence_group_ids")
        valid = (
            scenario.get("candidate_status") == "CANDIDATE"
            and scenario.get("data_classification") == "synthetic"
            and product.get("exact_sales_code") == policy["model_code"]
            and request.get("model_code") == policy["model_code"]
            and isinstance(request.get("raw_symptom"), str)
            and bool(request.get("raw_symptom", "").strip())
            and scenario.get("topic_code") == policy["topic_code"]
            and current_runtime.get("verification_status")
            == "STATIC_CONFIRMED"
            and ai.get("execution_status") == "FALLBACK"
            and ai.get("internal_issue_codes")
            == ["RUNTIME_PRODUCT_NOT_APPROVED"]
            and ai.get("risk_level") == policy["risk_level"]
            and ai.get("usage_guidance_status")
            == policy["usage_guidance_status"]
            and ai.get("requires_consultation") is True
            and isinstance(expected_groups, list)
            and len(expected_groups) == 1
            and isinstance(expected_groups[0], str)
            and expected_groups[0].startswith(
                f"EVD-{policy['model_code']}-"
            )
        )
        if not valid:
            raise CommandError(
                "제품 미승인 E2E Scenario가 승인된 MVP Oracle과 다릅니다."
            )

    @staticmethod
    def _validate_candidate_contract(candidate: dict, *, model_code: str) -> None:
        product = candidate.get("product", {})
        inquiry = candidate.get("inquiry", {})
        evidence = candidate.get("evidence", {})
        safety = candidate.get("safety", {})
        expected = candidate.get("expected_outcome", {})
        promotion = candidate.get("promotion", {})
        expected_risk = "danger" if model_code == "WPUIAC425SNW" else "caution"
        expected_resolution = (
            "CONSULTANT_HANDOFF"
            if model_code == "WPUIAC425SNW"
            else "SELF_RESOLUTION"
        )
        valid = (
            candidate.get("scope_status") == "E2E_CANDIDATE"
            and candidate.get("backend_import_status") == "NOT_IMPORTED"
            and candidate.get("runtime_status") == "NOT_VERIFIED"
            and candidate.get("data_classification") == "synthetic"
            and product.get("exact_sales_code") == model_code
            and evidence.get("exact_sales_code") == model_code
            and isinstance(inquiry.get("original_text"), str)
            and bool(inquiry.get("original_text", "").strip())
            and isinstance(inquiry.get("topic_code"), str)
            and bool(inquiry.get("topic_code", "").strip())
            and safety.get("risk_level") == expected_risk
            and isinstance(safety.get("requires_consultation"), bool)
            and expected.get("resolution_mode") == expected_resolution
            and promotion.get("canonical_fixture_included") is False
            and promotion.get("db_handoff_profile_included") is False
        )
        if not valid:
            raise CommandError(
                f"{model_code} E2E candidate가 Backend 후보 계약과 일치하지 않습니다."
            )
        if model_code == "WPUIAC425SNW" and not safety["requires_consultation"]:
            raise CommandError("IAC425 위험 Case는 상담 연결이 필수입니다.")
        if model_code == "WPUIAC606SNW" and safety["requires_consultation"]:
            raise CommandError("IAC606 주의 Case는 자가 해결 후보여야 합니다.")

    @staticmethod
    def _customer() -> tuple[User, CustomerProfile]:
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
        except (User.DoesNotExist, CustomerProfile.DoesNotExist) as exc:
            raise CommandError("seed_demo_accounts를 먼저 실행해야 합니다.") from exc
        return owner, customer

    @staticmethod
    def _product(candidate: dict) -> ProductModel:
        model_code = candidate["product"]["exact_sales_code"]
        try:
            public_id = UUID(candidate["product"]["fixture_public_id"])
            product = ProductModel.objects.get(model_code=model_code)
        except (ValueError, ProductModel.DoesNotExist) as exc:
            raise CommandError(
                f"{model_code} ProductModel을 db-product-expansion으로 먼저 준비해야 합니다."
            ) from exc
        if product.public_id != public_id:
            raise CommandError(
                f"{model_code} ProductModel public_id가 Candidate와 다릅니다."
            )
        return product

    @staticmethod
    def _readiness_blockers(*, product: ProductModel) -> list[str]:
        blockers = []
        if not product.is_active:
            blockers.append("PRODUCT_MODEL_INACTIVE")
        if not product.is_supported_mvp:
            blockers.append("PRODUCT_MODEL_RUNTIME_NOT_ENABLED")
        return blockers

    @staticmethod
    def _confirm_postgresql_database(expected_name: str | None) -> None:
        if connection.vendor != "postgresql":
            return
        actual = str(connection.settings_dict.get("NAME") or "")
        if not expected_name:
            raise CommandError("PostgreSQL apply에는 --confirm-database가 필요합니다.")
        if actual != expected_name:
            raise CommandError(
                "연결된 PostgreSQL DB가 --confirm-database와 다릅니다."
            )

    @classmethod
    def _confirm_isolated_database(cls, expected_name: str | None) -> None:
        cls._confirm_postgresql_database(expected_name)
        actual = str(connection.settings_dict.get("NAME") or "")
        if connection.vendor == "postgresql" and actual not in ISOLATED_DATABASE_NAMES:
            raise CommandError(
                "후보 Product 활성화는 waterbridge_team_integration에서만 허용합니다."
            )
        if connection.vendor != "postgresql" and "test" not in actual.lower():
            raise CommandError("후보 Product 활성화는 격리 Test DB에서만 허용합니다.")

    @staticmethod
    def _identity(
        *,
        model_code: str,
        run_id: str,
        scenario_id: str | None = None,
    ) -> dict[str, object]:
        identity_source = f"{model_code}/{run_id}"
        if scenario_id is not None:
            identity_source = f"{model_code}/{scenario_id}/{run_id}"
        digest = hashlib.sha256(identity_source.encode("utf-8")).hexdigest()
        short_model = model_code.removeprefix("WPU")
        return {
            "scenario_code": f"SYN-3M-{short_model}-{digest[:16]}",
            "subscription_public_id": uuid5(
                FIXTURE_NAMESPACE,
                f"subscription/{identity_source}",
            ),
            "customer_product_public_id": uuid5(
                FIXTURE_NAMESPACE,
                f"customer-product/{identity_source}",
            ),
            "contract_no": f"E2E-{short_model}-{digest[:24].upper()}",
            "serial_no": f"E2E-{short_model}-{digest[24:48].upper()}",
            "idempotency_key": f"product-expansion-e2e-{digest}",
            "correlation_id": uuid5(
                FIXTURE_NAMESPACE,
                f"correlation/{identity_source}",
            ),
        }

    @classmethod
    def _create_fixture(
        cls,
        *,
        candidate: dict,
        owner: User,
        customer: CustomerProfile,
        product: ProductModel,
        run_id: str,
        dry_run: bool,
        identity_scenario_id: str | None,
    ) -> dict:
        model_code = product.model_code
        identity = cls._identity(
            model_code=model_code,
            run_id=run_id,
            scenario_id=identity_scenario_id,
        )
        subscription, _ = CustomerSubscription.objects.get_or_create(
            contract_no=identity["contract_no"],
            defaults={
                "public_id": identity["subscription_public_id"],
                "customer": customer,
                "product_model": product,
                "serial_no": identity["serial_no"],
                "management_type_code": (
                    CustomerSubscription.ManagementType.SELF_MANAGED
                ),
                "status_code": CustomerSubscription.Status.ACTIVE,
                "started_on": date(2026, 8, 20),
                "ended_on": None,
                "installed_at": None,
                "installed_on": date(2026, 8, 20),
                "source_customer_product_public_id": identity[
                    "customer_product_public_id"
                ],
                "installation_address": "합성 3모델 E2E 설치 주소",
                "next_care_on": None,
            },
        )
        cls._assert_subscription(
            subscription=subscription,
            customer=customer,
            product=product,
            identity=identity,
        )

        outcome = InquiryService.create(
            actor=owner,
            validated_data={
                "subscription_id": subscription.public_id,
                "channel_code": Inquiry.Channel.MOBILE,
                "raw_text": candidate["inquiry"]["original_text"],
                "representative_symptom_code": candidate["inquiry"]["topic_code"],
                "questionnaire_session_id": None,
            },
            idempotency_key=identity["idempotency_key"],
            correlation_id=identity["correlation_id"],
        )
        inquiry = Inquiry.objects.select_for_update().get(
            public_id=outcome.data["inquiry_id"]
        )
        if inquiry.scenario_code is None:
            inquiry.scenario_code = identity["scenario_code"]
            inquiry.save(update_fields=["scenario_code", "updated_at"])
        cls._assert_unconsumed(
            inquiry=inquiry,
            owner=owner,
            subscription=subscription,
            identity=identity,
            candidate=candidate,
        )

        result = {
            "allowed_actions": [
                item["code"] for item in outcome.data["allowed_actions"]
            ],
            "candidate_case_id": candidate["case_id"],
            "candidate_runtime_status": candidate["runtime_status"],
            "created": not outcome.data["idempotent_replay"],
            "dry_run": dry_run,
            "evidence_group_id": candidate["evidence"]["evidence_group_id"],
            "expected_resolution_mode": candidate["expected_outcome"][
                "resolution_mode"
            ],
            "fixture_readiness": (
                "DRY_RUN_ROLLED_BACK" if dry_run else "READY_FOR_ISOLATED_E2E"
            ),
            "fixture_scope": FIXTURE_SCOPE,
            "inquiry_code": inquiry.inquiry_code,
            "inquiry_id": str(inquiry.public_id),
            "known_blockers": [],
            "model_code": model_code,
            "persisted": not dry_run,
            "request_correlation_id": str(identity["correlation_id"]),
            "run_id": run_id,
            "state_version": inquiry.state_version,
            "status": inquiry.status_code,
            "subscription_id": str(subscription.public_id),
            "topic_code": candidate["inquiry"]["topic_code"],
        }
        expectation = candidate.get("product_validation_expectation")
        if isinstance(expectation, dict):
            result.update(
                {
                    "case_name": expectation["case_name"],
                    "expected_fallback_reason_code": expectation[
                        "fallback_reason_code"
                    ],
                    "expected_provider_call_count": expectation[
                        "provider_call_count"
                    ],
                    "expected_risk_level": candidate["safety"][
                        "risk_level"
                    ],
                    "expected_runtime_evidence_count": expectation[
                        "runtime_evidence_count"
                    ],
                    "expected_usage_guidance_status": candidate["safety"][
                        "usage_guidance_status"
                    ],
                    "expected_vector_call_count": expectation[
                        "vector_call_count"
                    ],
                    "scenario_id": candidate["case_id"],
                    "symptom_description": candidate["inquiry"][
                        "original_text"
                    ],
                }
            )
        return result

    @staticmethod
    def _assert_subscription(
        *,
        subscription: CustomerSubscription,
        customer: CustomerProfile,
        product: ProductModel,
        identity: dict[str, object],
    ) -> None:
        matches = (
            subscription.public_id == identity["subscription_public_id"]
            and subscription.customer_id == customer.pk
            and subscription.product_model_id == product.pk
            and subscription.serial_no == identity["serial_no"]
            and subscription.source_customer_product_public_id
            == identity["customer_product_public_id"]
            and subscription.status_code == CustomerSubscription.Status.ACTIVE
        )
        if not matches:
            raise CommandError(
                "Existing product expansion Subscription identity conflicts."
            )

    @staticmethod
    def _assert_unconsumed(
        *,
        inquiry: Inquiry,
        owner: User,
        subscription: CustomerSubscription,
        identity: dict[str, object],
        candidate: dict,
    ) -> None:
        identity_matches = (
            inquiry.scenario_code == identity["scenario_code"]
            and inquiry.initiated_by_id == owner.pk
            and inquiry.subscription_id == subscription.pk
            and inquiry.raw_text == candidate["inquiry"]["original_text"]
        )
        unconsumed = (
            inquiry.status_code == Inquiry.Status.DRAFT
            and inquiry.state_version == 1
            and SymptomEntry.objects.filter(
                inquiry=inquiry,
                symptom_type_code=candidate["inquiry"]["topic_code"],
            ).count()
            == 1
            and not AIRun.objects.filter(inquiry=inquiry).exists()
            and not Consultation.objects.filter(inquiry=inquiry).exists()
        )
        if not identity_matches:
            raise CommandError("Existing product expansion Inquiry identity conflicts.")
        if not unconsumed:
            raise CommandError(
                "Product expansion E2E Fixture가 이미 소비되었습니다. "
                "이력을 되돌리지 말고 새 run_id를 사용하세요."
            )

    @staticmethod
    def _readiness_result(
        *,
        candidate: dict,
        product: ProductModel,
        run_id: str,
        blockers: list[str],
    ) -> dict:
        return {
            "candidate_case_id": candidate["case_id"],
            "candidate_runtime_status": candidate["runtime_status"],
            "evidence_group_id": candidate["evidence"]["evidence_group_id"],
            "fixture_readiness": "READY" if not blockers else "BLOCKED",
            "fixture_scope": FIXTURE_SCOPE,
            "known_blockers": blockers,
            "model_code": product.model_code,
            "product_active": product.is_active,
            "product_runtime_enabled": product.is_supported_mvp,
            "run_id": run_id,
        }

    def _render(self, payload: dict, *, json_output: bool) -> None:
        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if json_output:
            self.stdout.write(rendered)
            return
        self.stdout.write(
            self.style.SUCCESS(
                "Product expansion E2E fixture result: "
                f"{payload['fixture_readiness']}"
            )
        )
        self.stdout.write(f"PRODUCT_EXPANSION_E2E_CROSSWALK={rendered}")
