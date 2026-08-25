"""Plan a P1-team-only runtime without mutating the current database."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.accounts.models import (
    ContractEmailContact,
    CustomerAccountLink,
    CustomerProfile,
    User,
)
from apps.audit.models import AIRun
from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry
from apps.subscriptions.models import CustomerSubscription
from apps.visits.models import Visit


PRESERVE_PREFIX = "SYN-P1-TEAM-CUSTOMER-"
EXPECTED_PRESERVE_COUNT = 6


def _safe_output_path(value: str) -> Path:
    runtime_root = (Path(settings.BASE_DIR) / ".runtime").resolve()
    output = Path(value).resolve()
    try:
        output.relative_to(runtime_root)
    except ValueError as exc:
        raise CommandError(
            "점검 결과는 Git 제외 backend/.runtime 아래에만 저장할 수 있습니다."
        ) from exc
    return output


class Command(BaseCommand):
    help = (
        "현재 DB를 수정하지 않고 P1 팀 고객 6명 보존 및 기존 고객·문의 "
        "삭제 후보 수를 점검합니다."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--output-file")

    def handle(self, *args: Any, **options: Any) -> None:
        del args
        preserve = CustomerProfile.objects.filter(
            customer_no__startswith=PRESERVE_PREFIX,
        ).order_by("customer_no")
        remove_customers = CustomerProfile.objects.exclude(
            customer_no__startswith=PRESERVE_PREFIX,
        )
        preserve_ids = list(preserve.values_list("id", flat=True))

        blockers: list[str] = []
        preserve_numbers = list(preserve.values_list("customer_no", flat=True))
        expected_numbers = [
            f"{PRESERVE_PREFIX}{index:03d}"
            for index in range(1, EXPECTED_PRESERVE_COUNT + 1)
        ]
        if preserve_numbers != expected_numbers:
            blockers.append("P1_TEAM_CUSTOMER_SET_NOT_EXACT_6")
        if preserve.filter(is_synthetic=False).exists():
            blockers.append("P1_TEAM_CUSTOMER_NOT_SYNTHETIC")
        if remove_customers.filter(is_synthetic=False).exists():
            blockers.append("NON_SYNTHETIC_DELETE_CANDIDATE_PRESENT")

        preserve_contact_count = ContractEmailContact.objects.filter(
            customer_id__in=preserve_ids,
            is_active=True,
            is_primary=True,
        ).count()
        preserve_subscription_count = CustomerSubscription.objects.filter(
            customer_id__in=preserve_ids,
            status_code=CustomerSubscription.Status.ACTIVE,
        ).count()
        if preserve_contact_count != EXPECTED_PRESERVE_COUNT:
            blockers.append("P1_TEAM_ACTIVE_PRIMARY_CONTACT_NOT_6")
        if preserve_subscription_count != EXPECTED_PRESERVE_COUNT:
            blockers.append("P1_TEAM_ACTIVE_SUBSCRIPTION_NOT_6")

        inquiry_ids = list(Inquiry.objects.values_list("id", flat=True))
        result = {
            "mode": "PLAN_ONLY_READ_ONLY",
            "database_name": connection.settings_dict.get("NAME", ""),
            "source_database_mutated": False,
            "isolated_database_required": True,
            "preserve": {
                "customer_numbers": preserve_numbers,
                "customers": len(preserve_ids),
                "active_primary_contacts": preserve_contact_count,
                "active_subscriptions": preserve_subscription_count,
                "linked_accounts": CustomerAccountLink.objects.filter(
                    customer_id__in=preserve_ids,
                    is_active=True,
                ).count(),
                "consultant_users": User.objects.filter(
                    role_code=User.Role.CONSULTANT,
                    is_active=True,
                ).count(),
            },
            "delete_candidates": {
                "customers": remove_customers.count(),
                "customer_subscriptions": CustomerSubscription.objects.exclude(
                    customer_id__in=preserve_ids,
                ).count(),
                "inquiries": len(inquiry_ids),
                "consultations": Consultation.objects.filter(
                    inquiry_id__in=inquiry_ids,
                ).count(),
                "visits": Visit.objects.filter(
                    inquiry_id__in=inquiry_ids,
                ).count(),
                "ai_runs": AIRun.objects.filter(
                    inquiry_id__in=inquiry_ids,
                ).count(),
            },
            "blockers": sorted(set(blockers)),
            "ready_for_isolated_rebuild": not blockers,
        }

        payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
        if options.get("output_file"):
            output = _safe_output_path(str(options["output_file"]))
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(f"{payload}\n", encoding="utf-8")
        if options["json"]:
            self.stdout.write(payload)
        else:
            self.stdout.write(self.style.SUCCESS(payload))
