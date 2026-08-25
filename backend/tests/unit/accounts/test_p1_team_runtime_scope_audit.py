"""Read-only P1 team runtime scope audit tests."""

from __future__ import annotations

import json
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command

from apps.accounts.models import (
    ContractEmailContact,
    CustomerAccountLink,
    CustomerProfile,
    User,
)
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db


def _seed_ready_baseline() -> tuple[list[CustomerProfile], User]:
    product = ProductModel.objects.create(
        model_code="WPUJAC104DWH",
        model_name="초소형 직수 정수기",
        is_supported_mvp=True,
        is_active=True,
    )
    customers = []
    for index in range(1, 7):
        customer = CustomerProfile.objects.create(
            customer_no=f"SYN-P1-TEAM-CUSTOMER-{index:03d}",
            customer_name=f"P1 합성 고객 {index}",
            phone=f"010-9000-{index:04d}",
            is_synthetic=True,
        )
        ContractEmailContact.objects.create(
            customer=customer,
            encrypted_email=f"ciphertext-{index}",
            email_lookup_hmac=f"{index:064x}",
            key_version="test-v1",
            is_active=True,
            is_primary=True,
            delivery_policy=(
                ContractEmailContact.DeliveryPolicy.APPROVED_TEST_RECIPIENT
            ),
            source_system="PM_APPROVED_LOCAL_E2E_20260825",
            data_classification=(
                ContractEmailContact.DataClassification.APPROVED_TEST_PII
            ),
        )
        CustomerSubscription.objects.create(
            contract_no=f"SYN-P1-TEAM-CONTRACT-{index:03d}",
            customer=customer,
            product_model=product,
            serial_no=f"SYN-P1-TEAM-JAC104D-{index:03d}",
            management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
            status_code=CustomerSubscription.Status.ACTIVE,
            started_on=date(2026, 8, 25),
        )
        customers.append(customer)
    consultant = User.objects.create_user(
        username="DEMO-CONSULTANT-001",
        full_name="합성 상담사 001",
        role_code=User.Role.CONSULTANT,
        employee_no="DEMO-EMP-CNS-001",
        is_active=True,
        is_synthetic=True,
    )
    return customers, consultant


def test_scope_audit_reports_candidates_without_deleting_rows():
    for index in range(1, 7):
        CustomerProfile.objects.create(
            customer_no=f"SYN-P1-TEAM-CUSTOMER-{index:03d}",
            customer_name=f"P1 합성 고객 {index}",
            phone=f"010-9000-{index:04d}",
            is_synthetic=True,
        )
    CustomerProfile.objects.create(
        customer_no="OLD-SYNTHETIC-CUSTOMER-001",
        customer_name="기존 합성 고객",
        phone="010-8000-0001",
        is_synthetic=True,
    )
    User.objects.create_user(
        username="SYN-CONSULTANT-AUDIT-001",
        full_name="합성 상담사",
        role_code=User.Role.CONSULTANT,
        employee_no="SYN-EMP-CNS-AUDIT-001",
        is_synthetic=True,
    )
    before_customers = CustomerProfile.objects.count()
    before_users = User.objects.count()
    stdout = StringIO()

    call_command("audit_p1_team_runtime_scope", "--json", stdout=stdout)
    result = json.loads(stdout.getvalue())

    assert result["mode"] == "PLAN_ONLY_READ_ONLY"
    assert result["source_database_mutated"] is False
    assert result["preserve"]["customers"] == 6
    assert result["preserve"]["consultant_users"] == 1
    assert result["delete_candidates"]["customers"] == 1
    assert "P1_TEAM_ACTIVE_PRIMARY_CONTACT_NOT_6" in result["blockers"]
    assert "P1_TEAM_CONSULTANT_IDENTITY_NOT_EXACT_1" in result["blockers"]
    assert CustomerProfile.objects.count() == before_customers
    assert User.objects.count() == before_users


