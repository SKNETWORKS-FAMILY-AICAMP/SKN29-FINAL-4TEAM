"""P1 OTP Email Outbox 적재·전달 Service."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from apps.accounts.models import (
    ContractEmailContact,
    P1AuthEmailOutbox,
    P1AuthOtpChallenge,
)
from apps.accounts.services.p1_auth_email_service import P1AuthEmailService
from apps.accounts.services.contract_email_protection import (
    ContractEmailProtectionError,
)
from apps.accounts.services.p1_auth_otp_cipher import (
    P1AuthOtpCipher,
    P1AuthOtpCipherError,
)
from apps.accounts.services.p1_auth_target_service import P1AuthTargetService


class P1AuthEmailOutboxService:
    @staticmethod
    def scrub_expired_local_email_files() -> int:
        """로컬 파일 EmailBackend의 OTP 원문을 TTL 뒤 안전하게 지운다."""

        if (
            settings.EMAIL_BACKEND
            != "django.core.mail.backends.filebased.EmailBackend"
        ):
            return 0
        configured = getattr(settings, "EMAIL_FILE_PATH", None)
        if configured is None:
            return 0
        runtime_root = (Path(settings.BASE_DIR) / ".runtime").resolve()
        email_root = Path(configured).resolve()
        try:
            email_root.relative_to(runtime_root)
        except ValueError:
            return 0
        if not email_root.name.startswith("p1-auth-emails"):
            return 0

        cutoff = (
            timezone.now()
            - timedelta(seconds=settings.P1_AUTH_OTP_TTL_SECONDS)
        ).timestamp()
        removed = 0
        try:
            candidates = list(email_root.iterdir())
        except OSError:
            return 0
        for candidate in candidates:
            try:
                if candidate.is_file() and candidate.stat().st_mtime <= cutoff:
                    candidate.unlink(missing_ok=True)
                    removed += 1
            except OSError:
                continue
        return removed

    @classmethod
    def enqueue(
        cls,
        *,
        challenge: P1AuthOtpChallenge,
        contact: ContractEmailContact | None,
        otp_code: str,
    ) -> P1AuthEmailOutbox:
        if not challenge.target_resolved or contact is None:
            return P1AuthEmailOutbox.objects.create(
                challenge=challenge,
                contact=None,
                encrypted_otp="",
                status=P1AuthEmailOutbox.Status.SUPPRESSED,
                last_error_code="TARGET_UNRESOLVED",
            )
        encrypted = P1AuthOtpCipher.from_settings().encrypt(otp_code)
        return P1AuthEmailOutbox.objects.create(
            challenge=challenge,
            contact=contact,
            encrypted_otp=encrypted,
        )

    @classmethod
    def process_pending(cls, *, max_rows: int = 100) -> dict[str, int]:
        counts = {"processed": 0, "sent": 0, "failed": 0, "suppressed": 0}
        for _ in range(max(1, int(max_rows))):
            outcome = cls._process_one()
            if outcome is None:
                break
            counts["processed"] += 1
            counts[outcome] += 1
        return counts

    @classmethod
    @transaction.atomic
    def _process_one(cls) -> str | None:
        now = timezone.now()
        row = (
            P1AuthEmailOutbox.objects.select_for_update(
                skip_locked=True,
                of=("self",),
            )
            .filter(
                status=P1AuthEmailOutbox.Status.PENDING,
                available_at__lte=now,
                attempt_count__lt=models.F("max_attempts"),
            )
            .select_related("challenge", "contact")
            .order_by("created_at", "pk")
            .first()
        )
        if row is None:
            return None
        row.attempt_count += 1
        row.challenge.delivery_attempted = True
        row.challenge.save(update_fields=["delivery_attempted", "updated_at"])

        challenge_state_usable = (
            row.challenge.target_resolved
            and row.challenge.consumed_at is None
            and row.challenge.verified_at is None
            and row.challenge.expires_at > now
            and row.challenge.failure_count < row.challenge.max_failures
        )
        current_target = (
            P1AuthTargetService.lock_current(row.challenge)
            if challenge_state_usable
            else None
        )
        contact_usable = (
            row.contact is not None
            and current_target is not None
            and row.challenge.contact_id == row.contact_id
            and current_target.contact.pk == row.contact_id
        )
        if not challenge_state_usable or not contact_usable:
            row.status = P1AuthEmailOutbox.Status.SUPPRESSED
            row.encrypted_otp = ""
            row.last_error_code = "CHALLENGE_NOT_DELIVERABLE"
            row.save(
                update_fields=[
                    "attempt_count",
                    "status",
                    "encrypted_otp",
                    "last_error_code",
                    "updated_at",
                ]
            )
            return "suppressed"

        assert current_target is not None
        try:
            otp_code = P1AuthOtpCipher.from_settings().decrypt(row.encrypted_otp)
            delivered = P1AuthEmailService.deliver_otp(
                challenge=row.challenge,
                contact=current_target.contact,
                otp_code=otp_code,
            )
        except (ContractEmailProtectionError, P1AuthOtpCipherError):
            delivered = False
            row.last_error_code = "PROTECTED_DELIVERY_DATA_INVALID"
        else:
            row.last_error_code = "" if delivered else "DELIVERY_FAILED"

        if delivered:
            row.status = P1AuthEmailOutbox.Status.SENT
            row.sent_at = now
            row.encrypted_otp = ""
            outcome = "sent"
        elif row.attempt_count >= row.max_attempts:
            row.status = P1AuthEmailOutbox.Status.FAILED
            row.encrypted_otp = ""
            outcome = "failed"
        else:
            row.available_at = now + timedelta(seconds=30 * row.attempt_count)
            outcome = "failed"
        row.save(
            update_fields=[
                "attempt_count",
                "status",
                "available_at",
                "sent_at",
                "encrypted_otp",
                "last_error_code",
                "updated_at",
            ]
        )
        return outcome
