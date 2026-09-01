"""Guarded synchronization tests for the approved SKN-007 pair."""

from __future__ import annotations

import json
import os
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.accounts.management.commands.sync_skn007_pair import Command
from apps.accounts.models import (
    ContractEmailContact,
    CustomerAccountLink,
    CustomerProfile,
    User,
)
from apps.accounts.services.contract_email_protection import (
    ContractEmailProtectionService,
)
from apps.inquiries.p1_team_routing import P1TeamConsultantRouting
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db

TEST_PASSWORD = "StrongSKN007PasswordForTest2026"
TEST_INPUT = {
    "customer_name": "Synthetic Approved Customer 007",
    "customer_phone": "010-7000-0007",
    "customer_email": "approved-skn007@example.com",
    "consultant_full_name": "Synthetic Consultant 007",
}


@pytest.fixture
def approved_input_path(tmp_path):
    path = tmp_path / "skn007-approved-pair.json"
    path.write_text(
        json.dumps(TEST_INPUT, ensure_ascii=False),
        encoding="utf-8",
    )
    if os.name != "nt":
        path.chmod(0o600)
    return path


@pytest.fixture
def approved_product():
    return ProductModel.objects.create(
        model_code="WPUJAC104DWH",
        model_name="Synthetic approved model",
        manufacturer="SK매직",
        features={},
        is_supported_mvp=True,
        is_active=True,
    )


def _run_apply(path, monkeypatch) -> dict:
    monkeypatch.setenv("P1_TEAM_CONSULTANT_PASSWORD", TEST_PASSWORD)
    stdout = StringIO()
    with patch.object(Command, "_verify_apply_target", return_value=None):
        call_command(
            "sync_skn007_pair",
            "--input-file",
            str(path),
            "--apply",
            stdout=stdout,
        )
    return json.loads(stdout.getvalue())


def test_plan_and_dry_run_do_not_persist_sensitive_pair(
    approved_input_path,
    approved_product,
    monkeypatch,
):
    del approved_product
    monkeypatch.setenv("P1_TEAM_CONSULTANT_PASSWORD", TEST_PASSWORD)

    plan_stdout = StringIO()
    call_command(
        "sync_skn007_pair",
        "--input-file",
        str(approved_input_path),
        stdout=plan_stdout,
    )
    dry_run_stdout = StringIO()
    call_command(
        "sync_skn007_pair",
        "--input-file",
        str(approved_input_path),
        "--dry-run",
        stdout=dry_run_stdout,
    )

    for payload in (
        json.loads(plan_stdout.getvalue()),
        json.loads(dry_run_stdout.getvalue()),
    ):
        assert payload["consultant_action"] == "WOULD_CREATE"
        assert payload["customer_action"] == "WOULD_CREATE"
        assert payload["contact_action"] == "WOULD_CREATE"
        assert payload["subscription_action"] == "WOULD_CREATE"
        serialized = json.dumps(payload, ensure_ascii=False)
        for secret in (*TEST_INPUT.values(), TEST_PASSWORD):
            assert secret not in serialized

    assert not User.objects.filter(username="SKN-007").exists()
    assert not CustomerProfile.objects.filter(
        customer_no="SYN-P1-EXTRA-CUSTOMER-001"
    ).exists()
    assert not CustomerSubscription.objects.filter(
        contract_no="SYN-P1-EXTRA-CONTRACT-001"
    ).exists()


def test_apply_creates_exact_pair_and_replay_is_unchanged(
    approved_input_path,
    approved_product,
    monkeypatch,
):
    del approved_product

    first = _run_apply(approved_input_path, monkeypatch)
    second = _run_apply(approved_input_path, monkeypatch)

    assert first["mode"] == "apply"
    assert first["consultant_action"] == "CREATED"
    assert first["customer_action"] == "CREATED"
    assert first["contact_action"] == "CREATED"
    assert first["subscription_action"] == "CREATED"
    assert first["customer_user_count"] == 0
    assert first["account_link_count"] == 0
    assert first["plaintext_email_stored"] is False
    assert first["exact_route_verified"] is True
    assert second["consultant_action"] == "UNCHANGED"
    assert second["customer_action"] == "UNCHANGED"
    assert second["contact_action"] == "UNCHANGED"
    assert second["subscription_action"] == "UNCHANGED"

    consultant = User.objects.get(username="SKN-007")
    customer = CustomerProfile.objects.get(
        customer_no="SYN-P1-EXTRA-CUSTOMER-001"
    )
    contact = ContractEmailContact.objects.get(customer=customer)
    subscription = CustomerSubscription.objects.get(
        contract_no="SYN-P1-EXTRA-CONTRACT-001"
    )
    protection = ContractEmailProtectionService.from_settings()

    assert consultant.full_name == TEST_INPUT["consultant_full_name"]
    assert consultant.check_password(TEST_PASSWORD)
    assert consultant.role_code == User.Role.CONSULTANT
    assert consultant.is_synthetic is True
    assert customer.user_id is None
    assert customer.customer_name == TEST_INPUT["customer_name"]
    assert customer.phone == TEST_INPUT["customer_phone"]
    assert CustomerAccountLink.objects.filter(customer=customer).count() == 0
    assert TEST_INPUT["customer_email"] not in contact.encrypted_email
    assert protection.decrypt(contact.encrypted_email) == (
        TEST_INPUT["customer_email"]
    )
    assert subscription.customer_id == customer.pk
    assert subscription.status_code == CustomerSubscription.Status.ACTIVE
    assert P1TeamConsultantRouting.is_exact_reserved_pair(
        actor=consultant,
        contract_no=subscription.contract_no,
    )
    assert not P1TeamConsultantRouting.can_access_contract(
        actor=SimpleNamespace(username="SKN-001"),
        contract_no=subscription.contract_no,
    )


def test_apply_fails_closed_on_existing_phone_collision(
    approved_input_path,
    approved_product,
    monkeypatch,
):
    del approved_product
    CustomerProfile.objects.create(
        user=None,
        customer_no="SYN-OTHER-CUSTOMER-001",
        customer_name="Other synthetic customer",
        phone=TEST_INPUT["customer_phone"],
        is_synthetic=True,
    )

    with pytest.raises(CommandError, match="전화번호"):
        _run_apply(approved_input_path, monkeypatch)

    assert not User.objects.filter(username="SKN-007").exists()
    assert not CustomerProfile.objects.filter(
        customer_no="SYN-P1-EXTRA-CUSTOMER-001"
    ).exists()


@override_settings(
    DEBUG=False,
    P1_AUTH_RUNTIME_ENVIRONMENT="AWS_NONPROD",
)
def test_real_apply_guard_rejects_non_postgresql_target(
    approved_input_path,
    approved_product,
    monkeypatch,
):
    del approved_product
    monkeypatch.setenv("P1_TEAM_CONSULTANT_PASSWORD", TEST_PASSWORD)

    with pytest.raises(CommandError, match="PostgreSQL"):
        call_command(
            "sync_skn007_pair",
            "--input-file",
            str(approved_input_path),
            "--apply",
            "--pm-approved-aws-nonprod",
            "--expected-database",
            "test-db",
            "--expected-host",
            "test-host",
        )