def test_baseline_requires_exact_six_rows_and_one_consultant_only():
    _seed_ready_baseline()
    stdout = StringIO()

    call_command("audit_p1_team_runtime_scope", "--json", stdout=stdout)
    result = json.loads(stdout.getvalue())

    assert result["mode"] == "PLAN_ONLY_READ_ONLY"
    assert result["runtime_phase"] == "BASELINE"
    assert result["preserve"]["customers"] == 6
    assert result["preserve"]["active_primary_contacts"] == 6
    assert result["preserve"]["active_subscriptions"] == 6
    assert result["preserve"]["consultant_users"] == 1
    assert result["preserve"]["user_role_counts"] == {
        "CONSULTANT": 1,
        "CUSTOMER": 0,
        "OPERATOR": 0,
        "TECHNICIAN": 0,
    }
    assert result["runtime"]["p1_owned_inquiries"] == 0
    assert result["runtime"]["non_p1_inquiries"] == 0
    assert result["blockers"] == []
    assert result["ready_for_isolated_rebuild"] is True


def test_operational_mode_allows_only_linked_p1_customer_and_owned_inquiry():
    customers, _ = _seed_ready_baseline()
    customer = customers[0]
    customer_user = User.objects.create_user(
        username="p1.mobile.customer.001",
        password="SafePassword123",
        full_name=customer.customer_name,
        role_code=User.Role.CUSTOMER,
        is_active=True,
        is_synthetic=True,
    )
    customer.user = customer_user
    customer.save(update_fields=["user", "updated_at"])
    CustomerAccountLink.objects.create(
        user=customer_user,
        customer=customer,
        link_reason=CustomerAccountLink.LinkReason.SIGN_UP_EMAIL_OTP,
    )
    Inquiry.objects.create(
        subscription=customer.subscriptions.get(),
        initiated_by=customer_user,
        channel_code=Inquiry.Channel.MOBILE,
        raw_text="P1 합성 고객의 신규 문의",
    )

    baseline_stdout = StringIO()
    call_command(
        "audit_p1_team_runtime_scope",
        "--json",
        stdout=baseline_stdout,
    )
    baseline = json.loads(baseline_stdout.getvalue())
    assert "P1_TEAM_BASELINE_CUSTOMER_USER_PRESENT" in baseline["blockers"]
    assert "P1_TEAM_BASELINE_INQUIRY_PRESENT" in baseline["blockers"]

    operational_stdout = StringIO()
    call_command(
        "audit_p1_team_runtime_scope",
        "--operational",
        "--json",
        stdout=operational_stdout,
    )
    operational = json.loads(operational_stdout.getvalue())
    assert operational["mode"] == "OPERATIONAL_READ_ONLY"
    assert operational["runtime"]["p1_owned_inquiries"] == 1
    assert operational["runtime"]["non_p1_inquiries"] == 0
    assert operational["blockers"] == []
    assert operational["ready_for_isolated_rebuild"] is True


def test_operational_mode_rejects_non_p1_roles_and_inquiries():
    customers, _ = _seed_ready_baseline()
    operator = User.objects.create_user(
        username="P1-UNEXPECTED-OPERATOR",
        full_name="불필요 운영자",
        role_code=User.Role.OPERATOR,
        employee_no="P1-UNEXPECTED-OPS-001",
        is_active=True,
        is_synthetic=True,
    )
    Inquiry.objects.create(
        subscription=customers[0].subscriptions.get(),
        initiated_by=operator,
        channel_code=Inquiry.Channel.OPERATOR,
        raw_text="잘못된 실행자 문의",
    )
    stdout = StringIO()

    call_command(
        "audit_p1_team_runtime_scope",
        "--operational",
        "--json",
        stdout=stdout,
    )
    result = json.loads(stdout.getvalue())

    assert "P1_TEAM_OPERATOR_USER_PRESENT" in result["blockers"]
    assert "NON_P1_INQUIRY_PRESENT" in result["blockers"]
    assert result["ready_for_isolated_rebuild"] is False
