"""Seed the local consultant dashboard with deterministic synthetic data."""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.operations.repositories import SyntheticImportConflict
from apps.operations.services import ConsultantDashboardSeedService


BUSINESS_TIMEZONE = ZoneInfo("Asia/Seoul")


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
        parser.add_argument(
            "--reference-at",
            help=(
                "Anchor synthetic inquiry timestamps to this ISO-8601 "
                "date-time. A timezone-less value is interpreted as "
                "Asia/Seoul. Reuse the same value for an idempotent replay."
            ),
        )

    def handle(self, *args, **options) -> str:
        reference_at = self._parse_reference_at(options["reference_at"])
        try:
            result = ConsultantDashboardSeedService(
                inquiry_reference_at=reference_at
            ).run(
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

    @staticmethod
    def _parse_reference_at(value: str | None) -> datetime | None:
        if value is None:
            return None
        parsed = parse_datetime(value)
        if parsed is None:
            raise CommandError(
                "--reference-at must be an ISO-8601 date-time."
            )
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, BUSINESS_TIMEZONE)
        return parsed
