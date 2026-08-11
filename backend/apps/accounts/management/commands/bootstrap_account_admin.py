"""Bootstrap the fixed synthetic-account Admin group and memberships."""

from __future__ import annotations

from uuid import uuid4

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.account_admin_guards import allow_account_admin_m2m_change
from apps.accounts.account_admin_policy import (
    ACCOUNT_ADMIN_GROUP,
    ACCOUNT_ADMIN_PERMISSION_CODES,
)
from apps.accounts.models import User
from apps.accounts.services.account_lifecycle_service import (
    AccountLifecycleError,
    AccountLifecycleService,
)


class Command(BaseCommand):
    help = (
        "Create the fixed T-017 account Admin group and optionally grant or "
        "revoke one synthetic OPERATOR."
    )

    def add_arguments(self, parser):
        membership = parser.add_mutually_exclusive_group()
        membership.add_argument("--grant", metavar="USERNAME")
        membership.add_argument("--revoke", metavar="USERNAME")
        parser.add_argument("--actor", metavar="USERNAME")
        parser.add_argument("--reason")

    @transaction.atomic
    def handle(self, *args, **options):
        permissions = list(
            Permission.objects.filter(
                content_type__app_label="accounts",
                content_type__model="user",
                codename__in=ACCOUNT_ADMIN_PERMISSION_CODES,
            )
        )
        found_codes = {permission.codename for permission in permissions}
        if found_codes != ACCOUNT_ADMIN_PERMISSION_CODES:
            missing = sorted(ACCOUNT_ADMIN_PERMISSION_CODES - found_codes)
            raise CommandError(f"Missing account permissions: {missing}")

        group, created = Group.objects.get_or_create(name=ACCOUNT_ADMIN_GROUP)
        with allow_account_admin_m2m_change():
            group.permissions.set(permissions)

        membership_username = options.get("grant") or options.get("revoke")
        if membership_username:
            if not options.get("actor") or not str(options.get("reason") or "").strip():
                raise CommandError(
                    "--actor and a non-empty --reason are required for membership changes."
                )
            try:
                actor = User.objects.get(username=options["actor"])
                user = User.objects.get(username=membership_username)
            except User.DoesNotExist as exc:
                raise CommandError("Actor or target account does not exist.") from exc
            try:
                if options.get("grant"):
                    AccountLifecycleService.grant_account_admin(
                        actor=actor,
                        target=user,
                        reason=options["reason"],
                        correlation_id=uuid4(),
                    )
                    action = f"granted={user.username}"
                else:
                    AccountLifecycleService.revoke_account_admin(
                        actor=actor,
                        target=user,
                        reason=options["reason"],
                        correlation_id=uuid4(),
                    )
                    action = f"revoked={user.username}"
            except AccountLifecycleError as exc:
                raise CommandError(f"{exc.code}: {exc}") from exc
        else:
            action = "membership=unchanged"

        self.stdout.write(
            self.style.SUCCESS(
                f"group={group.name} created={created} {action}"
            )
        )
