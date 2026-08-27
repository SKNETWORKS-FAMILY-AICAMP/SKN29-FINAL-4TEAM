"""Read-only preflight for the AWS NONPROD OTP worker boundary."""

from __future__ import annotations

import re
import sys


HMAC_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _enabled(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _allowlist(value: object) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set, frozenset)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def main() -> int:
    stage = "DJANGO_SETUP"
    try:
        import django

        django.setup()

        from django.conf import settings
        from django.db.models import F
        from django.utils import timezone

        from apps.accounts.models import (
            ContractEmailContact,
            P1AuthEmailOutbox,
        )

        stage = "BACKEND_OWNER_GATE"
        required_settings = (
            "P1_AUTH_RUNTIME_ENVIRONMENT",
            "P1_AUTH_APPROVED_TEST_RECIPIENT_DELIVERY_ENABLED",
            "P1_AUTH_APPROVED_TEST_RECIPIENT_ALLOWLIST_HMACS",
        )
        if any(not hasattr(settings, name) for name in required_settings):
            print("BACKEND_OWNER_WAIT", file=sys.stderr)
            return 1
        if settings.DEBUG is not False:
            raise RuntimeError("DEBUG must remain disabled")
        if settings.P1_AUTH_RUNTIME_ENVIRONMENT != "AWS_NONPROD":
            raise RuntimeError("unexpected P1 auth runtime environment")
        if not _enabled(
            settings.P1_AUTH_APPROVED_TEST_RECIPIENT_DELIVERY_ENABLED
        ):
            raise RuntimeError("approved recipient delivery is disabled")

        approved_hmacs = _allowlist(
            settings.P1_AUTH_APPROVED_TEST_RECIPIENT_ALLOWLIST_HMACS
        )
        if (
            len(approved_hmacs) != 6
            or len(set(approved_hmacs)) != 6
            or any(not HMAC_PATTERN.fullmatch(item) for item in approved_hmacs)
        ):
            raise RuntimeError("approved recipient allowlist is invalid")

        stage = "PENDING_OUTBOX_BOUNDARY"
        now = timezone.now()
        pending_deliverable = P1AuthEmailOutbox.objects.filter(
            status=P1AuthEmailOutbox.Status.PENDING,
            available_at__lte=now,
            attempt_count__lt=F("max_attempts"),
            contact__isnull=False,
            contact__delivery_policy=(
                ContractEmailContact.DeliveryPolicy.APPROVED_TEST_RECIPIENT
            ),
            contact__data_classification=(
                ContractEmailContact.DataClassification.APPROVED_TEST_PII
            ),
            challenge__target_resolved=True,
            challenge__consumed_at__isnull=True,
            challenge__verified_at__isnull=True,
            challenge__expires_at__gt=now,
            challenge__failure_count__lt=F("challenge__max_failures"),
        ).count()
        if pending_deliverable != 0:
            raise RuntimeError("unexpected deliverable pending outbox rows")
    except Exception as exc:
        print(
            "P1_AUTH_EMAIL_WORKER_PREFLIGHT_FAILED "
            f"reason={stage} error_type={type(exc).__name__}",
            file=sys.stderr,
        )
        return 1

    print("P1_AUTH_EMAIL_WORKER_PREFLIGHT_PASS")
    print("runtime_environment=AWS_NONPROD")
    print("debug=false")
    print("approved_hmac_count=6")
    print("pending_deliverable=0")
    print("secret_values_printed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
