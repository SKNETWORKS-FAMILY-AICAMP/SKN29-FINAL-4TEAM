"""Plan or synchronize only the six consultant dashboard notices."""

from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, connection

from apps.operations.repositories import SyntheticImportConflict
from apps.operations.services.consultant_notice_sync_service import (
    ConsultantNoticeSyncService,
)


class Command(BaseCommand):
    """Run a guarded, notice-only synchronization."""

    help = (
        "Plan, dry-run, or apply the six synthetic consultant notices without "
        "seeding customers, inquiries, staff, or other dashboard data."
    )

    def add_arguments(self, parser) -> None:
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument(
            "--dry-run",
            action="store_true",
            help="Apply and verify the six notices, then roll back all writes.",
        )
        mode.add_argument(
            "--apply",
            action="store_true",
            help="Commit the six notice changes after target verification.",
        )
        parser.add_argument(
            "--expected-database",
            help="Required with --apply; must equal the configured DB name.",
        )
        parser.add_argument(
            "--expected-host",
            help="Required with --apply; must equal the configured DB host.",
        )

    def handle(self, *args, **options) -> str:
        mode = (
            "apply"
            if options["apply"]
            else "dry-run" if options["dry_run"] else "plan"
        )
        if mode == "apply":
            self._verify_apply_target(
                expected_database=options["expected_database"],
                expected_host=options["expected_host"],
            )
        try:
            result = ConsultantNoticeSyncService().run(mode=mode)
        except (
            SyntheticImportConflict,
            ValidationError,
            IntegrityError,
            ValueError,
        ) as exc:
            raise CommandError(
                f"Consultant notice sync aborted: {exc}"
            ) from exc
        return json.dumps(
            result.as_dict(),
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def _verify_apply_target(
        *,
        expected_database: str | None,
        expected_host: str | None,
    ) -> None:
        if not expected_database or not expected_host:
            raise CommandError(
                "--apply requires --expected-database and --expected-host."
            )
        configured_database = str(connection.settings_dict["NAME"])
        configured_host = str(connection.settings_dict["HOST"] or "localhost")
        if configured_database != expected_database:
            raise CommandError(
                "Configured database does not match --expected-database."
            )
        if configured_host != expected_host:
            raise CommandError(
                "Configured host does not match --expected-host."
            )
