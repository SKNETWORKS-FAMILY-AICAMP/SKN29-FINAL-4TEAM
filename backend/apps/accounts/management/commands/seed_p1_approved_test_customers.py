"""PM-approved six-recipient local OTP E2E seed."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.management.commands.seed_p1_account_link_fixture import (
    _ensure_product,
)
from apps.accounts.models import (
    ContractEmailContact,
    CustomerAccountLink,
    CustomerProfile,
)
from apps.accounts.services.contract_email_protection import (
    ContractEmailProtectionError,
    ContractEmailProtectionService,
)
from apps.subscriptions.models import CustomerSubscription


EXPECTED_CUSTOMER_COUNT = 6
PRODUCT_MODEL_CODE = "WPUJAC104DWH"
SOURCE_SYSTEM = "PM_APPROVED_LOCAL_E2E_20260825"
PHONE_PATTERN = re.compile(r"^010-[0-9]{4}-[0-9]{4}$")


def _load_approved_rows(path: Path) -> list[dict[str, str]]:
    runtime_root = (Path(settings.BASE_DIR) / ".runtime").resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(runtime_root)
    except ValueError as exc:
        raise CommandError(
            "승인 입력 파일은 Git 제외 backend/.runtime 아래에 있어야 합니다."
        ) from exc
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CommandError("승인 입력 파일을 읽을 수 없습니다.") from exc
    if (
        not isinstance(document, list)
        or len(document) != EXPECTED_CUSTOMER_COUNT
    ):
        raise CommandError("PM 승인 대상은 정확히 6건이어야 합니다.")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    seen_phones: set[str] = set()
    for item in document:
        if not isinstance(item, dict) or set(item) != {
            "name",
            "phone",
            "email",
        }:
            raise CommandError("승인 입력 항목의 필드를 확인해 주세요.")
        row = {
            key: str(item[key]).strip()
            for key in ("name", "phone", "email")
        }
        if not row["name"] or len(row["name"]) > 100:
            raise CommandError("승인 고객 이름 형식을 확인해 주세요.")
        if not PHONE_PATTERN.fullmatch(row["phone"]):
            raise CommandError("승인 고객 합성 전화번호 형식을 확인해 주세요.")
        if row["name"] in seen_names or row["phone"] in seen_phones:
            raise CommandError("승인 고객 이름과 전화번호는 중복될 수 없습니다.")
        seen_names.add(row["name"])
        seen_phones.add(row["phone"])
        rows.append(row)
    return rows


def _ensure_customer(
    index: int,
    row: dict[str, str],
) -> tuple[CustomerProfile, bool]:
    customer_no = f"SYN-P1-TEAM-CUSTOMER-{index:03d}"
    expected = {
        "user_id": None,
        "customer_name": row["name"],
        "phone": row["phone"],
        "is_synthetic": True,
        "deleted_at": None,
    }
    customer, created = CustomerProfile.objects.get_or_create(
        customer_no=customer_no,
        defaults={
            "user": None,
            "customer_name": row["name"],
            "phone": row["phone"],
            "postal_code": "",
            "address_line1": "",
            "address_line2": "",
            "consent_version": "",
            "consented_at": None,
            "is_synthetic": True,
        },
    )
    conflicts = [
        field
        for field, expected_value in expected.items()
        if getattr(customer, field) != expected_value
    ]
    if conflicts:
        raise CommandError(
            "기존 승인 고객 행이 현재 범위와 충돌합니다: "
            f"index={index}, fields={','.join(sorted(conflicts))}"
        )
    if CustomerAccountLink.objects.filter(customer=customer).exists():
        raise CommandError(
            f"승인 고객은 가입 전 상태여야 합니다: index={index}"
        )
    customer.full_clean()
    return customer, created


def _ensure_contact(
    *,
    index: int,
    customer: CustomerProfile,
    email: str,
    protection: ContractEmailProtectionService,
) -> tuple[ContractEmailContact, bool]:
    try:
        protected = protection.protect_approved_test(email)
    except ContractEmailProtectionError as exc:
        raise CommandError(
            f"승인 시험 이메일 형식을 확인해 주세요: index={index}"
        ) from exc
    existing = ContractEmailContact.objects.filter(
        customer=customer,
        is_active=True,
        is_primary=True,
    ).first()
    if existing is not None:
        valid = (
            existing.email_lookup_hmac == protected.email_lookup_hmac
            and existing.key_version == protected.key_version
            and existing.delivery_policy
            == ContractEmailContact.DeliveryPolicy.APPROVED_TEST_RECIPIENT
            and existing.data_classification
            == ContractEmailContact.DataClassification.APPROVED_TEST_PII
            and existing.source_system == SOURCE_SYSTEM
            and protection.decrypt(existing.encrypted_email)
            == protection.decrypt(protected.encrypted_email)
        )
        if not valid:
            raise CommandError(
                f"기존 승인 이메일 보호 행이 충돌합니다: index={index}"
            )
        existing.full_clean()
        return existing, False

    contact = ContractEmailContact(
        customer=customer,
        encrypted_email=protected.encrypted_email,
        email_lookup_hmac=protected.email_lookup_hmac,
        key_version=protected.key_version,
        is_active=True,
        is_primary=True,
        delivery_policy=(
            ContractEmailContact.DeliveryPolicy.APPROVED_TEST_RECIPIENT
        ),
        source_system=SOURCE_SYSTEM,
        data_classification=(
            ContractEmailContact.DataClassification.APPROVED_TEST_PII
        ),
    )
    contact.full_clean()
    contact.save()
    return contact, True


def _ensure_subscription(
    *,
    index: int,
    customer: CustomerProfile,
    product,
) -> tuple[CustomerSubscription, bool]:
    contract_no = f"SYN-P1-TEAM-CONTRACT-{index:03d}"
    expected = {
        "customer_id": customer.pk,
        "product_model_id": product.pk,
        "serial_no": f"SYN-P1-TEAM-JAC104D-{index:03d}",
        "management_type_code": (
            CustomerSubscription.ManagementType.VISIT_CARE
        ),
        "status_code": CustomerSubscription.Status.ACTIVE,
        "started_on": date(2026, 8, 25),
        "ended_on": None,
        "next_care_on": date(2026, 9, 25),
    }
    subscription, created = CustomerSubscription.objects.get_or_create(
        contract_no=contract_no,
        defaults={
            "customer": customer,
            "product_model": product,
            "serial_no": expected["serial_no"],
            "management_type_code": expected["management_type_code"],
            "status_code": expected["status_code"],
            "started_on": expected["started_on"],
            "ended_on": None,
            "installed_at": None,
            "installed_on": None,
            "source_customer_product_public_id": None,
            "installation_address": None,
            "next_care_on": expected["next_care_on"],
        },
    )
    conflicts = [
        field
        for field, expected_value in expected.items()
        if getattr(subscription, field) != expected_value
    ]
    if conflicts:
        raise CommandError(
            "기존 승인 구독 행이 현재 범위와 충돌합니다: "
            f"index={index}, fields={','.join(sorted(conflicts))}"
        )
    subscription.full_clean()
    return subscription, created


class Command(BaseCommand):
    help = (
        "PM 승인 팀원 6명의 실제 시험 이메일을 로컬에서만 암호화+HMAC으로 "
        "적재합니다. User와 CustomerAccountLink는 생성하지 않습니다."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--input-file", type=Path, required=True)
        parser.add_argument("--pm-approved-local-e2e", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--json", action="store_true")

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        del args
        if not settings.DEBUG or not options["pm_approved_local_e2e"]:
            raise CommandError(
                "이 명령은 PM 승인 표시가 있는 DEBUG 로컬 환경에서만 실행됩니다."
            )
        rows = _load_approved_rows(Path(options["input_file"]))
        try:
            protection = ContractEmailProtectionService.from_settings()
        except ContractEmailProtectionError as exc:
            raise CommandError(str(exc)) from exc

        protected_hmacs = []
        for index, row in enumerate(rows, start=1):
            try:
                protected_hmacs.append(
                    protection.protect_approved_test(
                        row["email"]
                    ).email_lookup_hmac
                )
            except ContractEmailProtectionError as exc:
                raise CommandError(
                    f"승인 시험 이메일 형식을 확인해 주세요: index={index}"
                ) from exc
        if len(set(protected_hmacs)) != EXPECTED_CUSTOMER_COUNT:
            raise CommandError("승인 시험 이메일은 중복될 수 없습니다.")

        product, product_created = _ensure_product(PRODUCT_MODEL_CODE)
        counts = {
            "products_created": int(product_created),
            "customers_created": 0,
            "contacts_created": 0,
            "subscriptions_created": 0,
        }
        for index, row in enumerate(rows, start=1):
            customer, customer_created = _ensure_customer(index, row)
            _, contact_created = _ensure_contact(
                index=index,
                customer=customer,
                email=row["email"],
                protection=protection,
            )
            _, subscription_created = _ensure_subscription(
                index=index,
                customer=customer,
                product=product,
            )
            counts["customers_created"] += int(customer_created)
            counts["contacts_created"] += int(contact_created)
            counts["subscriptions_created"] += int(subscription_created)

        status = "DRY_RUN_READY" if options["dry_run"] else "APPLIED"
        result = {
            "status": status,
            **counts,
            "approved_customers": EXPECTED_CUSTOMER_COUNT,
            "active_contracts": EXPECTED_CUSTOMER_COUNT,
            "active_contacts": EXPECTED_CUSTOMER_COUNT,
            "active_subscriptions": EXPECTED_CUSTOMER_COUNT,
            "candidate_users": 0,
            "candidate_account_links": 0,
            "plaintext_email_stored": False,
            "delivery_policy": "APPROVED_TEST_RECIPIENT",
            "environment_scope": "LOCAL_DEBUG_ONLY",
        }
        if options["dry_run"]:
            transaction.set_rollback(True)

        if options["json"]:
            self.stdout.write(
                json.dumps(result, ensure_ascii=False, sort_keys=True)
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"PM-approved local OTP customers ready (status={status}, "
                    f"customers={EXPECTED_CUSTOMER_COUNT}, users=0, links=0)"
                )
            )
