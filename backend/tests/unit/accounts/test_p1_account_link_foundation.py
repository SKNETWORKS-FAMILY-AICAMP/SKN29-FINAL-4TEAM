"""P1-A 가입 전 계약고객·계정 연결·이메일 보호 기반 검증."""

from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import override_settings

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


pytestmark = pytest.mark.django_db

SYNTHETIC_EMAIL = "customer-p1-001@waterbridge.invalid"


def _protection_service() -> ContractEmailProtectionService:
    return ContractEmailProtectionService(
        encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        hmac_key="AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=",
        key_version="test-v1",
    )


def _customer_user(sequence: int) -> tuple[User, CustomerProfile]:
    user = User.objects.create_user(
        username=f"SYN-P1-USER-{sequence:03d}",
        full_name=f"Synthetic P1 user {sequence}",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    profile = CustomerProfile.objects.create(
        user=user,
        customer_no=f"SYN-P1-CUSTOMER-{sequence:03d}",
        customer_name=f"Synthetic P1 customer {sequence}",
        is_synthetic=True,
    )
    return user, profile


def test_pre_signup_customer_can_exist_without_user():
    profile = CustomerProfile(
        user=None,
        customer_no="SYN-PRE-SIGNUP-001",
        customer_name="Synthetic pre-signup customer",
        is_synthetic=True,
    )

    profile.full_clean()
    profile.save()

    assert profile.user_id is None
    assert not CustomerAccountLink.objects.filter(customer=profile).exists()


def test_contract_email_is_encrypted_and_hmac_is_deterministic():
    service = _protection_service()

    first = service.protect(f"  {SYNTHETIC_EMAIL.upper()}  ")
    second = service.protect(SYNTHETIC_EMAIL)

    assert first.email_lookup_hmac == second.email_lookup_hmac
    assert first.encrypted_email != second.encrypted_email
    assert SYNTHETIC_EMAIL not in first.encrypted_email
    assert service.decrypt(first.encrypted_email) == SYNTHETIC_EMAIL
    assert service.matches(SYNTHETIC_EMAIL, first.email_lookup_hmac)


def test_contract_email_protection_rejects_real_or_invalid_addresses():
    for address in ("person@example.com", "not-an-email"):
        with pytest.raises(ContractEmailProtectionError):
            normalize_synthetic_contract_email(address)


def test_contract_email_model_rejects_plaintext_storage():
    customer = CustomerProfile.objects.create(
        user=None,
        customer_no="SYN-PRE-SIGNUP-002",
        customer_name="Synthetic pre-signup customer 2",
        is_synthetic=True,
    )
    contact = ContractEmailContact(
        customer=customer,
        encrypted_email=SYNTHETIC_EMAIL,
        email_lookup_hmac="a" * 64,
        key_version="test-v1",
        is_active=True,
        is_primary=True,
    )

    with pytest.raises(ValidationError):
        contact.full_clean()


def test_active_account_link_is_unique_for_user_and_customer():
    first_user, first_customer = _customer_user(1)
    second_user, second_customer = _customer_user(2)
    CustomerAccountLink.objects.create(
        user=first_user,
        customer=first_customer,
        is_active=True,
        link_reason=CustomerAccountLink.LinkReason.SIGN_UP_EMAIL_OTP,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CustomerAccountLink.objects.create(
                user=first_user,
                customer=second_customer,
                is_active=True,
                link_reason=(
                    CustomerAccountLink.LinkReason.SIGN_UP_EMAIL_OTP
                ),
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CustomerAccountLink.objects.create(
                user=second_user,
                customer=first_customer,
                is_active=True,
                link_reason=(
                    CustomerAccountLink.LinkReason.SIGN_UP_EMAIL_OTP
                ),
            )


def test_p1_fixture_seed_creates_pre_signup_rows_and_replays_without_change():
    first_stdout = StringIO()
    call_command("seed_p1_account_link_fixture", "--json", stdout=first_stdout)
    first_result = json.loads(first_stdout.getvalue())
    customer = CustomerProfile.objects.get(
        customer_no="SYN-CUSTOMER-P1-001"
    )
    contact = ContractEmailContact.objects.get(customer=customer)
    subscription = CustomerSubscription.objects.get(
        contract_no="SYN-CONTRACT-P1-001"
    )
    first_identity = {
        "customer": (customer.pk, customer.public_id, customer.updated_at),
        "contact": (
            contact.pk,
            contact.public_id,
            contact.encrypted_email,
            contact.updated_at,
        ),
        "subscription": (
            subscription.pk,
            subscription.public_id,
            subscription.updated_at,
        ),
    }

    second_stdout = StringIO()
    call_command("seed_p1_account_link_fixture", "--json", stdout=second_stdout)
    second_result = json.loads(second_stdout.getvalue())
    customer.refresh_from_db()
    contact.refresh_from_db()
    subscription.refresh_from_db()

    assert first_result["status"] == "APPLIED"
    assert first_result["candidate_users"] == 0
    assert first_result["candidate_account_links"] == 0
    assert second_result["customers_created"] == 0
    assert second_result["contacts_created"] == 0
    assert second_result["subscriptions_created"] == 0
    assert CustomerProfile.objects.count() == 1
    assert ContractEmailContact.objects.count() == 1
    assert CustomerSubscription.objects.count() == 1
    assert ProductModel.objects.count() == 1
    assert User.objects.count() == 0
    assert CustomerAccountLink.objects.count() == 0
    assert customer.user_id is None
    assert contact.encrypted_email != SYNTHETIC_EMAIL
    assert SYNTHETIC_EMAIL not in contact.encrypted_email
    assert subscription.status_code == CustomerSubscription.Status.ACTIVE
    assert subscription.product_model.model_code == "WPUJAC104DWH"
    assert {
        "customer": (customer.pk, customer.public_id, customer.updated_at),
        "contact": (
            contact.pk,
            contact.public_id,
            contact.encrypted_email,
            contact.updated_at,
        ),
        "subscription": (
            subscription.pk,
            subscription.public_id,
            subscription.updated_at,
        ),
    } == first_identity


def test_p1_fixture_dry_run_leaves_database_unchanged():
    stdout = StringIO()

    call_command(
        "seed_p1_account_link_fixture",
        "--dry-run",
        "--json",
        stdout=stdout,
    )

    assert json.loads(stdout.getvalue())["status"] == "DRY_RUN_READY"
    assert CustomerProfile.objects.count() == 0
    assert ContractEmailContact.objects.count() == 0
    assert CustomerSubscription.objects.count() == 0
    assert ProductModel.objects.count() == 0
    assert User.objects.count() == 0
    assert CustomerAccountLink.objects.count() == 0


@override_settings(
    CONTRACT_EMAIL_ENCRYPTION_KEY="",
    CONTRACT_EMAIL_HMAC_KEY="",
    CONTRACT_EMAIL_KEY_VERSION="",
)
def test_p1_fixture_seed_fails_closed_without_protection_keys():
    with pytest.raises(CommandError):
        call_command("seed_p1_account_link_fixture", "--json")

    assert CustomerProfile.objects.count() == 0
    assert ContractEmailContact.objects.count() == 0
    assert CustomerSubscription.objects.count() == 0


def test_p1_fixture_seed_rejects_precreated_user_and_rolls_back():
    User.objects.create_user(
        username="SYN-CUSTOMER-P1-001",
        full_name="Conflicting synthetic account",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )

    with pytest.raises(CommandError, match="User"):
        call_command("seed_p1_account_link_fixture", "--json")

    assert User.objects.count() == 1
    assert CustomerProfile.objects.count() == 0
    assert ContractEmailContact.objects.count() == 0
    assert CustomerSubscription.objects.count() == 0
    assert ProductModel.objects.count() == 0
