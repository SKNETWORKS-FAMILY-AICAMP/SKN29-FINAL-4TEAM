"""Process never-started HumanReview resume rows without automatic retry."""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.inquiries.services.human_review_resume_dispatch_service import (
    HumanReviewResumeDispatchService,
)


class Command(BaseCommand):
    help = "미전송 HumanReview AI 재개 Outbox를 민감값 출력 없이 처리합니다."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        del args
        result = HumanReviewResumeDispatchService.process_pending(
            max_rows=options["batch_size"]
        )
        if options["json"]:
            self.stdout.write(json.dumps(result, sort_keys=True))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "HumanReview resume outbox processed: "
                    f"{result['processed']}"
                )
            )
