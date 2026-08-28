"""Single-supervisor bootstrap, access, and credential regression tests."""

from __future__ import annotations

from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from apps.accounts.models import AccountAuditEvent, CustomerProfile, User
from apps.accounts.services.account_lifecycle_service import (
    AccountLifecycleError,
    AccountLifecycleService,
)
from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db

SUPERVISOR_PASSWORD = "SupervisorPassword2026!"


def supervisor_environment(monkeypatch) -> None:
    monkeypatch.setenv(
        "WATERBRIDGE_SUPERVISOR_USERNAME",
        "SYN-WATERBRIDGE-SUPERVISOR",
    )
    monkeypatch.setenv(
        "WATERBRIDGE_SUPERVISOR_PASSWORD",
        SUPERVISOR_PASSWORD,
    )
    monkeypatch.setenv(
        "WATERBRIDGE_SUPERVISOR_FULL_NAME",
        "Synthetic Water Bridge supervisor",
    )
    monkeypatch.setenv(
        "WATERBRIDGE_SUPERVISOR_EMPLOYEE_NO",
        "SYN-SUPERVISOR-001",
    )


def create_supervisor() -> User:
    return User.objects.create_superuser(
        username="SYN-WATERBRIDGE-SUPERVISOR",
        password=SUPERVISOR_PASSWORD,
        full_name="Synthetic Water Bridge supervisor",
        employee_no="SYN-SUPERVISOR-001",
        is_synthetic=True,
    )


def test_bootstrap_uses_environment_without_printing_secret(monkeypatch):
    supervisor_environment(monkeypatch)
    dry_output = StringIO()
    call_command(
        "bootstrap_waterbridge_supervisor",
        "--dry-run",
        "--json",
        stdout=dry_output,
    )
    assert not User.objects.exists()
    assert SUPERVISOR_PASSWORD not in dry_output.getvalue()

    output = StringIO()
    call_command(
        "bootstrap_waterbridge_supervisor",
        "--json",
        stdout=output,
    )
    supervisor = User.objects.get(username="SYN-WATERBRIDGE-SUPERVISOR")
    assert supervisor.check_password(SUPERVISOR_PASSWORD)
    assert supervisor.is_superuser is True
    assert supervisor.is_staff is True
    assert supervisor.role_code == User.Role.OPERATOR
    assert SUPERVISOR_PASSWORD not in output.getvalue()
    audit = AccountAuditEvent.objects.get(target_user=supervisor)
    assert "password" not in str(audit.before_values).lower()
    assert "password" not in str(audit.after_values).lower()


def test_bootstrap_refuses_a_second_superuser(monkeypatch):
    supervisor_environment(monkeypatch)
    User.objects.create_superuser(
        username="SYN-OTHER-SUPERUSER",
        password=SUPERVISOR_PASSWORD,
        full_name="Synthetic other supervisor",
        employee_no="SYN-OTHER-SUPERUSER",
        is_synthetic=True,
    )
    with pytest.raises(CommandError, match="다른 superuser"):
        call_command("bootstrap_waterbridge_supervisor", stdout=StringIO())


def test_admin_route_allows_only_the_configured_supervisor(client):
    anonymous = client.get(reverse("admin:index"))
    assert anonymous.status_code == 302
    login = client.get(reverse("admin:login"))
    assert login.status_code == 200
    assert "운영 관리자 로그인" in login.content.decode()

    other_superuser = User.objects.create_superuser(
        username="SYN-OTHER-SUPERUSER",
        password=SUPERVISOR_PASSWORD,
        full_name="Synthetic other supervisor",
        employee_no="SYN-OTHER-SUPERUSER",
        is_synthetic=True,
    )
    client.force_login(other_superuser)
    assert client.get(reverse("admin:index")).status_code == 403

    supervisor = create_supervisor()
    client.force_login(supervisor)
    response = client.get(reverse("admin:index"))
    assert response.status_code == 200
    assert "Water Bridge" in response.content.decode()
    assert client.get("/internal/admin/").status_code == 404


def test_expected_operations_models_are_registered():
    from apps.accounts.admin_site import waterbridge_admin_site

    assert User in waterbridge_admin_site._registry
    assert CustomerProfile in waterbridge_admin_site._registry
    assert CustomerSubscription in waterbridge_admin_site._registry
    assert Inquiry in waterbridge_admin_site._registry
    assert Consultation in waterbridge_admin_site._registry


def test_consultant_id_and_password_reset_follow_strict_policy():
    supervisor = create_supervisor()
    consultant = User.objects.create_user(
        username="SYN-CONSULTANT-001",
        password="InitialPassword2026",
        full_name="Synthetic consultant",
        role_code=User.Role.CONSULTANT,
        employee_no="SYN-CONSULTANT-001",
        is_synthetic=True,
    )
    initial_auth_version = consultant.auth_version

    with pytest.raises(AccountLifecycleError, match="영문·숫자"):
        AccountLifecycleService.update_consultant_credentials(
            actor=supervisor,
            target=consultant,
            username="SYN-CONSULTANT-002",
            new_password="Contains-Symbol-2026",
            reason="Reject invalid consultant password",
            correlation_id=uuid4(),
        )

    AccountLifecycleService.update_consultant_credentials(
        actor=supervisor,
        target=consultant,
        username="syn-consultant-002",
        new_password="ReplacementPass2026",
        reason="Reset transferred consultant credentials",
        correlation_id=uuid4(),
    )
    consultant.refresh_from_db()
    assert consultant.username == "SYN-CONSULTANT-002"
    assert consultant.check_password("ReplacementPass2026")
    assert consultant.auth_version == initial_auth_version + 1
    audit = AccountAuditEvent.objects.get(
        target_user=consultant,
        event_type=AccountAuditEvent.EventType.CREDENTIAL_RECOVERY,
    )
    assert audit.changed_fields == ["auth_version", "credential_changed"]
    assert "ReplacementPass2026" not in str(audit.after_values)


def test_supervisor_admin_resets_consultant_password_without_displaying_it(client):
    supervisor = create_supervisor()
    consultant = User.objects.create_user(
        username="SYN-CONSULTANT-ADMIN-001",
        password="OriginalPass2026",
        full_name="Synthetic consultant admin",
        role_code=User.Role.CONSULTANT,
        employee_no="SYN-CONSULTANT-ADMIN-001",
        is_synthetic=True,
    )
    client.force_login(supervisor)
    change_url = reverse("admin:accounts_user_change", args=[consultant.pk])
    page = client.get(change_url)
    assert page.status_code == 200
    assert "OriginalPass2026" not in page.content.decode()

    response = client.post(
        change_url,
        {
            "username": "SYN-CONSULTANT-ADMIN-002",
            "full_name": "Synthetic consultant admin",
            "email": "consultant@example.invalid",
            "phone": "000-0000-0000",
            "new_password1": "AdminResetPass2026",
            "new_password2": "AdminResetPass2026",
            "change_reason": "Rotate synthetic consultant credential",
            "_save": "Save",
        },
    )
    assert response.status_code == 302
    consultant.refresh_from_db()
    assert consultant.username == "SYN-CONSULTANT-ADMIN-002"
    assert consultant.check_password("AdminResetPass2026")
