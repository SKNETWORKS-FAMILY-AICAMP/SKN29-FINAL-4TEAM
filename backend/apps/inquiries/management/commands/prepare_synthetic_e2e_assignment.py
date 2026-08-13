"""Mark one exact runtime inquiry for the approved synthetic E2E assignment."""

from __future__ import annotations

import json
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.inquiries.models import Inquiry
from apps.inquiries.services.synthetic_e2e_assignment_service import (
    DEMO_CONSULTANT_USERNAME,
    SYNTHETIC_E2E_ASSIGNMENT_MODE,
    SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE,
    SYNTHETIC_E2E_SCENARIO_REFERENCE,
    SyntheticE2EAssignmentService,
    SyntheticE2EAssignmentValidationError,
)


class Command(BaseCommand):
    help = (
        "Mobile에서 생성된 한 개의 합성 문의를 대표 E2E 상담사 배정 대상으로 "
        "안전하게 표시합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--inquiry-id",
            required=True,
            type=UUID,
            help="Mobile이 생성한 합성 문의의 public UUID",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
            help="Frontend 인계용 공개 Crosswalk만 JSON으로 출력합니다.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        del args
        inquiry = self._locked_inquiry(options["inquiry_id"])
        try:
            SyntheticE2EAssignmentService.validate_preparation_candidate(
                inquiry
            )
            SyntheticE2EAssignmentService.require_active_demo_consultant()
        except SyntheticE2EAssignmentValidationError as exc:
            raise CommandError(str(exc)) from exc

        duplicate_marker = (
            Inquiry.objects.select_for_update(of=("self",))
            .filter(scenario_code=SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE)
            .exclude(pk=inquiry.pk)
            .exists()
        )
        if duplicate_marker:
            raise CommandError(
                "다른 문의가 이미 합성 E2E 배정 대상으로 표시되어 있습니다."
            )

        created = inquiry.scenario_code != SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE
        if created:
            inquiry.scenario_code = SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE
            inquiry.save(update_fields=["scenario_code", "updated_at"])

        crosswalk = {
            "assigned_consultant_code": DEMO_CONSULTANT_USERNAME,
            "assignment_mode": SYNTHETIC_E2E_ASSIGNMENT_MODE,
            "inquiry_code": inquiry.inquiry_code,
            "inquiry_id": str(inquiry.public_id),
            "operation_id": "requestConsultation",
            "scenario_code": SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE,
            "scenario_reference": SYNTHETIC_E2E_SCENARIO_REFERENCE,
            "state_version": inquiry.state_version,
            "status_code": inquiry.status_code,
        }
        rendered = json.dumps(
            crosswalk,
            ensure_ascii=False,
            sort_keys=True,
        )
        if options["json_output"]:
            self.stdout.write(rendered)
            return

        state = "marked" if created else "verified"
        self.stdout.write(
            self.style.SUCCESS(
                "Synthetic E2E assignment candidate ready "
                f"({state}=1, inquiry_id={inquiry.public_id})"
            )
        )
        self.stdout.write(f"SYNTHETIC_E2E_ASSIGNMENT_CROSSWALK={rendered}")

    @staticmethod
    def _locked_inquiry(inquiry_public_id: UUID) -> Inquiry:
        inquiry = (
            Inquiry.objects.select_for_update(of=("self",))
            .select_related(
                "initiated_by",
                "assigned_user",
                "subscription",
                "subscription__customer",
                "subscription__customer__user",
                "subscription__product_model",
            )
            .filter(public_id=inquiry_public_id)
            .first()
        )
        if inquiry is None:
            raise CommandError("지정한 문의를 찾을 수 없습니다.")
        return inquiry
