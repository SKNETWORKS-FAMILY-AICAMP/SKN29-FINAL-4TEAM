"""Safety tests for the P1 team isolated-runtime preparation command."""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import CustomerProfile


pytestmark = pytest.mark.django_db


def _seed_six() -> None:
    for index in range(1, 7):
        CustomerProfile.objects.create(
            customer_no=f"SYN-P1-TEAM-CUSTOMER-{index:03d}",
            customer_name=f"P1 합성 고객 {index}",
            phone=f"010-9100-{index:04d}",
            is_synthetic=True,
        )


def test_plan_reports_without_mutating_database():
    _seed_six()
    CustomerProfile.objects.create(
        customer_no="OLD-SYNTHETIC-CUSTOMER-001",
        customer_name="기존 합성 고객",
        phone="010-8100-0001",
        is_synthetic=True,
    )
    before = CustomerProfile.objects.count()

    with pytest.raises(CommandError, match="PostgreSQL 격리 DB"):
        call_command(
            "prepare_p1_team_isolated_runtime",
            "--json",
            stdout=StringIO(),
        )

    assert CustomerProfile.objects.count() == before


def test_apply_refuses_non_isolated_database():
    _seed_six()

    with pytest.raises(CommandError, match="격리 DB"):
        call_command(
            "prepare_p1_team_isolated_runtime",
            "--apply",
            "--confirm-isolated",
            "--json",
            stdout=StringIO(),
        )
