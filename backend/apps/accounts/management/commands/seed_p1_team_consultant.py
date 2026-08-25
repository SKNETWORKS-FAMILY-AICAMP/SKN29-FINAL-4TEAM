"""Create only the approved synthetic consultant in the P1 isolated DB."""

from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.accounts.models import User


ISOLATED_DATABASE_NAME = "waterbridge_p1_team_isolated"
CONSULTANT_USERNAME = "DEMO-CONSULTANT-001"
CONSULTANT_FULL_NAME = "합성 상담사 001"
CONSULTANT_EMPLOYEE_NO = "DEMO-EMP-CNS-001"


def _identity_conflicts(user: User) -> list[str]:
    expected = {
        "username": CONSULTANT_USERNAME,
        "full_name": CONSULTANT_FULL_NAME,
        "email": "",
        "phone": "",
        "role_code": User.Role.CONSULTANT,
        "employee_no": CONSULTANT_EMPLOYEE_NO,
        "is_active": True,
        "is_staff": False,
        "is_superuser": False,
        "is_synthetic": True,
    }
    return sorted(
        field
        for field, expected_value in expected.items()
        if getattr(user, field) != expected_value
    )


class Command(BaseCommand):
    help = (
        "정확한 DEBUG P1 격리 DB에 합성 상담사 "
        "DEMO-CONSULTANT-001 한 명만 멱등 준비합니다."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--confirm-isolated", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--json", action="store_true")

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        del args
        database_name = str(connection.settings_dict.get("NAME") or "")
        if (
            not settings.DEBUG
            or database_name != ISOLATED_DATABASE_NAME
            or not options["confirm_isolated"]
        ):
            raise CommandError(
                "합성 상담사 Seed는 --confirm-isolated가 있는 정확한 "
                "DEBUG P1 격리 DB에서만 실행됩니다."
            )

        existing_users = list(User.objects.select_for_update().order_by("id"))
        if len(existing_users) > 1:
            raise CommandError("P1 상담사 Seed 전에 다른 User가 존재합니다.")
        if existing_users and existing_users[0].username != CONSULTANT_USERNAME:
            raise CommandError("P1 상담사 Seed 전에 다른 User가 존재합니다.")

        created = not existing_users
        if created:
            consultant = User.objects.create_user(
                username=CONSULTANT_USERNAME,
                password=None,
                full_name=CONSULTANT_FULL_NAME,
                email="",
                phone="",
                role_code=User.Role.CONSULTANT,
                employee_no=CONSULTANT_EMPLOYEE_NO,
                is_active=True,
                is_staff=False,
                is_superuser=False,
                is_synthetic=True,
            )
        else:
            consultant = existing_users[0]
            conflicts = _identity_conflicts(consultant)
            if conflicts:
                raise CommandError(
                    "기존 P1 상담사 Identity가 승인 계약과 충돌합니다: "
                    f"fields={','.join(conflicts)}"
                )
            consultant.full_clean()

        if options["dry_run"]:
            transaction.set_rollback(True)

        result = {
            "status": "DRY_RUN_READY" if options["dry_run"] else "APPLIED",
            "database_name": database_name,
            "username": consultant.username,
            "role_code": consultant.role_code,
            "employee_no": consultant.employee_no,
            "created": created,
            "user_count": 1,
            "initial_password_usable": (
                consultant.has_usable_password() if not created else False
            ),
            "secret_exposed": False,
        }
        payload = json.dumps(result, ensure_ascii=False, sort_keys=True)
        if options["json"]:
            self.stdout.write(payload)
        else:
            self.stdout.write(self.style.SUCCESS(payload))
