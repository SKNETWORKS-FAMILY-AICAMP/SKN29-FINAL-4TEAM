"""P1 OTP Email Outbox worker."""

from __future__ import annotations

import json
import time

from django.core.management.base import BaseCommand

from apps.accounts.services.p1_auth_email_outbox_service import (
    P1AuthEmailOutboxService,
)


class Command(BaseCommand):
    help = "P1 OTP Email Outbox를 민감값 출력 없이 처리합니다."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--poll-seconds", type=float, default=1.0)
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        del args
        while True:
            result = P1AuthEmailOutboxService.process_pending(
                max_rows=options["batch_size"]
            )
            result["local_email_files_scrubbed"] = (
                P1AuthEmailOutboxService.scrub_expired_local_email_files()
            )
            if options["json"]:
                self.stdout.write(json.dumps(result, sort_keys=True))
            if options["once"]:
                return
            time.sleep(max(0.2, float(options["poll_seconds"])))
