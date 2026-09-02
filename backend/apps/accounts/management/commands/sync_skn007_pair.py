"""Guarded AWS NONPROD synchronization for the approved SKN-007 pair."""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.accounts.credential_policy import validate_consultant_password
from apps.accounts.models import (
    ContractEmailContact,
    CustomerAccountLink,
    CustomerProfile,
    User,
)
from apps.accounts.services.contract_email_protection import (
    ContractEmailProtectionError,
    ContractEmailProtectionService,
    ProtectedContractEmail,
    normalize_contract_email,
)
from apps.inquiries.p1_team_routing import P1TeamConsultantRouting
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


SyncMode = Literal["plan", "dry-run", "apply"]
CONSULTANT_USERNAME = "SKN-007"
CONSULTANT_EMPLOYEE_NO = "SKN-EMP-CNS-007"
CUSTOMER_NO = "SYN-P1-EXTRA-CUSTOMER-001"
CONTRACT_NO = "SYN-P1-EXTRA-CONTRACT-001"
SERIAL_NO = "SYN-P1-EXTRA-JAC104D-001"
PRODUCT_MODEL_CODE = "WPUJAC104DWH"
SOURCE_SYSTEM = "PM_APPROVED_AWS_NONPROD_20260901"
PASSWORD_ENVIRONMENT_VARIABLE = "P1_TEAM_CONSULTANT_PASSWORD"
PHONE_PATTERN = re.compile(r"^010-[0-9]{4}-[0-9]{4}$")
INPUT_FIELDS = frozenset(
    {
        "customer_name",
        "customer_phone",
        "customer_email",
        "consultant_full_name",
    }
)


@dataclass(frozen=True)
class ApprovedPairInput:
    """Sensitive input that is never included in command output."""

    customer_name: str
    customer_phone: str
    customer_email: str
    consultant_full_name: str


@dataclass(frozen=True)
class ApprovedPairSyncResult:
    """Non-sensitive evidence for one exact pair."""

    mode: SyncMode
    consultant_username: str
    customer_no: str
    contract_no: str
    consultant_action: str
    customer_action: str
    contact_action: str
    subscription_action: str
    password_usable: bool
    customer_user_count: int
    account_link_count: int
    plaintext_email_stored: bool
    exact_route_verified: bool


def _load_input(path: Path) -> ApprovedPairInput:
    resolved = path.resolve()
    if not resolved.is_file():
        raise CommandError("승인 입력 파일을 찾을 수 없습니다.")
    if resolved.stat().st_size > 4096:
        raise CommandError("승인 입력 파일 크기가 허용 범위를 초과합니다.")
    if os.name != "nt" and stat.S_IMODE(resolved.stat().st_mode) & 0o077:
        raise CommandError("승인 입력 파일 권한은 0600이어야 합니다.")
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CommandError("승인 입력 파일을 읽을 수 없습니다.") from exc
    if not isinstance(document, dict) or set(document) != INPUT_FIELDS:
        raise CommandError("승인 입력 필드를 확인해 주세요.")

    values = {
        key: str(document[key]).strip()
        for key in INPUT_FIELDS
    }
    if not values["customer_name"] or len(values["customer_name"]) > 100:
        raise CommandError("승인 고객 이름 형식을 확인해 주세요.")
    if not PHONE_PATTERN.fullmatch(values["customer_phone"]):
        raise CommandError("승인 고객 전화번호 형식을 확인해 주세요.")
    if (
        not values["consultant_full_name"]
        or len(values["consultant_full_name"]) > 100
    ):
        raise CommandError("승인 상담사 이름 형식을 확인해 주세요.")
    try:
        values["customer_email"] = normalize_contract_email(
            values["customer_email"]
        )
    except ContractEmailProtectionError as exc:
        raise CommandError("승인 고객 이메일 형식을 확인해 주세요.") from exc
    if values["customer_email"].rsplit("@", 1)[-1].endswith(".invalid"):
        raise CommandError("승인 고객 이메일은 실제 수신 주소여야 합니다.")
    return ApprovedPairInput(**values)


def _load_password() -> str:
    password = os.getenv(PASSWORD_ENVIRONMENT_VARIABLE, "")
    try:
        validate_consultant_password(password)
    except ValidationError as exc:
        raise CommandError(
            "상담사 비밀번호 보호 입력을 확인해 주세요."
        ) from exc
    return password


