"""Dry-run or atomically import the three-model 53-row evidence package."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.accounts.models import User
from apps.evidence.services.three_model_evidence_importer import (
    ThreeModelEvidenceImporter,
)


APPLY_ADVISORY_LOCK_ID = 8_102_026_081_907


class Command(BaseCommand):
    help = "Validate or atomically import the three-model 53-row evidence set."

    def add_arguments(self, parser):
        parser.add_argument("--identity-manifest", type=Path, required=True)
        parser.add_argument("--identity-sha256", type=str, required=True)
        parser.add_argument("--index-manifest", type=Path, required=True)
        parser.add_argument("--index-sha256", type=str, required=True)
        parser.add_argument("--embedding-fixture", type=Path, required=True)
        parser.add_argument("--embedding-fixture-sha256", type=str, required=True)
        parser.add_argument("--verified-by", type=str, required=True)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--confirm-database", type=str)

    def handle(self, *args, **options):
        del args
        importer = ThreeModelEvidenceImporter()
        package = importer.load_package(
            identity_path=options["identity_manifest"],
            identity_sha256=options["identity_sha256"],
            index_path=options["index_manifest"],
            index_sha256=options["index_sha256"],
            embedding_fixture_path=options["embedding_fixture"],
            embedding_fixture_sha256=options["embedding_fixture_sha256"],
        )
        verifier = self._resolve_verifier(options["verified_by"])
        is_apply = bool(options["apply"])
        if is_apply:
            self._confirm_database(options.get("confirm_database"))
        with transaction.atomic():
            if is_apply:
                self._acquire_apply_lock()
            result = importer.persist(package=package, verifier=verifier)
            if not is_apply:
                transaction.set_rollback(True)
        prefix = "APPLIED" if is_apply else "DRY_RUN_READY"
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix} chunks=53 models=15/19/19 "
                f"identity_sha256={package.identity_sha256} "
                f"index_sha256={package.index_sha256} "
                f"fixture_sha256={package.embedding_fixture_sha256} "
                f"{result.summary()}"
            )
        )

    @staticmethod
    def _resolve_verifier(username: str) -> User:
        try:
            return User.objects.get(
                username=username,
                role_code=User.Role.OPERATOR,
                is_active=True,
                is_synthetic=True,
            )
        except User.DoesNotExist as exc:
            raise CommandError(
                "--verified-by must reference an active synthetic OPERATOR."
            ) from exc

    @staticmethod
    def _confirm_database(expected_name: str | None) -> None:
        if connection.vendor != "postgresql":
            return
        if not expected_name:
            raise CommandError("--confirm-database is required for PostgreSQL apply.")
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            actual_name = str(cursor.fetchone()[0])
        if actual_name != expected_name:
            raise CommandError(
                "The connected PostgreSQL database does not match --confirm-database."
            )

    @staticmethod
    def _acquire_apply_lock() -> None:
        if connection.vendor != "postgresql":
            return
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [APPLY_ADVISORY_LOCK_ID])
