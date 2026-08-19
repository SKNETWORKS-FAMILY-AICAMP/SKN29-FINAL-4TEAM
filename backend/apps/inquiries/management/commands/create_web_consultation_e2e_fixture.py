"""Create one repeatable run-scoped Web consultation E2E fixture."""

from __future__ import annotations

import hashlib
import json
import re
from uuid import UUID, uuid5

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.management.commands.seed_demo_accounts import (
    DEMO_CUSTOMER_NO,
)
from apps.accounts.models import CustomerProfile, User
from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry
from apps.inquiries.services.consultation_request_service import (
    ConsultationRequestService,
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
        owner, consultant, subscription = self._dependencies()
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
            self._request_and_assign(
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

        inquiry.refresh_from_db()
        consultation = self._waiting_consultation(inquiry)
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
        }

    @staticmethod
    def _dependencies() -> tuple[User, User, CustomerSubscription]:
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
        return owner, consultant, subscription

    @staticmethod
    def _request_and_assign(
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
        inquiry.assigned_user = consultant
        inquiry.assigned_role_code = Inquiry.AssignedRole.CONSULTANT
        inquiry.clean()
        inquiry.save(
            update_fields=[
                "assigned_user",
                "assigned_role_code",
                "updated_at",
            ]
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

        cls._waiting_consultation(inquiry)
        if (
            inquiry.status_code != Inquiry.Status.CONSULTATION_REQUIRED
            or inquiry.state_version != 2
        ):
            raise CommandError(
                "Web G4 Fixture가 이미 소비되었습니다. 이력을 되돌리지 말고 "
                "새 run_id를 사용하세요."
            )

    @staticmethod
    def _waiting_consultation(inquiry: Inquiry) -> Consultation:
        consultations = list(
            Consultation.objects.filter(inquiry=inquiry).order_by("sequence")
        )
        if len(consultations) != 1:
            raise CommandError(
                "Web G4 Fixture 상담 요청 수가 예상값 1과 다릅니다."
            )
        consultation = consultations[0]
        if (
            consultation.status != Consultation.Status.WAITING
            or consultation.consultant_id is not None
            or consultation.state_version != inquiry.state_version
        ):
            raise CommandError(
                "Web G4 Fixture가 이미 소비되었습니다. 이력을 되돌리지 말고 "
                "새 run_id를 사용하세요."
            )
        return consultation
