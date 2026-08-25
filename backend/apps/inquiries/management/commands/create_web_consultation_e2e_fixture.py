"""Create one repeatable run-scoped Web consultation E2E fixture."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from uuid import UUID, uuid5

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.management.commands.seed_demo_accounts import (
    DEMO_CUSTOMER_NO,
)
from apps.accounts.models import CustomerProfile, User
from apps.consultations.models import Consultation
from apps.inquiries.models import FollowUpAnswer, Inquiry, InquiryQA
from apps.inquiries.services.consultation_request_service import (
    ConsultationRequestService,
)
from apps.inquiries.services.consultation_claim_service import (
    ConsultationClaimService,
)
from apps.subscriptions.management.commands.seed_demo_subscriptions import (
    DEMO_SUBSCRIPTION_CONTRACT_NO,
)
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.engine.allowed_action_resolver import (
    AllowedActionContext,
    AllowedActionResolver,
)


DEMO_CUSTOMER_USERNAME = "DEMO-CUSTOMER-001"
DEMO_CONSULTANT_USERNAME = "DEMO-CONSULTANT-001"
FIXTURE_SCOPE = "WEB_G4_CONSULTATION"
FIXTURE_NAMESPACE = UUID("7f33867e-f2b8-4c4b-84dc-9bd5d8672f57")
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
MANUAL_SCENARIO_FILE = (
    REPOSITORY_ROOT
    / "data"
    / "config"
    / "synthetic"
    / "manual_3model_candidate_scenarios.json"
)
QUESTION_TEMPLATE_SCENARIO_ID = "SYN-JAC104-025"
QUESTION_TEMPLATE_MODEL_CODE = "WPUJAC104DWH"
SYNTHETIC_CUSTOMER_NAME = "제갈지용"
SYNTHETIC_CUSTOMER_PHONE = "010-1234-5678"
QUESTION_ANSWERS = {
    "followup-occurrence-time": "오늘",
    "followup-target-water-type": "정수",
    "followup-occurrence-condition": "출수 버튼을 누를 때",
    "followup-actions-taken": "필터 상태 확인",
}


class Command(BaseCommand):
    help = (
        "고유 run_id마다 상담사 Web G4용 새 합성 문의를 생성하고 "
        "공개 Crosswalk를 JSON으로 반환합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--run-id",
            required=True,
            help=(
                "1~64자의 실행 식별자. 영문자·숫자·점·밑줄·하이픈만 "
                "허용합니다."
            ),
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
            help="Web Playwright 인계용 공개 Crosswalk만 JSON으로 출력합니다.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        del args
        run_id = self._validate_run_id(options["run_id"])
        digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
        question_specs = self._load_question_specs()
        owner, customer, consultant, subscription = self._dependencies()
        identity = self._identity(run_id=run_id, digest=digest)

        inquiry, created = Inquiry.objects.get_or_create(
            scenario_code=identity["scenario_code"],
            defaults={
                "public_id": identity["inquiry_public_id"],
                "inquiry_code": identity["inquiry_code"],
                "subscription": subscription,
                "initiated_by": owner,
                "assigned_user": None,
                "assigned_role_code": Inquiry.AssignedRole.NONE,
                "channel_code": Inquiry.Channel.MOBILE,
                "raw_text": (
                    "합성 Web 상담 처리 E2E 문의: 저수압과 출수량 감소를 "
                    "상담사가 확인합니다."
                ),
                "risk_level_code": Inquiry.RiskLevel.CAUTION,
                "priority_code": Inquiry.Priority.NORMAL,
                "usage_guidance_status": (
                    Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION
                ),
                "evidence_ids": [],
                "evidence_mode": Inquiry.EvidenceMode.NO_EVIDENCE,
                "requires_fallback": True,
                "source_idempotency_key": identity["source_key"],
                "source_correlation_id": identity["correlation_id"],
                "status_code": Inquiry.Status.AI_GUIDANCE,
                "state_version": 1,
            },
        )
        inquiry = Inquiry.objects.select_for_update().get(pk=inquiry.pk)

        if created:
            self._prepare_synthetic_customer(customer)
            self._create_questionnaire(
                inquiry=inquiry,
                owner=owner,
                question_specs=question_specs,
            )
            self._request_and_claim(
                inquiry=inquiry,
                owner=owner,
                consultant=consultant,
                identity=identity,
            )
        else:
            self._assert_unconsumed(
                inquiry=inquiry,
                owner=owner,
                consultant=consultant,
                subscription=subscription,
                identity=identity,
            )

        self._assert_synthetic_customer(customer)
        self._assert_questionnaire(
            inquiry=inquiry,
            owner=owner,
            question_specs=question_specs,
        )

        inquiry.refresh_from_db()
        consultation = self._assigned_consultation(
            inquiry,
            consultant=consultant,
        )
        allowed_actions = AllowedActionResolver.resolve(
            context=AllowedActionContext.from_models(
                inquiry=inquiry,
                actor=consultant,
                consultation=consultation,
            )
        )
        crosswalk = {
            "allowed_actions": [item["code"] for item in allowed_actions],
            "assigned_consultant": DEMO_CONSULTANT_USERNAME,
            "consultation_status": consultation.status,
            "created": created,
            "fixture_readiness": "READY",
            "fixture_scope": FIXTURE_SCOPE,
            "g3_audit_result": "NOT_APPLICABLE",
            "inquiry_code": inquiry.inquiry_code,
            "inquiry_id": str(inquiry.public_id),
            "known_blocker": "NONE",
            "request_correlation_id": str(consultation.correlation_id),
            "run_id": run_id,
            "state_version": inquiry.state_version,
            "status": inquiry.status_code,
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
                "Web consultation E2E fixture ready "
                f"({state}=1, run_id={run_id}, inquiry_id={inquiry.public_id})"
            )
        )
        self.stdout.write(f"WEB_G4_FIXTURE_CROSSWALK={rendered}")

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
    def _load_question_specs() -> tuple[dict[str, object], ...]:
        try:
            payload = json.loads(
                MANUAL_SCENARIO_FILE.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CommandError(
                "3모델 합성 Scenario 파일을 읽을 수 없습니다."
            ) from exc

        scenarios = (
            payload.get("scenarios") if isinstance(payload, dict) else None
        )
        if (
            not isinstance(payload, dict)
            or payload.get("dataset_status") != "CANDIDATE"
            or not isinstance(scenarios, list)
            or len(scenarios) != 30
        ):
            raise CommandError(
                "3모델 합성 Scenario 30건의 Candidate 계약이 올바르지 않습니다."
            )

        matches = [
            item
            for item in scenarios
            if isinstance(item, dict)
            and item.get("scenario_id") == QUESTION_TEMPLATE_SCENARIO_ID
        ]
        if len(matches) != 1:
            raise CommandError(
                f"{QUESTION_TEMPLATE_SCENARIO_ID} Scenario는 정확히 1건이어야 합니다."
            )

        scenario = matches[0]
        product = scenario.get("product", {})
        question_expectations = scenario.get("question_expectations", {})
        common_questions = question_expectations.get("common")
        if (
            scenario.get("candidate_status") != "CANDIDATE"
            or scenario.get("data_classification") != "synthetic"
            or product.get("exact_sales_code") != QUESTION_TEMPLATE_MODEL_CODE
            or not isinstance(common_questions, list)
            or len(common_questions) != len(QUESTION_ANSWERS)
        ):
            raise CommandError(
                "Web G4 문진 Source Scenario 계약이 올바르지 않습니다."
            )

        normalized: list[dict[str, object]] = []
        seen_codes: set[str] = set()
        for raw_question in common_questions:
            if not isinstance(raw_question, dict):
                raise CommandError(
                    "Web G4 문진 질문 형식이 올바르지 않습니다."
                )
            question_code = raw_question.get("question_id")
            question_text = raw_question.get("question_text")
            options = raw_question.get("options")
            target_field = raw_question.get("target_field")
            answer = QUESTION_ANSWERS.get(question_code)
            if (
                not isinstance(question_code, str)
                or not question_code.strip()
                or question_code in seen_codes
                or not isinstance(question_text, str)
                or not question_text.strip()
                or not isinstance(options, list)
                or not options
                or any(
                    not isinstance(option, str) or not option.strip()
                    for option in options
                )
                or not isinstance(target_field, str)
                or not target_field.strip()
                or answer not in options
            ):
                raise CommandError(
                    "Web G4 문진 질문·답변 계약이 올바르지 않습니다."
                )
            seen_codes.add(question_code)
            normalized.append(
                {
                    "question_code": question_code,
                    "question_text": question_text.strip(),
                    "options": [option.strip() for option in options],
                    "target_field": target_field.strip(),
                    "answer": answer,
                }
            )

        if seen_codes != set(QUESTION_ANSWERS):
            raise CommandError("Web G4 문진 질문 집합이 예상값과 다릅니다.")

        expected_common_questions = [
            {
                "question_id": spec["question_code"],
                "question_text": spec["question_text"],
                "options": spec["options"],
                "target_field": spec["target_field"],
            }
            for spec in normalized
        ]
        for candidate in scenarios:
            candidate_questions = (
                candidate.get("question_expectations", {}).get("common")
                if isinstance(candidate, dict)
                else None
            )
            if candidate_questions != expected_common_questions:
                raise CommandError(
                    "3모델 합성 Scenario 30건의 공통 문진 계약이 "
                    "서로 다릅니다."
                )
        return tuple(normalized)

    @staticmethod
    def _identity(*, run_id: str, digest: str) -> dict[str, object]:
        return {
            "scenario_code": f"SYN-WEB-G4-{digest[:24]}",
            "inquiry_code": f"WEB-G4-INQ-{digest[:32].upper()}",
            "inquiry_public_id": uuid5(
                FIXTURE_NAMESPACE,
                f"inquiry/{run_id}",
            ),
            "correlation_id": uuid5(
                FIXTURE_NAMESPACE,
                f"correlation/{run_id}",
            ),
            "source_key": f"web-g4-fixture-{digest}",
            "request_key": f"web-g4-request-{digest}",
            "claim_key": f"web-g4-claim-{digest}",
        }

    @staticmethod
    def _dependencies() -> tuple[
        User,
        CustomerProfile,
        User,
        CustomerSubscription,
    ]:
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
            consultant = User.objects.get(
                username=DEMO_CONSULTANT_USERNAME,
                role_code=User.Role.CONSULTANT,
                is_active=True,
                is_synthetic=True,
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
        return owner, customer, consultant, subscription

    @staticmethod
    def _prepare_synthetic_customer(customer: CustomerProfile) -> None:
        allowed_names = {"합성 고객 001", SYNTHETIC_CUSTOMER_NAME}
        allowed_phones = {"", SYNTHETIC_CUSTOMER_PHONE}
        if (
            not customer.is_synthetic
            or customer.customer_no != DEMO_CUSTOMER_NO
            or customer.customer_name not in allowed_names
            or customer.phone not in allowed_phones
        ):
            raise CommandError(
                "Web G4 합성 고객 Profile이 안전한 갱신 조건과 다릅니다."
            )
        customer.customer_name = SYNTHETIC_CUSTOMER_NAME
        customer.phone = SYNTHETIC_CUSTOMER_PHONE
        customer.full_clean()
        customer.save(
            update_fields=["customer_name", "phone", "updated_at"]
        )

    @staticmethod
    def _assert_synthetic_customer(customer: CustomerProfile) -> None:
        customer.refresh_from_db()
        if (
            not customer.is_synthetic
            or customer.customer_no != DEMO_CUSTOMER_NO
            or customer.customer_name != SYNTHETIC_CUSTOMER_NAME
            or customer.phone != SYNTHETIC_CUSTOMER_PHONE
        ):
            raise CommandError(
                "Web G4 합성 고객 Profile이 예상값과 다릅니다."
            )

    @classmethod
    def _create_questionnaire(
        cls,
        *,
        inquiry: Inquiry,
        owner: User,
        question_specs: tuple[dict[str, object], ...],
    ) -> None:
        for sequence_no, spec in enumerate(question_specs, start=1):
            question_code = str(spec["question_code"])
            question = InquiryQA(
                public_id=uuid5(
                    FIXTURE_NAMESPACE,
                    f"question/{inquiry.public_id}/{question_code}",
                ),
                inquiry=inquiry,
                sequence_no=sequence_no,
                question_code=question_code,
                question_text=str(spec["question_text"]),
                answer_type_code="SINGLE_CHOICE",
                answer_payload={
                    "question_options": list(spec["options"]),
                    "target_field": str(spec["target_field"]),
                },
                asked_by_type_code="RULE",
            )
            question.full_clean()
            question.save()

            answer = FollowUpAnswer(
                public_id=uuid5(
                    FIXTURE_NAMESPACE,
                    f"answer/{inquiry.public_id}/{question_code}",
                ),
                question=question,
                answered_by=owner,
                answer_payload={"selected_option": spec["answer"]},
                accepted_state_version=inquiry.state_version,
            )
            answer.full_clean()
            answer.save()

    @staticmethod
    def _assert_questionnaire(
        *,
        inquiry: Inquiry,
        owner: User,
        question_specs: tuple[dict[str, object], ...],
    ) -> None:
        questions = list(
            InquiryQA.objects.filter(inquiry=inquiry)
            .select_related("customer_answer")
            .order_by("sequence_no", "public_id")
        )
        if len(questions) != len(question_specs):
            raise CommandError("Web G4 문진 질문 수가 예상값과 다릅니다.")

        for sequence_no, (question, spec) in enumerate(
            zip(questions, question_specs, strict=True),
            start=1,
        ):
            expected_code = str(spec["question_code"])
            expected_question_id = uuid5(
                FIXTURE_NAMESPACE,
                f"question/{inquiry.public_id}/{expected_code}",
            )
            expected_answer_id = uuid5(
                FIXTURE_NAMESPACE,
                f"answer/{inquiry.public_id}/{expected_code}",
            )
            try:
                answer = question.customer_answer
            except FollowUpAnswer.DoesNotExist as exc:
                raise CommandError("Web G4 문진 답변이 누락되었습니다.") from exc
            matches = (
                question.public_id == expected_question_id
                and question.sequence_no == sequence_no
                and question.question_code == expected_code
                and question.question_text == spec["question_text"]
                and question.answer_type_code == "SINGLE_CHOICE"
                and question.question_options == spec["options"]
                and question.target_field == spec["target_field"]
                and answer.public_id == expected_answer_id
                and answer.answered_by_id == owner.pk
                and answer.answer_text is None
                and answer.answer_payload
                == {"selected_option": spec["answer"]}
                and answer.accepted_state_version == 1
            )
            if not matches:
                raise CommandError(
                    "Web G4 문진 질문·답변이 예상값과 다릅니다."
                )

    @staticmethod
    def _request_and_claim(
        *,
        inquiry: Inquiry,
        owner: User,
        consultant: User,
        identity: dict[str, object],
    ) -> None:
        ConsultationRequestService.request(
            actor=owner,
            inquiry_public_id=inquiry.public_id,
            validated_data={"state_version": inquiry.state_version},
            idempotency_key=str(identity["request_key"]),
            correlation_id=identity["correlation_id"],
        )
        inquiry.refresh_from_db()
        ConsultationClaimService.claim(
            actor=consultant,
            inquiry_public_id=inquiry.public_id,
            validated_data={"state_version": inquiry.state_version},
            idempotency_key=str(identity["claim_key"]),
            correlation_id=identity["correlation_id"],
        )

    @classmethod
    def _assert_unconsumed(
        cls,
        *,
        inquiry: Inquiry,
        owner: User,
        consultant: User,
        subscription: CustomerSubscription,
        identity: dict[str, object],
    ) -> None:
        identity_matches = (
            inquiry.public_id == identity["inquiry_public_id"]
            and inquiry.inquiry_code == identity["inquiry_code"]
            and inquiry.initiated_by_id == owner.pk
            and inquiry.subscription_id == subscription.pk
            and inquiry.source_idempotency_key == identity["source_key"]
            and inquiry.source_correlation_id == identity["correlation_id"]
            and inquiry.assigned_user_id == consultant.pk
            and inquiry.assigned_role_code == Inquiry.AssignedRole.CONSULTANT
        )
        if not identity_matches:
            raise CommandError("Existing Web G4 Fixture identity conflicts.")

        cls._assigned_consultation(
            inquiry,
            consultant=consultant,
        )
        if (
            inquiry.status_code != Inquiry.Status.CONSULTATION_REQUIRED
            or inquiry.state_version != 3
        ):
            raise CommandError(
                "Web G4 Fixture가 이미 소비되었습니다. 이력을 되돌리지 말고 "
                "새 run_id를 사용하세요."
            )

    @staticmethod
    def _assigned_consultation(
        inquiry: Inquiry,
        *,
        consultant: User,
    ) -> Consultation:
        consultations = list(
            Consultation.objects.filter(inquiry=inquiry).order_by("sequence")
        )
        if len(consultations) != 1:
            raise CommandError(
                "Web G4 Fixture 상담 요청 수가 예상값 1과 다릅니다."
            )
        consultation = consultations[0]
        if (
            consultation.status != Consultation.Status.ASSIGNED
            or consultation.consultant_id != consultant.pk
            or consultation.started_at is not None
            or consultation.state_version != inquiry.state_version
        ):
            raise CommandError(
                "Web G4 Fixture가 이미 소비되었습니다. 이력을 되돌리지 말고 "
                "새 run_id를 사용하세요."
            )
        return consultation
