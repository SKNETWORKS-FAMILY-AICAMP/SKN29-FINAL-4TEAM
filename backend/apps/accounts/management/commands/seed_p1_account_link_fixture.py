"""승인된 P1-A 가입 전 합성 계약고객 Fixture를 멱등 적재한다."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from jsonschema import Draft202012Validator

from apps.accounts.models import (
    ContractEmailContact,
    CustomerAccountLink,
    CustomerProfile,
    User,
)
from apps.accounts.services.contract_email_protection import (
    ContractEmailProtectionError,
    ContractEmailProtectionService,
    normalize_synthetic_contract_email,
)
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


DEFAULT_CANDIDATE = (
    Path(settings.BASE_DIR).parent
    / "data"
    / "synthetic"
    / "candidates"
    / "p1_account_link_candidates.json"
)
DEFAULT_SCHEMA = (
    Path(settings.BASE_DIR).parent
    / "data"
    / "schemas"
    / "synthetic"
    / "p1AccountLinkCandidate.schema.json"
)
PRODUCT_FIXTURE = (
    Path(settings.BASE_DIR).parent
    / "data"
    / "synthetic"
    / "fixtures"
    / "products.json"
)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommandError(
            f"승인 Fixture를 읽을 수 없습니다: {path.name}"
        ) from exc


def _validate_candidates(
    candidate_path: Path,
    schema_path: Path,
) -> list[dict[str, Any]]:
    candidates = _load_json(candidate_path)
    schema = _load_json(schema_path)
    if not isinstance(candidates, list) or not candidates:
        raise CommandError("P1-A Candidate 배열이 비어 있습니다.")
    validator = Draft202012Validator(schema)
    for candidate in candidates:
        errors = sorted(
            validator.iter_errors(candidate),
            key=lambda error: tuple(str(part) for part in error.path),
        )
        if errors:
            first = errors[0]
            location = ".".join(str(part) for part in first.path) or "root"
            raise CommandError(
                "P1-A Candidate Schema 검증에 실패했습니다: "
                f"path={location}"
            )
    return candidates


def _load_product_fixture(model_code: str) -> dict[str, Any]:
    rows = _load_json(PRODUCT_FIXTURE)
    matches = [row for row in rows if row.get("product_code") == model_code]
    if len(matches) != 1:
        raise CommandError(
            "승인 제품 Fixture에서 대상 모델을 하나로 결정할 수 없습니다."
        )
    return matches[0]


def _ensure_product(model_code: str) -> tuple[ProductModel, bool]:
    row = _load_product_fixture(model_code)
    expected = {
        "public_id": UUID(row["public_id"]),
        "model_name": row["product_model"],
        "generation_code": row["product_generation"],
        "features": {
            "model_family": row["model_family"],
            "manual_revision": row["manual_revision"],
            "support_scope": row["support_scope"],
            "data_classification": row["data_classification"],
        },
        "is_supported_mvp": row["support_scope"] == "MVP",
        "is_active": True,
    }
    product, created = ProductModel.objects.get_or_create(
        model_code=model_code,
        defaults=expected,
    )
    if not created:
        conflict_fields = [
            field
            for field, expected_value in expected.items()
            if getattr(product, field) != expected_value
        ]
        if conflict_fields:
            raise CommandError(
                "기존 제품 행이 승인 Fixture와 충돌합니다: "
                f"fields={','.join(sorted(conflict_fields))}"
            )
    product.full_clean()
    return product, created


def _ensure_customer(candidate: dict[str, Any]) -> tuple[CustomerProfile, bool]:
    customer_data = candidate["customer_candidate"]
    customer_no = customer_data["customer_code"]
    customer, created = CustomerProfile.objects.get_or_create(
        customer_no=customer_no,
        defaults={
            "user": None,
            "customer_name": customer_data["display_name"],
            "phone": "",
            "postal_code": "",
            "address_line1": "",
            "address_line2": "",
            "consent_version": "",
            "consented_at": None,
            "is_synthetic": True,
        },
    )
    expected = {
        "user_id": None,
        "customer_name": customer_data["display_name"],
        "is_synthetic": True,
        "deleted_at": None,
    }
    conflict_fields = [
        field
        for field, expected_value in expected.items()
        if getattr(customer, field) != expected_value
    ]
    if conflict_fields:
        raise CommandError(
            "기존 계약고객 행이 승인 Candidate와 충돌합니다: "
            f"fields={','.join(sorted(conflict_fields))}"
        )
    customer.full_clean()
    return customer, created


def _ensure_contact(
    candidate: dict[str, Any],
    customer: CustomerProfile,
    protection: ContractEmailProtectionService,
) -> tuple[ContractEmailContact, bool]:
    contact_data = candidate["contract_email"]
    normalized_email = normalize_synthetic_contract_email(
        contact_data["synthetic_address"]
    )
    protected = protection.protect(normalized_email)
    existing = ContractEmailContact.objects.filter(
        customer=customer,
        is_active=True,
        is_primary=True,
    ).first()
    if existing is not None:
        if (
            existing.email_lookup_hmac != protected.email_lookup_hmac
            or existing.key_version != protected.key_version
            or existing.delivery_policy != contact_data["delivery_policy"]
            or protection.decrypt(existing.encrypted_email)
            != normalized_email
        ):
            raise CommandError(
                "기존 계약 이메일 보호 행이 승인 Candidate와 충돌합니다."
            )
        existing.full_clean()
        return existing, False

    contact = ContractEmailContact(
        customer=customer,
        encrypted_email=protected.encrypted_email,
        email_lookup_hmac=protected.email_lookup_hmac,
        key_version=protected.key_version,
        is_active=contact_data["is_active"],
        is_primary=True,
        delivery_policy=contact_data["delivery_policy"],
        source_system="P1_ACCOUNT_LINK_FIXTURE",
        data_classification=candidate["data_classification"],
    )
    contact.full_clean()
    contact.save()
    return contact, True


def _ensure_subscription(
    candidate: dict[str, Any],
    customer: CustomerProfile,
    product: ProductModel,
) -> tuple[CustomerSubscription, bool]:
    subscription_data = candidate["subscription"]
    expected = {
        "customer_id": customer.pk,
        "product_model_id": product.pk,
        "serial_no": subscription_data["serial_no"],
        "management_type_code": subscription_data[
            "management_type_code"
        ],
        "status_code": subscription_data["status_code"],
        "started_on": date.fromisoformat(subscription_data["started_on"]),
        "ended_on": None,
        "next_care_on": date.fromisoformat(subscription_data["next_care_on"]),
    }
    subscription, created = CustomerSubscription.objects.get_or_create(
        contract_no=subscription_data["contract_no"],
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
    conflict_fields = [
        field
        for field, expected_value in expected.items()
        if getattr(subscription, field) != expected_value
    ]
    if conflict_fields:
        raise CommandError(
            "기존 구독 행이 승인 Candidate와 충돌합니다: "
            f"fields={','.join(sorted(conflict_fields))}"
        )
    subscription.full_clean()
    return subscription, created


class Command(BaseCommand):
    help = (
        "P1-A 승인 Candidate를 가입 전 계약고객·보호 이메일·활성 구독으로 "
        "멱등 적재합니다. User와 CustomerAccountLink는 생성하지 않습니다."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--candidate-file",
            type=Path,
            default=DEFAULT_CANDIDATE,
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--json", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        del args
        candidate_path = Path(options["candidate_file"]).resolve()
        candidates = _validate_candidates(candidate_path, DEFAULT_SCHEMA)
        try:
            protection = ContractEmailProtectionService.from_settings()
        except ContractEmailProtectionError as exc:
            raise CommandError(str(exc)) from exc

        counts = {
            "products_created": 0,
            "customers_created": 0,
            "contacts_created": 0,
            "subscriptions_created": 0,
        }
        fixture_ids: list[str] = []
        for candidate in candidates:
            fixture_ids.append(candidate["fixture_id"])
            product, product_created = _ensure_product(
                candidate["subscription"]["product_model_code"]
            )
            customer, customer_created = _ensure_customer(candidate)
            _, contact_created = _ensure_contact(
                candidate,
                customer,
                protection,
            )
            _, subscription_created = _ensure_subscription(
                candidate,
                customer,
                product,
            )
            if User.objects.filter(username=customer.customer_no).exists():
                raise CommandError(
                    "P1-A 가입 전 Candidate에 User가 존재합니다."
                )
            if CustomerAccountLink.objects.filter(customer=customer).exists():
                raise CommandError(
                    "P1-A 가입 전 Candidate에 CustomerAccountLink가 존재합니다."
                )

            counts["products_created"] += int(product_created)
            counts["customers_created"] += int(customer_created)
            counts["contacts_created"] += int(contact_created)
            counts["subscriptions_created"] += int(subscription_created)

        status = "DRY_RUN_READY" if options["dry_run"] else "APPLIED"
        result = {
            "status": status,
            "fixture_ids": fixture_ids,
            **counts,
            "candidate_customers": len(candidates),
            "candidate_active_contracts": len(candidates),
            "candidate_active_contacts": len(candidates),
            "candidate_active_subscriptions": len(candidates),
            "candidate_users": 0,
            "candidate_account_links": 0,
            "plaintext_email_stored": False,
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
                    "P1-A account-link fixture ready "
                    f"(status={status}, candidates={len(candidates)}, "
                    "users=0, links=0)"
                )
            )
