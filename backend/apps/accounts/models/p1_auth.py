"""P1 고객 이메일 OTP 인증·단회성 Ticket·동의 원장."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.accounts.models.contract_email_contact import ContractEmailContact
from apps.accounts.models.customer_profile import CustomerProfile
from common.models.base import TimestampedModel


class P1AuthOtpChallenge(TimestampedModel):
    """OTP 원문 없이 인증 상태와 실패 횟수만 보존한다."""

    class Purpose(models.TextChoices):
        SIGNUP = "SIGNUP", "회원가입"
        USERNAME_RECOVERY = "USERNAME_RECOVERY", "아이디 찾기"
        PASSWORD_RESET = "PASSWORD_RESET", "비밀번호 재설정"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="p1_auth_challenges",
    )
    contact = models.ForeignKey(
        ContractEmailContact,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="p1_auth_challenges",
    )
    subscription = models.ForeignKey(
        "subscriptions.CustomerSubscription",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="p1_auth_challenges",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="p1_auth_challenges",
    )
    target_resolved = models.BooleanField(default=False)
    idempotency_key_hmac = models.CharField(max_length=64)
    request_fingerprint_hmac = models.CharField(max_length=64)
    otp_digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    resend_not_before = models.DateTimeField()
    failure_count = models.PositiveSmallIntegerField(default=0)
    max_failures = models.PositiveSmallIntegerField(default=5)
    verified_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    delivery_attempted = models.BooleanField(default=False)
    data_classification = models.CharField(
        max_length=20,
        default="synthetic",
        editable=False,
    )

    class Meta:
        db_table = "accounts_p1_auth_otp_challenge"
        constraints = [
            models.UniqueConstraint(
                fields=["purpose", "idempotency_key_hmac"],
                name="ux_p1_otp_purpose_idem_hmac",
            ),
            models.CheckConstraint(
                condition=Q(data_classification="synthetic"),
                name="ck_p1_otp_synthetic_only",
            ),
            models.CheckConstraint(
                condition=Q(max_failures__gte=1),
                name="ck_p1_otp_max_failures_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(failure_count__lte=F("max_failures")),
                name="ck_p1_otp_failures_lte_max",
            ),
        ]
        indexes = [
            models.Index(
                fields=["purpose", "request_fingerprint_hmac", "created_at"],
                name="ix_p1_otp_request_created",
            ),
            models.Index(fields=["expires_at"], name="ix_p1_otp_expires"),
        ]

    def clean(self) -> None:
        super().clean()
        linked = bool(self.customer_id and self.contact_id)
        if self.target_resolved != linked:
            raise ValidationError(
                {"target_resolved": "확인된 대상에는 고객과 연락처가 필요합니다."}
            )
        if self.contact_id and self.contact.customer_id != self.customer_id:
            raise ValidationError({"contact": "고객과 계약 연락처가 일치해야 합니다."})
        if (
            self.subscription_id
            and self.subscription.customer_id != self.customer_id
        ):
            raise ValidationError({"subscription": "고객과 계약이 일치해야 합니다."})
        if self.user_id and self.customer_id:
            if not self.customer.account_links.filter(
                user_id=self.user_id,
                is_active=True,
            ).exists():
                raise ValidationError({"user": "활성 고객 계정 연결이 필요합니다."})
        if self.data_classification != "synthetic":
            raise ValidationError(
                {"data_classification": "합성 데이터만 허용합니다."}
            )

    @property
    def is_usable(self) -> bool:
        now = timezone.now()
        return (
            self.target_resolved
            and self.consumed_at is None
            and self.verified_at is None
            and self.expires_at > now
            and self.failure_count < self.max_failures
        )


class P1AuthTicket(TimestampedModel):
    """응답 원문은 저장하지 않고 HMAC digest만 저장하는 단회성 Ticket."""

    class Purpose(models.TextChoices):
        CLAIM = "CLAIM", "회원가입 Claim"
        PASSWORD_RESET = "PASSWORD_RESET", "비밀번호 재설정"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    purpose = models.CharField(max_length=24, choices=Purpose.choices)
    digest = models.CharField(max_length=64, unique=True)
    challenge = models.OneToOneField(
        P1AuthOtpChallenge,
        on_delete=models.PROTECT,
        related_name="ticket",
    )
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.PROTECT,
        related_name="p1_auth_tickets",
    )
    auth_version_at_issue = models.PositiveIntegerField(
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="p1_auth_tickets",
    )
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    data_classification = models.CharField(
        max_length=20,
        default="synthetic",
        editable=False,
    )

    class Meta:
        db_table = "accounts_p1_auth_ticket"
        constraints = [
            models.CheckConstraint(
                condition=Q(data_classification="synthetic"),
                name="ck_p1_ticket_synthetic_only",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        purpose="CLAIM",
                        user__isnull=True,
                        auth_version_at_issue__isnull=True,
                    )
                    | Q(
                        purpose="PASSWORD_RESET",
                        user__isnull=False,
                        auth_version_at_issue__gte=1,
                    )
                ),
                name="ck_p1_ticket_purpose_binding",
            ),
        ]
        indexes = [models.Index(fields=["expires_at"], name="ix_p1_ticket_expires")]

    def clean(self) -> None:
        super().clean()
        if self.challenge_id and self.challenge.customer_id != self.customer_id:
            raise ValidationError({"customer": "Challenge 고객과 일치해야 합니다."})
        if self.purpose == self.Purpose.PASSWORD_RESET and not self.user_id:
            raise ValidationError({"user": "재설정 Ticket에는 사용자가 필요합니다."})
        if (
            self.purpose == self.Purpose.PASSWORD_RESET
            and not self.auth_version_at_issue
        ):
            raise ValidationError(
                {"auth_version_at_issue": "재설정 Ticket에는 인증 버전이 필요합니다."}
            )
        if self.purpose == self.Purpose.CLAIM and self.user_id:
            raise ValidationError({"user": "가입 전 Claim에는 사용자가 없어야 합니다."})
        if (
            self.purpose == self.Purpose.CLAIM
            and self.auth_version_at_issue is not None
        ):
            raise ValidationError(
                {"auth_version_at_issue": "가입 Claim에는 인증 버전이 없어야 합니다."}
            )


class P1AuthChallengeRateBucket(TimestampedModel):
    """동일 인증대상의 동시 OTP 발급 제한을 직렬화한다."""

    id = models.BigAutoField(primary_key=True)
    purpose = models.CharField(
        max_length=32,
        choices=P1AuthOtpChallenge.Purpose.choices,
    )
    request_fingerprint_hmac = models.CharField(max_length=64)
    window_started_at = models.DateTimeField(default=timezone.now)
    request_count = models.PositiveIntegerField(default=0)
    last_requested_at = models.DateTimeField(null=True, blank=True)
    data_classification = models.CharField(
        max_length=20,
        default="synthetic",
        editable=False,
    )

    class Meta:
        db_table = "accounts_p1_auth_challenge_rate_bucket"
        constraints = [
            models.UniqueConstraint(
                fields=["purpose", "request_fingerprint_hmac"],
                name="ux_p1_challenge_rate_subject",
            ),
            models.CheckConstraint(
                condition=Q(data_classification="synthetic"),
                name="ck_p1_challenge_rate_synthetic",
            ),
        ]


class P1AccountConsent(TimestampedModel):
    """회원가입 시점의 약관별 동의 버전을 보존한다."""

    class Code(models.TextChoices):
        TERMS_OF_SERVICE = "TERMS_OF_SERVICE", "이용약관"
        PRIVACY_COLLECTION_USE = "PRIVACY_COLLECTION_USE", "개인정보 수집 이용"
        MARKETING = "MARKETING", "마케팅"

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="p1_account_consents",
    )
    code = models.CharField(max_length=40, choices=Code.choices)
    version = models.CharField(max_length=40)
    agreed = models.BooleanField()
    recorded_at = models.DateTimeField(default=timezone.now)
    data_classification = models.CharField(
        max_length=20,
        default="synthetic",
        editable=False,
    )

    class Meta:
        db_table = "accounts_p1_account_consent"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "code", "version"],
                name="ux_p1_consent_user_code_version",
            ),
            models.CheckConstraint(
                condition=Q(data_classification="synthetic"),
                name="ck_p1_consent_synthetic_only",
            ),
        ]


class P1AuthOperationReceipt(TimestampedModel):
    """민감 응답을 저장하지 않는 가입·재설정 Idempotency 원장."""

    class Operation(models.TextChoices):
        SIGNUP = "SIGNUP", "회원가입"
        PASSWORD_RESET = "PASSWORD_RESET", "비밀번호 재설정"

    id = models.BigAutoField(primary_key=True)
    operation = models.CharField(max_length=24, choices=Operation.choices)
    idempotency_key_hmac = models.CharField(max_length=64)
    request_fingerprint_hmac = models.CharField(max_length=64)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="p1_auth_operation_receipts",
    )
    auth_version_at_completion = models.PositiveIntegerField(default=1)
    completed_at = models.DateTimeField(default=timezone.now)
    data_classification = models.CharField(
        max_length=20,
        default="synthetic",
        editable=False,
    )

    class Meta:
        db_table = "accounts_p1_auth_operation_receipt"
        constraints = [
            models.UniqueConstraint(
                fields=["operation", "idempotency_key_hmac"],
                name="ux_p1_receipt_operation_idem",
            ),
            models.CheckConstraint(
                condition=Q(data_classification="synthetic"),
                name="ck_p1_receipt_synthetic_only",
            ),
            models.CheckConstraint(
                condition=Q(auth_version_at_completion__gte=1),
                name="ck_p1_receipt_auth_version_gte_1",
            ),
        ]


class P1AuthIdempotencyLock(TimestampedModel):
    """가입·재설정 Idempotency-Key별 동시 실행을 직렬화한다."""

    id = models.BigAutoField(primary_key=True)
    operation = models.CharField(
        max_length=24,
        choices=P1AuthOperationReceipt.Operation.choices,
    )
    idempotency_key_hmac = models.CharField(max_length=64)
    data_classification = models.CharField(
        max_length=20,
        default="synthetic",
        editable=False,
    )

    class Meta:
        db_table = "accounts_p1_auth_idempotency_lock"
        constraints = [
            models.UniqueConstraint(
                fields=["operation", "idempotency_key_hmac"],
                name="ux_p1_idempotency_lock_key",
            ),
            models.CheckConstraint(
                condition=Q(data_classification="synthetic"),
                name="ck_p1_idempotency_lock_synthetic",
            ),
        ]


class P1AuthRateLimitEvent(models.Model):
    """원문 식별자를 배제한 DB 기반 인증 시도 제한 이벤트."""

    class Action(models.TextChoices):
        LOGIN_FAILURE = "LOGIN_FAILURE", "로그인 실패"

    id = models.BigAutoField(primary_key=True)
    action = models.CharField(max_length=24, choices=Action.choices)
    subject_hmac = models.CharField(max_length=64)
    occurred_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "accounts_p1_auth_rate_limit_event"
        indexes = [
            models.Index(
                fields=["action", "subject_hmac", "occurred_at"],
                name="ix_p1_rate_subject_time",
            )
        ]


class P1AuthLoginRateBucket(TimestampedModel):
    """동일 아이디의 동시 로그인 실패 제한을 직렬화한다."""

    id = models.BigAutoField(primary_key=True)
    subject_hmac = models.CharField(max_length=64, unique=True)
    window_started_at = models.DateTimeField(default=timezone.now)
    failure_count = models.PositiveIntegerField(default=0)
    last_failed_at = models.DateTimeField(null=True, blank=True)
    data_classification = models.CharField(
        max_length=20,
        default="synthetic",
        editable=False,
    )

    class Meta:
        db_table = "accounts_p1_auth_login_rate_bucket"
        constraints = [
            models.CheckConstraint(
                condition=Q(data_classification="synthetic"),
                name="ck_p1_login_rate_synthetic",
            )
        ]


class P1AuthEmailOutbox(TimestampedModel):
    """API 응답과 SMTP 전달을 분리하는 합성 OTP Outbox."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "전송 대기"
        SENT = "SENT", "전송 완료"
        FAILED = "FAILED", "전송 실패"
        SUPPRESSED = "SUPPRESSED", "대상 없음"

    id = models.BigAutoField(primary_key=True)
    challenge = models.OneToOneField(
        P1AuthOtpChallenge,
        on_delete=models.PROTECT,
        related_name="email_outbox",
    )
    contact = models.ForeignKey(
        ContractEmailContact,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="p1_auth_email_outbox_rows",
    )
    encrypted_otp = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    attempt_count = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    available_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=40, blank=True)
    data_classification = models.CharField(
        max_length=20,
        default="synthetic",
        editable=False,
    )

    class Meta:
        db_table = "accounts_p1_auth_email_outbox"
        constraints = [
            models.CheckConstraint(
                condition=Q(data_classification="synthetic"),
                name="ck_p1_email_outbox_synthetic_only",
            ),
            models.CheckConstraint(
                condition=Q(max_attempts__gte=1),
                name="ck_p1_email_outbox_max_attempts",
            ),
            models.CheckConstraint(
                condition=Q(attempt_count__lte=F("max_attempts")),
                name="ck_p1_email_outbox_attempts_lte_max",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="PENDING",
                        encrypted_otp__gt="",
                        sent_at__isnull=True,
                        attempt_count__lt=F("max_attempts"),
                    )
                    | Q(
                        status="SENT",
                        encrypted_otp="",
                        sent_at__isnull=False,
                        attempt_count__gte=1,
                    )
                    | Q(
                        status="FAILED",
                        encrypted_otp="",
                        sent_at__isnull=True,
                        attempt_count=F("max_attempts"),
                    )
                    | Q(
                        status="SUPPRESSED",
                        encrypted_otp="",
                        sent_at__isnull=True,
                    )
                ),
                name="ck_p1_email_outbox_state",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "available_at"],
                name="ix_p1_email_outbox_pending",
            )
        ]
