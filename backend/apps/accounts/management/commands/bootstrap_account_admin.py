"""Bootstrap the fixed synthetic-account Admin group and memberships."""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User


ACCOUNT_ADMIN_GROUP = "T017_ACCOUNT_ADMINISTRATORS"
ACCOUNT_ADMIN_PERMISSION_CODES = {
    "add_user",
    "change_user",
    "view_user",
}


class Command(BaseCommand):
    help = (
        "Create the fixed T-017 account Admin group and optionally grant or "
        "revoke one synthetic OPERATOR."
    )

    def add_arguments(self, parser):
        membership = parser.add_mutually_exclusive_group()
        membership.add_argument("--grant", metavar="USERNAME")
        membership.add_argument("--revoke", metavar="USERNAME")

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
        group.permissions.set(permissions)

        if options.get("grant"):
            user = self._get_eligible_user(options["grant"])
            user.groups.add(group)
            if not user.is_staff:
                user.is_staff = True
                user.save(update_fields=["is_staff", "updated_at"])
            action = f"granted={user.username}"
        elif options.get("revoke"):
            try:
                user = User.objects.get(username=options["revoke"])
            except User.DoesNotExist as exc:
                raise CommandError("Account does not exist.") from exc
            if user.is_superuser:
                raise CommandError("Superuser access is not managed here.")
            user.groups.remove(group)
            if user.is_staff:
                user.is_staff = False
                user.save(update_fields=["is_staff", "updated_at"])
            action = f"revoked={user.username}"
        else:
            action = "membership=unchanged"

        self.stdout.write(
            self.style.SUCCESS(
                f"group={group.name} created={created} {action}"
            )
        )

    @staticmethod
    def _get_eligible_user(username: str) -> User:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError("Account does not exist.") from exc
        if user.is_superuser:
            raise CommandError("Superuser access is not managed here.")
        if not user.is_active:
            raise CommandError("Only active accounts can receive Admin access.")
        if not user.is_synthetic:
            raise CommandError("Only synthetic accounts can receive Admin access.")
        if user.role_code != User.Role.OPERATOR:
            raise CommandError("Only OPERATOR accounts can receive Admin access.")
        return user