class Command(BaseCommand):
    """Synchronize only SKN-007 and its approved synthetic customer pair."""

    help = (
        "PM 승인 AWS NONPROD SKN-007 상담사와 계약고객 1건을 "
        "plan, dry-run 또는 멱등 apply합니다."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--input-file", type=Path, required=True)
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--apply", action="store_true")
        parser.add_argument("--expected-database")
        parser.add_argument("--expected-host")
        parser.add_argument("--pm-approved-aws-nonprod", action="store_true")

    def handle(self, *args: Any, **options: Any) -> str:
        del args
        mode: SyncMode = (
            "apply"
            if options["apply"]
            else "dry-run" if options["dry_run"] else "plan"
        )
        if mode == "apply":
            self._verify_apply_target(
                expected_database=options["expected_database"],
                expected_host=options["expected_host"],
                pm_approved=options["pm_approved_aws_nonprod"],
            )
        approved = _load_input(options["input_file"])
        password = _load_password()
        try:
            result = self._run(
                mode=mode,
                approved=approved,
                password=password,
            )
        except ContractEmailProtectionError as exc:
            raise CommandError("계약 이메일 보호 설정을 확인해 주세요.") from exc
        return json.dumps(
            asdict(result),
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def _verify_apply_target(
        *,
        expected_database: str | None,
        expected_host: str | None,
        pm_approved: bool,
    ) -> None:
        if not pm_approved:
            raise CommandError("--apply에는 PM 승인 표시가 필요합니다.")
        if settings.DEBUG:
            raise CommandError("AWS NONPROD apply는 DEBUG=False여야 합니다.")
        if settings.P1_AUTH_RUNTIME_ENVIRONMENT != "AWS_NONPROD":
            raise CommandError("AWS NONPROD Runtime에서만 apply할 수 있습니다.")
        if connection.vendor != "postgresql":
            raise CommandError("PostgreSQL 연결에서만 apply할 수 있습니다.")
        if not expected_database or not expected_host:
            raise CommandError(
                "--apply에는 --expected-database와 --expected-host가 필요합니다."
            )
        if str(connection.settings_dict["NAME"]) != expected_database:
            raise CommandError("대상 데이터베이스가 일치하지 않습니다.")
        configured_host = str(connection.settings_dict["HOST"] or "localhost")
        if configured_host != expected_host:
            raise CommandError("대상 데이터베이스 Host가 일치하지 않습니다.")

    @transaction.atomic
    def _run(
        self,
        *,
        mode: SyncMode,
        approved: ApprovedPairInput,
        password: str,
    ) -> ApprovedPairSyncResult:
        if not P1TeamConsultantRouting.is_exact_reserved_pair(
            actor=SimpleNamespace(username=CONSULTANT_USERNAME),
            contract_no=CONTRACT_NO,
        ):
            raise CommandError("SKN-007 계약 라우팅이 배포 소스와 일치하지 않습니다.")

        protection = ContractEmailProtectionService.from_settings()
        protected = protection.protect_approved_test(approved.customer_email)
        product = ProductModel.objects.filter(
            model_code=PRODUCT_MODEL_CODE,
            is_active=True,
            is_supported_mvp=True,
        ).first()
        if product is None:
            raise CommandError("승인 제품 모델을 찾을 수 없습니다.")

        consultant = User.objects.select_for_update().filter(
            username__iexact=CONSULTANT_USERNAME
        ).first()
        customer = CustomerProfile.objects.select_for_update().filter(
            customer_no=CUSTOMER_NO
        ).first()
        subscription = CustomerSubscription.objects.select_for_update().filter(
            contract_no=CONTRACT_NO
        ).first()
        contact = None
        if customer is not None:
            contact = ContractEmailContact.objects.select_for_update().filter(
                customer=customer,
                is_active=True,
                is_primary=True,
            ).first()

        self._assert_no_identity_collisions(
            consultant=consultant,
            customer=customer,
            protected_hmac=protected.email_lookup_hmac,
            approved=approved,
        )
        consultant_action = self._consultant_action(
            consultant=consultant,
            approved=approved,
            password=password,
        )
        customer_action = self._customer_action(
            customer=customer,
            approved=approved,
        )
        contact_action = self._contact_action(
            contact=contact,
            customer=customer,
            protected=protected,
            approved=approved,
            protection=protection,
        )
        subscription_action = self._subscription_action(
            subscription=subscription,
            customer=customer,
            product=product,
        )

        if mode != "plan":
            consultant = consultant or User.objects.create_user(
                username=CONSULTANT_USERNAME,
                password=password,
                full_name=approved.consultant_full_name,
                email="",
                phone="",
                role_code=User.Role.CONSULTANT,
                employee_no=CONSULTANT_EMPLOYEE_NO,
                is_active=True,
                is_staff=False,
                is_superuser=False,
                is_synthetic=True,
            )
            customer = customer or self._create_customer(approved)
            contact = contact or self._create_contact(
                customer=customer,
                protected=protected,
            )
            subscription = subscription or self._create_subscription(
                customer=customer,
                product=product,
            )
            self._verify_persisted(
                consultant=consultant,
                customer=customer,
                contact=contact,
                subscription=subscription,
                approved=approved,
                password=password,
                protection=protection,
            )
            if mode == "apply":
                consultant_action = self._applied_action(consultant_action)
                customer_action = self._applied_action(customer_action)
                contact_action = self._applied_action(contact_action)
                subscription_action = self._applied_action(
                    subscription_action
                )
        customer_user_count = int(customer is not None and customer.user_id is not None)
        account_link_count = (
            CustomerAccountLink.objects.filter(customer=customer).count()
            if customer is not None
            else 0
        )
        result = ApprovedPairSyncResult(
            mode=mode,
            consultant_username=CONSULTANT_USERNAME,
            customer_no=CUSTOMER_NO,
            contract_no=CONTRACT_NO,
            consultant_action=consultant_action,
            customer_action=customer_action,
            contact_action=contact_action,
            subscription_action=subscription_action,
            password_usable=(
                consultant.check_password(password)
                if consultant is not None
                else True
            ),
            customer_user_count=customer_user_count,
            account_link_count=account_link_count,
            plaintext_email_stored=False,
            exact_route_verified=True,
        )
        if mode == "dry-run":
            transaction.set_rollback(True)
        return result

    @staticmethod
    def _applied_action(planned_action: str) -> str:
        return "CREATED" if planned_action == "WOULD_CREATE" else planned_action

    @staticmethod
    def _assert_no_identity_collisions(
        *,
        consultant: User | None,
        customer: CustomerProfile | None,
        protected_hmac: str,
        approved: ApprovedPairInput,
    ) -> None:
        employee_collision = User.objects.filter(
            employee_no=CONSULTANT_EMPLOYEE_NO
        ).exclude(pk=getattr(consultant, "pk", None)).exists()
        if employee_collision:
            raise CommandError("상담사 사번이 다른 계정과 충돌합니다.")
        phone_collision = CustomerProfile.objects.filter(
            phone=approved.customer_phone,
            deleted_at__isnull=True,
        ).exclude(pk=getattr(customer, "pk", None)).exists()
        if phone_collision:
            raise CommandError("고객 전화번호가 다른 고객과 충돌합니다.")
        email_collision = ContractEmailContact.objects.filter(
            email_lookup_hmac=protected_hmac,
            is_active=True,
        ).exclude(customer_id=getattr(customer, "pk", None)).exists()
        if email_collision:
            raise CommandError("계약 이메일이 다른 고객과 충돌합니다.")
        serial_collision = CustomerSubscription.objects.filter(
            serial_no=SERIAL_NO,
            status_code__in=[
                CustomerSubscription.Status.ACTIVE,
                CustomerSubscription.Status.SUSPENDED,
            ],
        ).exclude(contract_no=CONTRACT_NO).exists()
        if serial_collision:
            raise CommandError("제품 일련번호가 다른 활성 계약과 충돌합니다.")

    @staticmethod
    def _consultant_action(
        *,
        consultant: User | None,
        approved: ApprovedPairInput,
        password: str,
    ) -> str:
        if consultant is None:
            return "WOULD_CREATE"
        expected = {
            "full_name": approved.consultant_full_name,
            "email": "",
            "phone": "",
            "role_code": User.Role.CONSULTANT,
            "employee_no": CONSULTANT_EMPLOYEE_NO,
            "is_active": True,
            "is_staff": False,
            "is_superuser": False,
            "is_synthetic": True,
        }
        conflicts = sorted(
            field
            for field, value in expected.items()
            if getattr(consultant, field) != value
        )
        if conflicts or not consultant.check_password(password):
            raise CommandError("기존 SKN-007 계정이 승인 입력과 충돌합니다.")
        consultant.full_clean()
        return "UNCHANGED"

    @staticmethod
    def _customer_action(
        *,
        customer: CustomerProfile | None,
        approved: ApprovedPairInput,
    ) -> str:
        if customer is None:
            return "WOULD_CREATE"
        expected = {
            "user_id": None,
            "customer_name": approved.customer_name,
            "phone": approved.customer_phone,
            "postal_code": "",
            "address_line1": "",
            "address_line2": "",
            "consent_version": "",
            "consented_at": None,
            "is_synthetic": True,
            "deleted_at": None,
        }
        if any(getattr(customer, field) != value for field, value in expected.items()):
            raise CommandError("기존 고객 행이 승인 입력과 충돌합니다.")
        if CustomerAccountLink.objects.filter(customer=customer).exists():
            raise CommandError("승인 고객은 가입 전 상태여야 합니다.")
        customer.full_clean()
        return "UNCHANGED"

    @staticmethod
    def _contact_action(
        *,
        contact: ContractEmailContact | None,
        customer: CustomerProfile | None,
        protected: ProtectedContractEmail,
        approved: ApprovedPairInput,
        protection: ContractEmailProtectionService,
    ) -> str:
        del customer
        if contact is None:
            return "WOULD_CREATE"
        valid = (
            contact.email_lookup_hmac == protected.email_lookup_hmac
            and contact.key_version == protected.key_version
            and contact.is_active
            and contact.is_primary
            and contact.delivery_policy
            == ContractEmailContact.DeliveryPolicy.APPROVED_TEST_RECIPIENT
            and contact.data_classification
            == ContractEmailContact.DataClassification.APPROVED_TEST_PII
            and contact.source_system == SOURCE_SYSTEM
            and protection.decrypt(contact.encrypted_email)
            == approved.customer_email
        )
        if not valid:
            raise CommandError("기존 계약 이메일 행이 승인 입력과 충돌합니다.")
        contact.full_clean()
        return "UNCHANGED"

    @staticmethod
    def _subscription_action(
        *,
        subscription: CustomerSubscription | None,
        customer: CustomerProfile | None,
        product: ProductModel,
    ) -> str:
        if subscription is None:
            return "WOULD_CREATE"
        expected = {
            "customer_id": getattr(customer, "pk", None),
            "product_model_id": product.pk,
            "serial_no": SERIAL_NO,
            "management_type_code": CustomerSubscription.ManagementType.VISIT_CARE,
            "status_code": CustomerSubscription.Status.ACTIVE,
            "started_on": date(2026, 9, 1),
            "ended_on": None,
            "next_care_on": date(2026, 10, 1),
        }
        if any(
            getattr(subscription, field) != value
            for field, value in expected.items()
        ):
            raise CommandError("기존 계약 행이 승인 입력과 충돌합니다.")
        subscription.full_clean()
        return "UNCHANGED"

    @staticmethod
    def _create_customer(approved: ApprovedPairInput) -> CustomerProfile:
        customer = CustomerProfile(
            user=None,
            customer_no=CUSTOMER_NO,
            customer_name=approved.customer_name,
            phone=approved.customer_phone,
            postal_code="",
            address_line1="",
            address_line2="",
            consent_version="",
            consented_at=None,
            is_synthetic=True,
        )
        customer.full_clean()
        customer.save()
        return customer

    @staticmethod
    def _create_contact(
        *,
        customer: CustomerProfile,
        protected: ProtectedContractEmail,
    ) -> ContractEmailContact:
        contact = ContractEmailContact(
            customer=customer,
            encrypted_email=protected.encrypted_email,
            email_lookup_hmac=protected.email_lookup_hmac,
            key_version=protected.key_version,
            is_active=True,
            is_primary=True,
            delivery_policy=ContractEmailContact.DeliveryPolicy.APPROVED_TEST_RECIPIENT,
            source_system=SOURCE_SYSTEM,
            data_classification=(
                ContractEmailContact.DataClassification.APPROVED_TEST_PII
            ),
        )
        contact.full_clean()
        contact.save()
        return contact

    @staticmethod
    def _create_subscription(
        *,
        customer: CustomerProfile,
        product: ProductModel,
    ) -> CustomerSubscription:
        subscription = CustomerSubscription(
            contract_no=CONTRACT_NO,
            customer=customer,
            product_model=product,
            serial_no=SERIAL_NO,
            management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
            status_code=CustomerSubscription.Status.ACTIVE,
            started_on=date(2026, 9, 1),
            ended_on=None,
            installed_at=None,
            installed_on=None,
            source_customer_product_public_id=None,
            installation_address=None,
            next_care_on=date(2026, 10, 1),
        )
        subscription.full_clean()
        subscription.save()
        return subscription

    @staticmethod
    def _verify_persisted(
        *,
        consultant: User,
        customer: CustomerProfile,
        contact: ContractEmailContact,
        subscription: CustomerSubscription,
        approved: ApprovedPairInput,
        password: str,
        protection: ContractEmailProtectionService,
    ) -> None:
        if (
            consultant.username != CONSULTANT_USERNAME
            or not consultant.check_password(password)
            or customer.customer_no != CUSTOMER_NO
            or customer.user_id is not None
            or CustomerAccountLink.objects.filter(customer=customer).exists()
            or contact.customer_id != customer.pk
            or protection.decrypt(contact.encrypted_email)
            != approved.customer_email
            or subscription.customer_id != customer.pk
            or subscription.contract_no != CONTRACT_NO
        ):
            raise CommandError("SKN-007 승인 Pair 저장 검증에 실패했습니다.")
