"""Create or rotate the single Water Bridge supervisor from environment data."""

from __future__ import annotations

import json
import os
from typing import Any
from uuid import uuid4

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.credential_policy import normalize_synthetic_username
from apps.accounts.models import AccountAuditEvent, User
from apps.accounts.repositories.account_audit_repository import (
    AccountAuditRepository,
)
from apps.accounts.services.account_lifecycle_service import (
    AccountLifecycleService,
)


SUPERVISOR_ENV_NAMES = {
    "username": "WATERBRIDGE_SUPERVISOR_USERNAME",
    "password": "WATERBRIDGE_SUPERVISOR_PASSWORD",
    "full_name": "WATERBRIDGE_SUPERVISOR_FULL_NAME",
    "employee_no": "WATERBRIDGE_SUPERVISOR_EMPLOYEE_NO",
}


def _required_environment() -> dict[str, str]:
    values = {
        field: os.getenv(environment_name, "").strip()
        for field, environment_name in SUPERVISOR_ENV_NAMES.items()
    }
    missing = [
        SUPERVISOR_ENV_NAMES[field]
        for field, value in values.items()
        if not value
    ]
    if missing:
        raise CommandError("필수 환경변수가 없습니다: " + ", ".join(missing))
    try:
        values["username"] = normalize_synthetic_username(values["username"])
    except ValidationError as exc:
        raise CommandError(" ".join(exc.messages)) from exc
    if not values["employee_no"].upper().startswith(("DEMO-", "SYN-")):
        raise CommandError(
            "WATERBRIDGE_SUPERVISOR_EMPLOYEE_NO는 DEMO- 또는 SYN-으로 "
            "시작해야 합니다."
        )
    if not any(
        marker in values["full_name"].upper()
        for marker in ("SYNTHETIC", "DEMO", "합성")
    ):
        raise CommandError(
            "WATERBRIDGE_SUPERVISOR_FULL_NAME에는 Synthetic, Demo 또는 "
            "합성 표기가 필요합니다."
        )
    if not 12 <= len(values["password"]) <= 128:
        raise CommandError("Supervisor 비밀번호는 12~128자여야 합니다.")
    try:
        password_validation.validate_password(values["password"])
    except ValidationError as exc:
        raise CommandError(" ".join(exc.messages)) from exc
    return values


class Command(BaseCommand):
    help = (
        "환경변수에서 단일 Water Bridge Supervisor를 생성하거나 "
        "비밀번호를 회전합니다. 비밀값은 출력하지 않습니다."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--json", action="store_true")

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        del args
        values = _required_environment()
        username = values["username"]

        users = User.objects.select_for_update().order_by("pk")
        others = list(
            users.filter(is_superuser=True).exclude(username__iexact=username)
        )
        if others:
            raise CommandError(
                "다른 superuser가 존재합니다. 단일 Supervisor 정책에 맞게 "
                "기존 계정을 먼저 검토해 주세요."
            )

        target = users.filter(username__iexact=username).first()
        created = target is None
        if created:
            target = User(
                username=username,
                full_name=values["full_name"],
                employee_no=values["employee_no"],
                role_code=User.Role.OPERATOR,
                is_synthetic=True,
                is_active=True,
                is_staff=True,
                is_superuser=True,
            )
            target.set_password(values["password"])
            target.full_clean()
            target.save()
            AccountAuditRepository.record(
                actor=target,
                target=target,
                event_type=AccountAuditEvent.EventType.CREATE,
                before_values={},
                after_values=AccountLifecycleService._snapshot(target),
                changed_fields=["account_created"],
                reason="Bootstrap the single Water Bridge supervisor",
                correlation_id=uuid4(),
            )
            password_changed = True
            access_changed = True
        else:
            if not target.is_synthetic:
                raise CommandError("기존 계정이 합성 계정이 아니므로 중단했습니다.")
            if (
                target.full_name != values["full_name"]
                or target.employee_no != values["employee_no"]
            ):
                raise CommandError(
                    "기존 Supervisor의 이름 또는 사번이 환경변수와 다릅니다. "
                    "자동 덮어쓰기는 하지 않습니다."
                )
            before = AccountLifecycleService._snapshot(target)
            password_changed = not target.check_password(values["password"])
            access_changed = not all(
                (
                    target.is_active,
                    target.is_staff,
                    target.is_superuser,
                    target.role_code == User.Role.OPERATOR,
                )
            )
            target.role_code = User.Role.OPERATOR
            target.is_active = True
            target.is_staff = True
            target.is_superuser = True
            changed_fields = []
            if access_changed:
                changed_fields.extend(
                    ["role_code", "is_active", "is_staff", "is_superuser"]
                )
            if password_changed:
                target.set_password(values["password"])
                target.auth_version += 1
                changed_fields.extend(["auth_version", "credential_changed"])
            target.full_clean()
            target.save(
                update_fields=[
                    "role_code",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "password",
                    "auth_version",
                    "updated_at",
                ]
            )
            if password_changed:
                AccountLifecycleService._revoke_all_refresh_tokens(target)
            if changed_fields:
                after = AccountLifecycleService._snapshot(target)
                before["credential_changed"] = False
                after["credential_changed"] = password_changed
                AccountAuditRepository.record(
                    actor=target,
                    target=target,
                    event_type=(
                        AccountAuditEvent.EventType.PASSWORD_RESET
                        if password_changed
                        else AccountAuditEvent.EventType.ADMIN_PERMISSION_CHANGE
                    ),
                    before_values=before,
                    after_values=after,
                    changed_fields=sorted(set(changed_fields)),
                    reason="Synchronize the single Water Bridge supervisor",
                    correlation_id=uuid4(),
                )

        if options["dry_run"]:
            transaction.set_rollback(True)

        result = {
            "status": "DRY_RUN" if options["dry_run"] else "APPLIED",
            "username": username,
            "created": created,
            "password_changed": password_changed,
            "access_changed": access_changed,
            "secret_exposed": False,
        }
        output = json.dumps(result, ensure_ascii=False, sort_keys=True)
        if options["json"]:
            self.stdout.write(output)
        else:
            self.stdout.write(self.style.SUCCESS(output))
