"""Read-only P1 team runtime scope audit tests."""

from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command

from apps.accounts.models import CustomerProfile, User


pytestmark = pytest.mark.django_db


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
    assert CustomerProfile.objects.count() == before_customers
    assert User.objects.count() == before_users
