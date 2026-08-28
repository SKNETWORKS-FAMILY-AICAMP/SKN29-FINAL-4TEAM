"""T-017B synthetic-account Admin access and mutation boundaries."""

from __future__ import annotations

from io import StringIO

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.management.commands.bootstrap_account_admin import (
    ACCOUNT_ADMIN_GROUP,
    ACCOUNT_ADMIN_PERMISSION_CODES,
)
from apps.accounts.models import User


pytestmark = pytest.mark.django_db

PASSWORD = "Admin-Test-Password-2026!"


def create_operator(
    username: str,
    *,
    is_staff: bool = False,
    is_synthetic: bool = True,
) -> User:
    return User.objects.create_user(
        username=username,
        password=PASSWORD,
        full_name="Synthetic operator",
        role_code=User.Role.OPERATOR,
        employee_no=f"EMP-{username}",
        is_staff=is_staff,
        is_synthetic=is_synthetic,
    )


def create_supervisor() -> User:
    return User.objects.create_superuser(
        username="SYN-WATERBRIDGE-SUPERVISOR",
        password=PASSWORD,
        full_name="Synthetic Water Bridge supervisor",
        employee_no="SYN-SUPERVISOR-001",
        is_synthetic=True,
    )


def grant_account_admin(user: User) -> None:
    actor, _ = User.objects.get_or_create(
        username="SYN-ACCOUNT-ADMIN-BOOTSTRAP-SUPERUSER",
        defaults={
            "full_name": "Synthetic bootstrap superuser",
            "role_code": User.Role.OPERATOR,
            "employee_no": "SYN-BOOTSTRAP-SUPER-001",
            "is_staff": True,
            "is_superuser": True,
            "is_synthetic": True,
        },
    )
    if not actor.check_password(PASSWORD):
        actor.set_password(PASSWORD)
        actor.save(update_fields=["password", "updated_at"])
    call_command(
        "bootstrap_account_admin",
        grant=user.username,
        actor=actor.username,
        reason="Synthetic unit-test administrator grant",
        stdout=StringIO(),
    )
    user.refresh_from_db()


def test_bootstrap_group_is_idempotent_and_grants_only_fixed_permissions():
    operator = create_operator("SYN-OPERATOR-BOOTSTRAP")
    backup = create_operator("SYN-OPERATOR-BOOTSTRAP-BACKUP")

    grant_account_admin(operator)
    grant_account_admin(backup)
    call_command("bootstrap_account_admin", stdout=StringIO())

    group = Group.objects.get(name=ACCOUNT_ADMIN_GROUP)
    assert set(group.permissions.values_list("codename", flat=True)) == (
        ACCOUNT_ADMIN_PERMISSION_CODES
    )
    assert operator.is_staff is True
    assert operator.groups.filter(pk=group.pk).exists()

    call_command(
        "bootstrap_account_admin",
        revoke=operator.username,
        actor="SYN-ACCOUNT-ADMIN-BOOTSTRAP-SUPERUSER",
        reason="Synthetic unit-test administrator revoke",
        stdout=StringIO(),
    )
    operator.refresh_from_db()
    assert operator.is_staff is False
    assert not operator.groups.filter(pk=group.pk).exists()


@pytest.mark.parametrize(
    ("role_code", "is_staff", "expected_status"),
    [
        (User.Role.OPERATOR, False, 403),
        (User.Role.CUSTOMER, True, 403),
    ],
)
def test_non_staff_and_non_operator_cannot_open_account_admin(
    client,
    role_code,
    is_staff,
    expected_status,
):
    employee_no = None if role_code == User.Role.CUSTOMER else "EMP-DENIED"
    user = User.objects.create_user(
        username=f"SYN-DENIED-{role_code}",
        password=PASSWORD,
        full_name="Denied account",
        role_code=role_code,
        employee_no=employee_no,
        is_staff=is_staff,
        is_synthetic=True,
    )
    client.force_login(user)

    response = client.get(reverse("admin:accounts_user_changelist"))

    assert response.status_code == expected_status


def test_operator_without_model_permission_is_denied(client):
    operator = create_operator("SYN-OPERATOR-NO-PERM", is_staff=True)
    client.force_login(operator)

    response = client.get(reverse("admin:accounts_user_changelist"))

    assert response.status_code == 403


