"""Import the canonical synthetic handoff into backend domain models."""

from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from apps.operations.repositories import SyntheticImportConflict
from apps.operations.services import (
    SyntheticHandoffImportService,
)


class Command(BaseCommand):
    """Run one atomic handoff or product-expansion import."""

    help = (
        "Import the canonical synthetic handoff or the isolated two-product "
        "expansion with strict identifier and post-import verification."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--profile",
            choices=(
                "smoke",
                "full",
                "db-smoke",
                "db-full",
                "db-product-expansion",
            ),
            required=True,
            help=(
                "Select the exact 37-row smoke, 367-row full closure, or "
                "isolated two-product expansion."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Execute every import and verification step, then roll "
                "back all domain and ledger writes."
            ),
        )

    def handle(self, *args, **options) -> str:
        try:
            result = SyntheticHandoffImportService().run(
                profile=options["profile"],
                dry_run=options["dry_run"],
            )
        except (
            SyntheticImportConflict,
            ValidationError,
            IntegrityError,
        ) as exc:
            raise CommandError(
                f"Synthetic handoff import aborted: {exc}"
            ) from exc

        payload = json.dumps(
            result.as_dict(),
            ensure_ascii=False,
            sort_keys=True,
        )
        return payload
