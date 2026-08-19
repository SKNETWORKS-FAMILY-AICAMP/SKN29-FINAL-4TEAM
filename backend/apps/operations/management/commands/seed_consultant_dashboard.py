"""Seed the local consultant dashboard with deterministic synthetic data."""

from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from apps.operations.repositories import SyntheticImportConflict
from apps.operations.services import ConsultantDashboardSeedService


class Command(BaseCommand):
    """Create or reconcile the namespaced local dashboard dataset."""

    help = (
        "Seed 90 assigned synthetic inquiries, staff contacts, and notices "
        "for the local consultant dashboard."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run every write and verification step, then roll it back.",
        )

    def handle(self, *args, **options) -> str:
        try:
            result = ConsultantDashboardSeedService().run(
                dry_run=options["dry_run"]
            )
        except (
            SyntheticImportConflict,
            ValidationError,
            IntegrityError,
        ) as exc:
            raise CommandError(
                f"Consultant dashboard seed aborted: {exc}"
            ) from exc

        payload = json.dumps(
            result.as_dict(),
            ensure_ascii=False,
            sort_keys=True,
        )
        return payload