def test_granted_operator_sees_only_synthetic_accounts(client):
    operator = create_supervisor()
    synthetic = User.objects.create_user(
        username="SYN-CUSTOMER-VISIBLE",
        full_name="Synthetic visible",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    real_account = User.objects.create_user(
        username="REAL-CUSTOMER-HIDDEN",
        full_name="Real hidden",
        role_code=User.Role.CUSTOMER,
        is_synthetic=False,
    )
    client.force_login(operator)

    response = client.get(reverse("admin:accounts_user_changelist"))

    assert response.status_code == 200
    body = response.content.decode()
    assert synthetic.username in body
    assert real_account.username not in body


def test_admin_add_forces_synthetic_and_blocks_privilege_escalation(client):
    operator = create_supervisor()
    client.force_login(operator)

    response = client.post(
        reverse("admin:accounts_user_add"),
        {
            "username": "syn-customer-created",
            "password1": PASSWORD,
            "password2": PASSWORD,
            "role_code": User.Role.CUSTOMER,
            "employee_no": "",
            "full_name": "Synthetic created",
            "email": "synthetic@example.invalid",
            "phone": "",
            "change_reason": "Create synthetic QA customer",
            "is_synthetic": "0",
            "is_staff": "1",
            "is_superuser": "1",
            "_save": "Save",
        },
    )

    assert response.status_code == 302
    created = User.objects.get(username="SYN-CUSTOMER-CREATED")
    assert created.is_synthetic is True
    assert created.is_staff is False
    assert created.is_superuser is False
    assert created.check_password(PASSWORD)


def test_admin_change_preserves_identity_role_and_access_fields(client):
    operator = create_supervisor()
    target = User.objects.create_user(
        username="SYN-CUSTOMER-IMMUTABLE",
        full_name="Before",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    client.force_login(operator)

    response = client.post(
        reverse("admin:accounts_user_change", args=[target.pk]),
        {
            "full_name": "Synthetic after",
            "email": "after@example.invalid",
            "phone": "000-0000-0000",
            "change_reason": "Update synthetic QA profile",
            "username": "SYN-TAMPERED",
            "role_code": User.Role.OPERATOR,
            "employee_no": "EMP-TAMPERED",
            "is_active": "0",
            "is_staff": "1",
            "is_superuser": "1",
            "is_synthetic": "0",
            "_save": "Save",
        },
    )

    assert response.status_code == 302
    target.refresh_from_db()
    assert target.full_name == "Synthetic after"
    assert target.email == "after@example.invalid"
    assert target.username == "SYN-CUSTOMER-IMMUTABLE"
    assert target.role_code == User.Role.CUSTOMER
    assert target.employee_no is None
    assert target.is_active is True
    assert target.is_staff is False
    assert target.is_superuser is False
    assert target.is_synthetic is True


def test_admin_rejects_values_that_could_be_real_personal_information(client):
    operator = create_supervisor()
    client.force_login(operator)

    response = client.post(
        reverse("admin:accounts_user_add"),
        {
            "username": "SYN-CUSTOMER-REAL-PII",
            "password1": PASSWORD,
            "password2": PASSWORD,
            "role_code": User.Role.CUSTOMER,
            "employee_no": "",
            "full_name": "Real Person",
            "email": "real.person@example.com",
            "phone": "010-1234-5678",
            "change_reason": "Reject unsafe synthetic profile",
            "_save": "Save",
        },
    )

    assert response.status_code == 200
    assert not User.objects.filter(username="SYN-CUSTOMER-REAL-PII").exists()
    assert "Synthetic names must include" in response.content.decode()


def test_physical_delete_and_superuser_change_are_denied(client):
    operator = create_supervisor()
    target = User.objects.create_user(
        username="SYN-CUSTOMER-NO-DELETE",
        full_name="No delete",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    superuser = User.objects.create_superuser(
        username="SYN-SUPERUSER-PROTECTED",
        password=PASSWORD,
        full_name="Protected superuser",
        employee_no="EMP-SUPER-PROTECTED",
        is_synthetic=True,
    )
    client.force_login(operator)

    delete_response = client.post(
        reverse("admin:accounts_user_delete", args=[target.pk]),
        {"post": "yes"},
    )
    change_response = client.post(
        reverse("admin:accounts_user_change", args=[superuser.pk]),
        {
            "full_name": "Tampered superuser",
            "email": "",
            "phone": "",
            "change_reason": "Attempt protected superuser update",
            "_save": "Save",
        },
    )

    assert delete_response.status_code == 403
    assert change_response.status_code == 403
    assert User.objects.filter(pk=target.pk).exists()
    superuser.refresh_from_db()
    assert superuser.full_name == "Protected superuser"


def test_deactivate_action_skips_self_and_superuser(client):
    operator = create_supervisor()
    target = User.objects.create_user(
        username="SYN-CUSTOMER-DEACTIVATE",
        full_name="Deactivate target",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    superuser = User.objects.create_superuser(
        username="SYN-SUPERUSER-ACTION",
        password=PASSWORD,
        full_name="Action protected",
        employee_no="EMP-SUPER-ACTION",
        is_synthetic=True,
    )
    client.force_login(operator)

    response = client.post(
        reverse("admin:accounts_user_changelist"),
        {
            "action": "deactivate_accounts",
            "_selected_action": [operator.pk, target.pk, superuser.pk],
            "index": "0",
            "lifecycle_reason": "Deactivate selected synthetic QA account",
        },
    )

    assert response.status_code == 302
    operator.refresh_from_db()
    target.refresh_from_db()
    superuser.refresh_from_db()
    assert operator.is_active is True
    assert target.is_active is False
    assert superuser.is_active is True


def test_admin_mutation_requires_csrf(client):
    from django.test import Client

    operator = create_supervisor()
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(operator)

    response = csrf_client.post(
        reverse("admin:accounts_user_add"),
        {
            "username": "SYN-CSRF-REJECTED",
            "password1": PASSWORD,
            "password2": PASSWORD,
            "role_code": User.Role.CUSTOMER,
            "full_name": "Rejected",
        },
    )

    assert response.status_code == 403
    assert not User.objects.filter(username="SYN-CSRF-REJECTED").exists()
