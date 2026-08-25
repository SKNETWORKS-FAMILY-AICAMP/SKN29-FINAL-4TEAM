"""Synthetic consultant password-login and local setup command tests."""

from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User


pytestmark = pytest.mark.django_db

USERNAME = "SYN-CONSULTANT-LOGIN-001"
PASSWORD = "consultant-pass-2026"


def _consultant() -> User:
    user = User.objects.create_user(
        username=USERNAME,
        full_name="합성 상담사 로그인",
        role_code=User.Role.CONSULTANT,
        employee_no="SYN-EMP-CNS-LOGIN-001",
        is_synthetic=True,
    )
    user.set_unusable_password()
    user.save(update_fields=["password", "updated_at"])
    return user


def test_local_command_reads_password_from_environment_and_supports_dry_run(
    monkeypatch,
    settings,
):
    settings.DEBUG = True
    user = _consultant()
    initial_auth_version = user.auth_version
    monkeypatch.setenv("TEST_CONSULTANT_PASSWORD", PASSWORD)

    dry_stdout = StringIO()
    call_command(
        "set_synthetic_consultant_password",
        "--username",
        USERNAME,
        "--password-env",
        "TEST_CONSULTANT_PASSWORD",
        "--dry-run",
        "--json",
        stdout=dry_stdout,
    )
    user.refresh_from_db()
    assert not user.check_password(PASSWORD)
    assert user.auth_version == initial_auth_version
    assert json.loads(dry_stdout.getvalue())["secret_exposed"] is False

    apply_stdout = StringIO()
    call_command(
        "set_synthetic_consultant_password",
        "--username",
        USERNAME,
        "--password-env",
        "TEST_CONSULTANT_PASSWORD",
        "--json",
        stdout=apply_stdout,
    )
    user.refresh_from_db()
    assert user.check_password(PASSWORD)
    assert user.auth_version == initial_auth_version + 1
    assert PASSWORD not in apply_stdout.getvalue()


def test_local_command_rejects_non_consultant(monkeypatch, settings):
    settings.DEBUG = True
    User.objects.create_user(
        username="SYN-CUSTOMER-LOGIN-001",
        full_name="합성 고객",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    monkeypatch.setenv("TEST_CONSULTANT_PASSWORD", PASSWORD)

    with pytest.raises(CommandError, match="합성 상담사"):
        call_command(
            "set_synthetic_consultant_password",
            "--username",
            "SYN-CUSTOMER-LOGIN-001",
            "--password-env",
            "TEST_CONSULTANT_PASSWORD",
        )


def test_consultant_can_use_general_password_login_without_customer_link(client):
    user = _consultant()
    user.set_password(PASSWORD)
    user.save(update_fields=["password", "updated_at"])

    success = client.post(
        "/api/v1/auth/login",
        {"username": USERNAME, "password": PASSWORD},
        content_type="application/json",
    )
    wrong = client.post(
        "/api/v1/auth/login",
        {"username": USERNAME, "password": "wrong"},
        content_type="application/json",
    )

    assert success.status_code == 200
    assert success.json()["data"]["user"]["role_code"] == "CONSULTANT"
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "AUTH_LOGIN_FAILED"
