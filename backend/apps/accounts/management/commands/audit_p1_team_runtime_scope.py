"""Plan a P1-team-only runtime without mutating the current database."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import Count, F, Q

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
EXPECTED_PRODUCT_MODEL_CODE = "WPUJAC104DWH"
EXPECTED_CONSULTANT_USERNAME = "DEMO-CONSULTANT-001"
EXPECTED_CONSULTANT_EMPLOYEE_NO = "DEMO-EMP-CNS-001"
EXPECTED_CONSULTANT_NAME = "합성 상담사 001"


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
        parser.add_argument(
            "--operational",
            action="store_true",
            help=(
                "P1 고객의 OTP 가입 계정과 그 고객 소유 문의만 허용합니다. "
                "기본값은 가입 전 고객 User와 문의가 모두 0인 Baseline입니다."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        del args
        operational = bool(options["operational"])
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
        preserve_all_contact_count = ContractEmailContact.objects.filter(
            customer_id__in=preserve_ids,
        ).count()
        preserve_subscription_count = CustomerSubscription.objects.filter(
            customer_id__in=preserve_ids,
            status_code=CustomerSubscription.Status.ACTIVE,
            product_model__model_code=EXPECTED_PRODUCT_MODEL_CODE,
        ).count()
        preserve_all_subscription_count = CustomerSubscription.objects.filter(
            customer_id__in=preserve_ids,
        ).count()
        per_customer = preserve.annotate(
            active_primary_contact_count=Count(
                "contract_email_contacts",
                filter=Q(
                    contract_email_contacts__is_active=True,
                    contract_email_contacts__is_primary=True,
                ),
                distinct=True,
            ),
            active_jac_subscription_count=Count(
                "subscriptions",
                filter=Q(
                    subscriptions__status_code=CustomerSubscription.Status.ACTIVE,
                    subscriptions__product_model__model_code=(
                        EXPECTED_PRODUCT_MODEL_CODE
                    ),
                ),
                distinct=True,
            ),
        )
        if (
            preserve_contact_count != EXPECTED_PRESERVE_COUNT
            or preserve_all_contact_count != EXPECTED_PRESERVE_COUNT
            or per_customer.exclude(active_primary_contact_count=1).exists()
        ):
            blockers.append("P1_TEAM_ACTIVE_PRIMARY_CONTACT_NOT_6")
        if (
            preserve_subscription_count != EXPECTED_PRESERVE_COUNT
            or preserve_all_subscription_count != EXPECTED_PRESERVE_COUNT
            or per_customer.exclude(active_jac_subscription_count=1).exists()
        ):
            blockers.append("P1_TEAM_ACTIVE_SUBSCRIPTION_NOT_6")

        if remove_customers.exists():
            blockers.append("NON_P1_CUSTOMER_PRESENT")

        consultants = User.objects.filter(role_code=User.Role.CONSULTANT)
        exact_consultants = consultants.filter(
            username=EXPECTED_CONSULTANT_USERNAME,
            full_name=EXPECTED_CONSULTANT_NAME,
            employee_no=EXPECTED_CONSULTANT_EMPLOYEE_NO,
            is_active=True,
            is_synthetic=True,
            is_staff=False,
            is_superuser=False,
        )
        if consultants.count() != 1 or exact_consultants.count() != 1:
            blockers.append("P1_TEAM_CONSULTANT_IDENTITY_NOT_EXACT_1")

        linked_p1_user_ids = set(
            preserve.exclude(user_id=None).values_list("user_id", flat=True)
        )
        linked_p1_user_ids.update(
            CustomerAccountLink.objects.filter(
                customer_id__in=preserve_ids,
                is_active=True,
            ).values_list("user_id", flat=True)
        )
        customer_users = User.objects.filter(role_code=User.Role.CUSTOMER)
        invalid_p1_customer_users = User.objects.filter(
            id__in=linked_p1_user_ids,
        ).exclude(
            role_code=User.Role.CUSTOMER,
            is_active=True,
            is_synthetic=True,
            employee_no__isnull=True,
        )
        foreign_customer_users = customer_users.exclude(id__in=linked_p1_user_ids)
        technician_user_count = User.objects.filter(
            role_code=User.Role.TECHNICIAN
        ).count()
        operator_user_count = User.objects.filter(
            role_code=User.Role.OPERATOR
        ).count()
        if operational:
            if invalid_p1_customer_users.exists() or foreign_customer_users.exists():
                blockers.append("NON_P1_OR_INVALID_CUSTOMER_USER_PRESENT")
        elif customer_users.exists():
            blockers.append("P1_TEAM_BASELINE_CUSTOMER_USER_PRESENT")
        if technician_user_count:
            blockers.append("P1_TEAM_TECHNICIAN_USER_PRESENT")
        if operator_user_count:
            blockers.append("P1_TEAM_OPERATOR_USER_PRESENT")

        inquiries = Inquiry.objects.all()
        p1_owned_inquiries = inquiries.filter(
            subscription__customer_id__in=preserve_ids,
            initiated_by_id=F("subscription__customer__user_id"),
            initiated_by__role_code=User.Role.CUSTOMER,
            initiated_by__is_active=True,
            initiated_by__is_synthetic=True,
        )
        p1_inquiry_ids = list(p1_owned_inquiries.values_list("id", flat=True))
        non_p1_inquiry_ids = list(
            inquiries.exclude(id__in=p1_inquiry_ids).values_list("id", flat=True)
        )
        inquiry_ids = p1_inquiry_ids + non_p1_inquiry_ids
        if non_p1_inquiry_ids:
            blockers.append("NON_P1_INQUIRY_PRESENT")
        if not operational and p1_inquiry_ids:
            blockers.append("P1_TEAM_BASELINE_INQUIRY_PRESENT")

        user_role_counts = {
            role: User.objects.filter(role_code=role).count()
            for role in User.Role.values
        }
        result = {
            "mode": (
                "OPERATIONAL_READ_ONLY" if operational else "PLAN_ONLY_READ_ONLY"
            ),
            "runtime_phase": "OPERATIONAL" if operational else "BASELINE",
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
                "consultant_users": consultants.filter(is_active=True).count(),
                "exact_consultant_users": exact_consultants.count(),
                "user_role_counts": user_role_counts,
                "p1_linked_customer_users": len(linked_p1_user_ids),
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
            "runtime": {
                "p1_owned_inquiries": len(p1_inquiry_ids),
                "non_p1_inquiries": len(non_p1_inquiry_ids),
                "operational_p1_inquiries_allowed": operational,
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
