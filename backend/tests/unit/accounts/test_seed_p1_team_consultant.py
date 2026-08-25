"""Safety tests for the narrow P1 isolated consultant Seed."""

from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.accounts.management.commands.seed_p1_team_consultant import (
    CONSULTANT_EMPLOYEE_NO,
    CONSULTANT_FULL_NAME,
    CONSULTANT_USERNAME,
    ISOLATED_DATABASE_NAME,
)
from apps.accounts.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def isolated_database(monkeypatch, settings) -> None:
    settings.DEBUG = True
    monkeypatch.setitem(
        connection.settings_dict,
        "NAME",
        ISOLATED_DATABASE_NAME,
    )


def _run(*arguments: str) -> dict[str, object]:
    stdout = StringIO()
    call_command(
        "seed_p1_team_consultant",
        "--confirm-isolated",
        "--json",
        *arguments,
        stdout=stdout,
    )
    return json.loads(stdout.getvalue())


def test_seed_creates_only_one_exact_consultant_with_unusable_password(
    isolated_database,
):
    result = _run()

    assert result["status"] == "APPLIED"
    assert result["created"] is True
    assert result["secret_exposed"] is False
    assert User.objects.count() == 1
    consultant = User.objects.get()
    assert consultant.username == CONSULTANT_USERNAME
    assert consultant.full_name == CONSULTANT_FULL_NAME
    assert consultant.role_code == User.Role.CONSULTANT
    assert consultant.employee_no == CONSULTANT_EMPLOYEE_NO
    assert consultant.is_active is True
    assert consultant.is_synthetic is True
    assert consultant.has_usable_password() is False


def test_seed_is_idempotent_and_preserves_securely_set_password(
    isolated_database,
):
    _run()
    consultant = User.objects.get()
    public_id = consultant.public_id
    consultant.set_password("SecureConsultant123")
    consultant.save(update_fields=["password", "updated_at"])

    result = _run()

    assert result["created"] is False
    assert result["initial_password_usable"] is True
    assert User.objects.count() == 1
    consultant.refresh_from_db()
    assert consultant.public_id == public_id
    assert consultant.check_password("SecureConsultant123") is True


def test_dry_run_rolls_back_new_consultant(isolated_database):
    result = _run("--dry-run")

    assert result["status"] == "DRY_RUN_READY"
    assert result["created"] is True
    assert User.objects.count() == 0


def test_seed_fails_closed_when_another_user_exists(isolated_database):
    User.objects.create_user(
        username="ANOTHER-CONSULTANT-001",
        full_name="다른 합성 상담사",
        role_code=User.Role.CONSULTANT,
        employee_no="ANOTHER-EMP-001",
        is_synthetic=True,
    )

    with pytest.raises(CommandError, match="다른 User"):
        _run()

    assert User.objects.count() == 1


def test_seed_requires_exact_database_debug_and_confirmation(
    isolated_database,
    monkeypatch,
    settings,
):
    with pytest.raises(CommandError, match="confirm-isolated"):
        call_command("seed_p1_team_consultant", stdout=StringIO())

    monkeypatch.setitem(connection.settings_dict, "NAME", "waterbridge")
    with pytest.raises(CommandError, match="P1 격리 DB"):
        call_command(
            "seed_p1_team_consultant",
            "--confirm-isolated",
            stdout=StringIO(),
        )

    monkeypatch.setitem(
        connection.settings_dict,
        "NAME",
        ISOLATED_DATABASE_NAME,
    )
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG"):
        call_command(
            "seed_p1_team_consultant",
            "--confirm-isolated",
            stdout=StringIO(),
        )
