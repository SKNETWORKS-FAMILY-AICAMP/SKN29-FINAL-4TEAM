"""Validate or atomically import the local-only reference catalogue."""

from __future__ import annotations

import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from local_apps.reference_cases.catalog import (
    DEFAULT_CATALOG_PATH,
    ReferenceCatalogError,
    load_reference_catalog,
)
from local_apps.reference_cases.importer import (
    ReferenceScenarioImportConflict,
    ReferenceScenarioImporter,
)


APPLY_ADVISORY_LOCK_ID = 8_102_026_083_101
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
LOCAL_DATABASE_PREFIX = "waterbridge_reference_cases_"
SQLITE_TEST_SETTINGS = {"config.settings.reference_cases_test"}


class Command(BaseCommand):
    help = (
        "Validate or atomically import 45 synthetic three-model reference "
        "scenarios into a dedicated local database."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--catalog",
            type=Path,
            default=DEFAULT_CATALOG_PATH,
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Commit the insert-only import; the default is rollback.",
        )
        parser.add_argument(
            "--confirm-database",
            type=str,
            help="Required for apply and must equal the connected DB name.",
        )
        parser.add_argument(
            "--confirm-system-identifier",
            type=str,
            help=(
                "Required for PostgreSQL and must equal pg_control_system() "
                "system_identifier for the dedicated local cluster."
            ),
        )

    def handle(self, *args, **options):
        del args
        try:
            catalog = load_reference_catalog(options["catalog"])
        except (OSError, ReferenceCatalogError) as exc:
            raise CommandError(str(exc)) from exc

        is_apply = bool(options["apply"])
        database_name = self._assert_local_database(
            options.get("confirm_system_identifier")
        )
        if is_apply:
            confirmed = str(options.get("confirm_database") or "")
            if confirmed != database_name:
                raise CommandError(
                    "--confirm-database must equal the connected database name."
                )

        try:
            with transaction.atomic():
                if connection.vendor == "postgresql":
                    self._acquire_apply_lock()
                result = ReferenceScenarioImporter.persist(catalog)
                if not is_apply:
                    transaction.set_rollback(True)
        except ReferenceScenarioImportConflict as exc:
            raise CommandError(str(exc)) from exc

        prefix = "APPLIED" if is_apply else "DRY_RUN_READY"
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix} database={database_name} "
                f"catalog={catalog.catalog_version} "
                f"records={result.records} created={result.created} "
                f"unchanged={result.unchanged} "
                f"sha256={catalog.catalog_sha256}"
            )
        )

    @staticmethod
    def _assert_local_database(expected_system_identifier: str | None) -> str:
        vendor = connection.vendor
        settings_dict = connection.settings_dict
        configured_name = str(settings_dict.get("NAME") or "")
        if vendor == "sqlite":
            if os.getenv("DJANGO_SETTINGS_MODULE") not in SQLITE_TEST_SETTINGS:
                raise CommandError(
                    "SQLite import is allowed only with the isolated "
                    "reference_cases_test settings profile."
                )
            return configured_name

        if vendor != "postgresql":
            raise CommandError(f"unsupported database vendor: {vendor}")
        configured_host = str(settings_dict.get("HOST") or "").lower()
        if configured_host not in LOOPBACK_HOSTS:
            raise CommandError("reference scenario import requires a loopback DB host.")
        if not configured_name.startswith(LOCAL_DATABASE_PREFIX):
            raise CommandError(
                "reference scenario import requires a dedicated local DB named "
                f"{LOCAL_DATABASE_PREFIX}*."
            )
        expected_identifier = str(expected_system_identifier or "").strip()
        if not expected_identifier:
            raise CommandError(
                "--confirm-system-identifier is required for PostgreSQL."
            )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_database(), "
                "system_identifier::text FROM pg_control_system()"
            )
            actual_name, actual_identifier = map(str, cursor.fetchone())
        if actual_name != configured_name:
            raise CommandError("configured and connected database names differ.")
        if actual_identifier != expected_identifier:
            raise CommandError(
                "--confirm-system-identifier does not match the connected "
                "PostgreSQL cluster."
            )
        return actual_name

    @staticmethod
    def _acquire_apply_lock() -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s)",
                [APPLY_ADVISORY_LOCK_ID],
            )
