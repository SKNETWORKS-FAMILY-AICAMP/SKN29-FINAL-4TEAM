"""Set a local synthetic consultant password without exposing the secret."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User


DEFAULT_PASSWORD_ENV = "WATERBRIDGE_CONSULTANT_PASSWORD"
ENV_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,80}$")


def _validate_password(value: str) -> None:
    if not 12 <= len(value) <= 64:
        raise CommandError("상담사 비밀번호는 12~64자여야 합니다.")
    if re.search(r"[A-Za-z]", value) is None or re.search(r"[0-9]", value) is None:
        raise CommandError("상담사 비밀번호에는 영문과 숫자가 모두 포함되어야 합니다.")


class Command(BaseCommand):
    help = "DEBUG 로컬 합성 상담사 계정의 ID/PW 로그인을 준비합니다."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--username", required=True)
        parser.add_argument("--password-env", default=DEFAULT_PASSWORD_ENV)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--json", action="store_true")

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        del args
        if not settings.DEBUG:
            raise CommandError("이 명령은 DEBUG 로컬 환경에서만 실행할 수 있습니다.")

        username = str(options["username"] or "").strip()
        env_name = str(options["password_env"] or "").strip()
        if not username:
            raise CommandError("상담사 username을 입력해 주세요.")
        if ENV_NAME_PATTERN.fullmatch(env_name) is None:
            raise CommandError("비밀번호 환경변수 이름 형식을 확인해 주세요.")

        password = os.environ.get(env_name, "")
        if not password:
            raise CommandError(f"{env_name} 환경변수가 비어 있습니다.")
        _validate_password(password)

        user = (
            User.objects.select_for_update(of=("self",))
            .filter(username__iexact=username)
            .first()
        )
        if user is None:
            raise CommandError("해당 합성 상담사 계정을 찾을 수 없습니다.")
        if (
            user.role_code != User.Role.CONSULTANT
            or not user.is_synthetic
            or not user.is_active
            or not user.employee_no
        ):
            raise CommandError("활성 합성 상담사 계정만 준비할 수 있습니다.")

        changed = not user.check_password(password)
        if changed:
            user.set_password(password)
            user.auth_version += 1
            user.full_clean()
            user.save(update_fields=["password", "auth_version", "updated_at"])

        if options["dry_run"]:
            transaction.set_rollback(True)

        result = {
            "status": "DRY_RUN" if options["dry_run"] else "APPLIED",
            "username": user.username,
            "role_code": user.role_code,
            "password_source": "ENVIRONMENT",
            "password_env": env_name,
            "changed": changed,
            "secret_exposed": False,
        }
        message = json.dumps(result, ensure_ascii=False, sort_keys=True)
        if options["json"]:
            self.stdout.write(message)
        else:
            self.stdout.write(self.style.SUCCESS(message))
