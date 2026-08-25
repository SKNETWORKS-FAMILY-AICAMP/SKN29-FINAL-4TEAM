"""P1 계약고객 OTP 회원가입·로그인·계정복구 Runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.accounts.models import (
    AccountAuditEvent,
    ContractEmailContact,
    CustomerAccountLink,
    CustomerProfile,
    P1AccountConsent,
    P1AuthChallengeRateBucket,
    P1AuthOperationReceipt,
    P1AuthIdempotencyLock,
    P1AuthLoginRateBucket,
    P1AuthOtpChallenge,
    P1AuthRateLimitEvent,
    P1AuthTicket,
    User,
)
from apps.accounts.services.authentication_service import (
    AuthenticationService,
    TokenPair,
)
from apps.accounts.services.contract_email_protection import (
    ContractEmailProtectionError,
    ContractEmailProtectionService,
)
from apps.accounts.services.p1_auth_crypto import P1AuthCrypto
from apps.accounts.services.p1_auth_email_outbox_service import (
    P1AuthEmailOutboxService,
)
from apps.accounts.services.p1_auth_target_service import (
    CurrentAuthTarget,
    P1AuthTargetService,
)
from apps.subscriptions.models import CustomerSubscription
from common.exceptions.base import BackendError
from common.exceptions.error_codes import DUPLICATE_EVENT, INVALID_REQUEST


AUTH_VERIFICATION_FAILED = "AUTH_VERIFICATION_FAILED"
AUTH_LOGIN_FAILED = "AUTH_LOGIN_FAILED"
AUTH_IDENTIFIER_UNAVAILABLE = "AUTH_IDENTIFIER_UNAVAILABLE"
AUTH_SIGNUP_CONFLICT = "AUTH_SIGNUP_CONFLICT"
AUTH_RATE_LIMITED = "AUTH_RATE_LIMITED"

CHALLENGE_MESSAGE = "등록된 계약 연락처가 확인되면 인증번호가 발송됩니다."
DUMMY_PASSWORD_HASH = make_password("waterbridge-p1-dummy-password")


@dataclass(frozen=True)
class ResolvedTarget:
    customer: CustomerProfile
    contact: ContractEmailContact
    user: User | None
    subscription: CustomerSubscription | None


@dataclass(frozen=True)
class SignupResult:
    user: User
    pair: TokenPair
    idempotent_replay: bool


class P1AuthService:
    """민감 원문을 영속·로그에 남기지 않는 인증 업무 경계."""

    @staticmethod
    def _verification_failed() -> BackendError:
        return BackendError(
            AUTH_VERIFICATION_FAILED,
            "인증정보를 확인할 수 없습니다. 처음부터 다시 시도해 주세요.",
            status_code=401,
        )

    @staticmethod
    def _rate_limited(retry_after: int) -> BackendError:
        seconds = max(1, int(retry_after))
        return BackendError(
            AUTH_RATE_LIMITED,
            "요청 횟수를 초과했습니다. 안내된 시간 후 다시 시도해 주세요.",
            details={"retry_after_seconds": seconds},
            status_code=429,
            headers={"Retry-After": str(seconds)},
        )

    @staticmethod
    def _idempotency_key(value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized or len(normalized) > 128:
            raise BackendError(
                INVALID_REQUEST,
                "Idempotency-Key 헤더를 확인해 주세요.",
                status_code=400,
            )
        return normalized

    @classmethod
    def _identity_fingerprint(
        cls,
        crypto: P1AuthCrypto,
        identity: dict[str, str],
    ) -> str:
        canonical = {
            key: (
                crypto.normalize_username(value)
                if key in {"email", "username"}
                else crypto.normalize_text(value)
            )
            for key, value in identity.items()
            if value
        }
        return crypto.fingerprint("challenge-request", canonical)

    @classmethod
    def _resolve_target(
        cls,
        *,
        identity: dict[str, str],
        purpose: str,
    ) -> ResolvedTarget | None:
        contacts = ContractEmailContact.objects.filter(
            is_active=True,
            is_primary=True,
            data_classification="synthetic",
            customer__is_synthetic=True,
            customer__deleted_at__isnull=True,
        ).select_related("customer")

        eligible_subscriptions = CustomerSubscription.objects.filter(
            customer_id=OuterRef("customer_id"),
            status_code=CustomerSubscription.Status.ACTIVE,
        )

        if identity.get("customer_number"):
            eligible_subscriptions = eligible_subscriptions.filter(
                contract_no=identity["contract_number"]
            )
            contacts = contacts.filter(
                customer__customer_no=identity["customer_number"],
            )
        else:
            try:
                protected = ContractEmailProtectionService.from_settings().protect(
                    identity["email"]
                )
            except ContractEmailProtectionError:
                return None
            contacts = contacts.filter(
                email_lookup_hmac=protected.email_lookup_hmac,
                customer__customer_name=identity["name"],
            )

        matches = list(
            contacts.annotate(
                has_eligible_subscription=Exists(eligible_subscriptions)
            ).filter(has_eligible_subscription=True)[:2]
        )
        if len(matches) != 1:
            return None
        contact = matches[0]
        customer = contact.customer
        subscription = None
        if identity.get("customer_number"):
            subscription = CustomerSubscription.objects.filter(
                customer=customer,
                contract_no=identity["contract_number"],
                status_code=CustomerSubscription.Status.ACTIVE,
            ).first()
            if subscription is None:
                return None
        link = (
            CustomerAccountLink.objects.filter(
                customer=customer,
                is_active=True,
                user__is_active=True,
                user__role_code=User.Role.CUSTOMER,
                user__is_synthetic=True,
            )
            .select_related("user")
            .first()
        )

        if purpose == P1AuthOtpChallenge.Purpose.SIGNUP:
            if customer.user_id is not None or link is not None:
                return None
            return ResolvedTarget(
                customer=customer,
                contact=contact,
                user=None,
                subscription=subscription,
            )

        if link is None or customer.user_id != link.user_id:
            return None
        if identity.get("username") and (
            link.user.username.casefold() != identity["username"].casefold()
        ):
            return None
        return ResolvedTarget(
            customer=customer,
            contact=contact,
            user=link.user,
            subscription=subscription,
        )

    @classmethod
    def _lock_current_challenge_target(
        cls,
        challenge: P1AuthOtpChallenge,
    ) -> CurrentAuthTarget | None:
        del cls
        return P1AuthTargetService.lock_current(challenge)

    @classmethod
    def create_challenge(
        cls,
        *,
        purpose: str,
        identity: dict[str, str],
        idempotency_key: str,
    ) -> dict[str, Any]:
        crypto = P1AuthCrypto.from_settings()
        normalized_key = cls._idempotency_key(idempotency_key)
        idem_hmac = crypto.digest("idempotency-key", normalized_key)
        fingerprint = cls._identity_fingerprint(crypto, identity)
        now = timezone.now()

        try:
            with transaction.atomic():
                existing = (
                    P1AuthOtpChallenge.objects.select_for_update(of=("self",))
                    .filter(purpose=purpose, idempotency_key_hmac=idem_hmac)
                    .first()
                )
                if existing is not None:
                    return cls._replay_challenge(
                        challenge=existing,
                        fingerprint=fingerprint,
                        crypto=crypto,
                    )

                bucket, _ = P1AuthChallengeRateBucket.objects.get_or_create(
                    purpose=purpose,
                    request_fingerprint_hmac=fingerprint,
                    defaults={"window_started_at": now},
                )
                bucket = P1AuthChallengeRateBucket.objects.select_for_update(
                    of=("self",)
                ).get(pk=bucket.pk)
                # 같은 fingerprint/key 동시 retry의 패자는 bucket lock을
                # 기다린 뒤 승자가 만든 challenge를 동일 응답으로 재사용한다.
                existing = P1AuthOtpChallenge.objects.filter(
                    purpose=purpose,
                    idempotency_key_hmac=idem_hmac,
                ).first()
                if existing is not None:
                    return cls._replay_challenge(
                        challenge=existing,
                        fingerprint=fingerprint,
                        crypto=crypto,
                    )
                window = timedelta(
                    hours=settings.P1_AUTH_CHALLENGE_WINDOW_HOURS
                )
                if bucket.window_started_at <= now - window:
                    bucket.window_started_at = now
                    bucket.request_count = 0
                    bucket.last_requested_at = None
                if (
                    bucket.last_requested_at is not None
                    and bucket.last_requested_at
                    + timedelta(seconds=settings.P1_AUTH_OTP_RESEND_SECONDS)
                    > now
                ):
                    retry_after = (
                        bucket.last_requested_at
                        + timedelta(seconds=settings.P1_AUTH_OTP_RESEND_SECONDS)
                        - now
                    ).total_seconds()
                    raise cls._rate_limited(int(retry_after) + 1)
                if (
                    bucket.request_count
                    >= settings.P1_AUTH_CHALLENGE_MAX_PER_WINDOW
                ):
                    raise cls._rate_limited(3600)

                target = cls._resolve_target(identity=identity, purpose=purpose)
                otp_code = crypto.generate_otp()
                challenge = P1AuthOtpChallenge(
                    purpose=purpose,
                    customer=target.customer if target else None,
                    contact=target.contact if target else None,
                    subscription=target.subscription if target else None,
                    user=target.user if target else None,
                    target_resolved=target is not None,
                    idempotency_key_hmac=idem_hmac,
                    request_fingerprint_hmac=fingerprint,
                    otp_digest="0" * 64,
                    expires_at=now
                    + timedelta(seconds=settings.P1_AUTH_OTP_TTL_SECONDS),
                    resend_not_before=now
                    + timedelta(seconds=settings.P1_AUTH_OTP_RESEND_SECONDS),
                    max_failures=settings.P1_AUTH_OTP_MAX_FAILURES,
                )
                challenge.otp_digest = crypto.otp_digest(
                    str(challenge.public_id),
                    purpose,
                    otp_code,
                )
                challenge.full_clean()
                challenge.save()

                P1AuthOtpChallenge.objects.filter(
                    purpose=purpose,
                    request_fingerprint_hmac=fingerprint,
                    consumed_at__isnull=True,
                ).exclude(pk=challenge.pk).update(consumed_at=now)

                P1AuthEmailOutboxService.enqueue(
                    challenge=challenge,
                    contact=target.contact if target is not None else None,
                    otp_code=otp_code,
                )
                bucket.request_count += 1
                bucket.last_requested_at = now
                bucket.save(
                    update_fields=[
                        "window_started_at",
                        "request_count",
                        "last_requested_at",
                        "updated_at",
                    ]
                )
        except IntegrityError:
            # 동시 요청 둘이 모두 "없음"을 본 경우 Unique 제약의 승자만
            # 남는다. 패자는 커밋된 동일 요청만 재조회해 같은 응답을 준다.
            existing = P1AuthOtpChallenge.objects.filter(
                purpose=purpose,
                idempotency_key_hmac=idem_hmac,
            ).first()
            if existing is None:
                raise
            return cls._replay_challenge(
                challenge=existing,
                fingerprint=fingerprint,
                crypto=crypto,
            )

        return cls._challenge_data(challenge)

    @classmethod
    def _replay_challenge(
        cls,
        *,
        challenge: P1AuthOtpChallenge,
        fingerprint: str,
        crypto: P1AuthCrypto,
    ) -> dict[str, Any]:
        if not crypto.compare(
            challenge.request_fingerprint_hmac,
            fingerprint,
        ):
            raise BackendError(
                DUPLICATE_EVENT,
                "동일 Idempotency-Key가 다른 요청에 재사용되었습니다.",
                status_code=409,
            )
        return cls._challenge_data(challenge)

    @staticmethod
    def _challenge_data(challenge: P1AuthOtpChallenge) -> dict[str, Any]:
        return {
            "challenge_id": str(challenge.public_id),
            "expires_in": settings.P1_AUTH_OTP_TTL_SECONDS,
            "resend_after": settings.P1_AUTH_OTP_RESEND_SECONDS,
            "message": CHALLENGE_MESSAGE,
        }

    @classmethod
    def _lock_and_verify_challenge(
        cls,
        *,
        challenge_id: UUID,
        purpose: str,
        otp_code: str,
    ) -> P1AuthOtpChallenge | BackendError:
        challenge = (
            P1AuthOtpChallenge.objects.select_for_update(of=("self",))
            .filter(public_id=challenge_id, purpose=purpose)
            .select_related("customer", "contact", "user")
            .first()
        )
        if challenge is None:
            return cls._verification_failed()
        now = timezone.now()
        if challenge.failure_count >= challenge.max_failures:
            return cls._rate_limited(settings.P1_AUTH_OTP_RESEND_SECONDS)
        if (
            challenge.consumed_at is not None
            or challenge.verified_at is not None
            or challenge.expires_at <= now
        ):
            return cls._verification_failed()

        crypto = P1AuthCrypto.from_settings()
        actual = crypto.otp_digest(str(challenge.public_id), purpose, otp_code)
        if not crypto.compare(actual, challenge.otp_digest):
            challenge.failure_count += 1
            challenge.save(update_fields=["failure_count", "updated_at"])
            if challenge.failure_count >= challenge.max_failures:
                return cls._rate_limited(settings.P1_AUTH_OTP_RESEND_SECONDS)
            return cls._verification_failed()
        if not challenge.target_resolved or not challenge.customer_id:
            return cls._verification_failed()
        current_target = cls._lock_current_challenge_target(challenge)
        if current_target is None:
            challenge.consumed_at = now
            challenge.save(update_fields=["consumed_at", "updated_at"])
            return cls._verification_failed()
        challenge.customer = current_target.customer
        challenge.contact = current_target.contact
        challenge.user = current_target.user
        if current_target.subscription is not None:
            challenge.subscription = current_target.subscription
        challenge.verified_at = now
        challenge.consumed_at = now
        challenge.save(
            update_fields=["verified_at", "consumed_at", "updated_at"]
        )
        return challenge

    @classmethod
    def verify_signup_challenge(
        cls,
        *,
        challenge_id: UUID,
        otp_code: str,
    ) -> dict[str, Any]:
        pending_error = None
        with transaction.atomic():
            result = cls._lock_and_verify_challenge(
                challenge_id=challenge_id,
                purpose=P1AuthOtpChallenge.Purpose.SIGNUP,
                otp_code=otp_code,
            )
            if isinstance(result, BackendError):
                pending_error = result
                raw_ticket = ""
            else:
                challenge = result
                raw_ticket = P1AuthCrypto.generate_ticket()
                P1AuthTicket.objects.create(
                    purpose=P1AuthTicket.Purpose.CLAIM,
                    digest=P1AuthCrypto.from_settings().ticket_digest(raw_ticket),
                    challenge=challenge,
                    customer=challenge.customer,
                    expires_at=timezone.now()
                    + timedelta(seconds=settings.P1_AUTH_TICKET_TTL_SECONDS),
                )
        if pending_error is not None:
            raise pending_error
        return {
            "claim_ticket": raw_ticket,
            "expires_in": settings.P1_AUTH_TICKET_TTL_SECONDS,
        }

    @classmethod
    def verify_username_challenge(
        cls,
        *,
        challenge_id: UUID,
        otp_code: str,
    ) -> dict[str, str]:
        pending_error = None
        username = ""
        with transaction.atomic():
            result = cls._lock_and_verify_challenge(
                challenge_id=challenge_id,
                purpose=P1AuthOtpChallenge.Purpose.USERNAME_RECOVERY,
                otp_code=otp_code,
            )
            if isinstance(result, BackendError):
                pending_error = result
            elif result.user is None:
                pending_error = cls._verification_failed()
            else:
                username = result.user.username
        if pending_error is not None:
            raise pending_error
        # Mobile의 동결 JSON key를 유지하되 사용자의 승인 요구대로 값은
        # 마스킹하지 않는다. 소유 검증(OTP) 후 한 번만 반환한다.
        return {"masked_username": username}

    @classmethod
    def verify_password_reset_challenge(
        cls,
        *,
        challenge_id: UUID,
        otp_code: str,
    ) -> dict[str, Any]:
        pending_error = None
        with transaction.atomic():
            result = cls._lock_and_verify_challenge(
                challenge_id=challenge_id,
                purpose=P1AuthOtpChallenge.Purpose.PASSWORD_RESET,
                otp_code=otp_code,
            )
            if isinstance(result, BackendError):
                pending_error = result
                raw_ticket = ""
            elif result.user is None:
                pending_error = cls._verification_failed()
                raw_ticket = ""
            else:
                challenge = result
                raw_ticket = P1AuthCrypto.generate_ticket()
                P1AuthTicket.objects.create(
                    purpose=P1AuthTicket.Purpose.PASSWORD_RESET,
                    digest=P1AuthCrypto.from_settings().ticket_digest(raw_ticket),
                    challenge=challenge,
                    customer=challenge.customer,
                    user=challenge.user,
                    auth_version_at_issue=challenge.user.auth_version,
                    expires_at=timezone.now()
                    + timedelta(seconds=settings.P1_AUTH_TICKET_TTL_SECONDS),
                )
        if pending_error is not None:
            raise pending_error
        return {
            "reset_ticket": raw_ticket,
            "expires_in": settings.P1_AUTH_TICKET_TTL_SECONDS,
        }

    @staticmethod
    def _lock_operation_idempotency(
        *,
        operation: str,
        idempotency_key_hmac: str,
    ) -> None:
        lock, _ = P1AuthIdempotencyLock.objects.get_or_create(
            operation=operation,
            idempotency_key_hmac=idempotency_key_hmac,
        )
        P1AuthIdempotencyLock.objects.select_for_update(of=("self",)).get(
            pk=lock.pk
        )

    @staticmethod
    def _lock_operation_receipt(
        *,
        operation: str,
        idempotency_key_hmac: str,
    ) -> P1AuthOperationReceipt | None:
        return (
            P1AuthOperationReceipt.objects.select_for_update(of=("self",))
            .filter(
                operation=operation,
                idempotency_key_hmac=idempotency_key_hmac,
            )
            .first()
        )

    @staticmethod
    def _validate_receipt_request(
        *,
        receipt: P1AuthOperationReceipt,
        fingerprint: str,
        crypto: P1AuthCrypto,
    ) -> None:
        if not crypto.compare(
            receipt.request_fingerprint_hmac,
            fingerprint,
        ):
            raise BackendError(
                DUPLICATE_EVENT,
                "동일 Idempotency-Key가 다른 요청에 재사용되었습니다.",
                status_code=409,
            )

    @classmethod
    def _lock_current_receipt_user(
        cls,
        *,
        receipt: P1AuthOperationReceipt,
        password: str,
    ) -> User:
        replay_cutoff = timezone.now() - timedelta(
            seconds=settings.P1_AUTH_IDEMPOTENCY_REPLAY_TTL_SECONDS
        )
        user = (
            User.objects.select_for_update(of=("self",))
            .filter(
                pk=receipt.user_id,
                is_active=True,
                role_code=User.Role.CUSTOMER,
                is_synthetic=True,
                customer_account_links__is_active=True,
                customer_profile__deleted_at__isnull=True,
            )
            .first()
        )
        if (
            user is None
            or receipt.completed_at < replay_cutoff
            or user.auth_version != receipt.auth_version_at_completion
            or not user.check_password(password)
        ):
            raise cls._verification_failed()
        return user

    @classmethod
    def _replay_signup_receipt(
        cls,
        *,
        receipt: P1AuthOperationReceipt,
        fingerprint: str,
        password: str,
        crypto: P1AuthCrypto,
    ) -> SignupResult:
        cls._validate_receipt_request(
            receipt=receipt,
            fingerprint=fingerprint,
            crypto=crypto,
        )
        user = cls._lock_current_receipt_user(
            receipt=receipt,
            password=password,
        )
        pair = AuthenticationService.issue_pair(user)
        return SignupResult(user=user, pair=pair, idempotent_replay=True)

    @classmethod
    def _replay_password_reset_receipt(
        cls,
        *,
        receipt: P1AuthOperationReceipt,
        fingerprint: str,
        password: str,
        crypto: P1AuthCrypto,
    ) -> dict[str, bool]:
        cls._validate_receipt_request(
            receipt=receipt,
            fingerprint=fingerprint,
            crypto=crypto,
        )
        cls._lock_current_receipt_user(
            receipt=receipt,
            password=password,
        )
        return {"password_reset": True, "sessions_revoked": True}

    @classmethod
    def signup(
        cls,
        *,
        claim_ticket: str,
        name: str | None = None,
        email: str | None = None,
        username: str,
        password: str,
        consents: list[dict[str, Any]],
        idempotency_key: str,
        correlation_id: str,
    ) -> SignupResult:
        crypto = P1AuthCrypto.from_settings()
        idem_hmac = crypto.digest(
            "idempotency-key", cls._idempotency_key(idempotency_key)
        )
        ticket_digest = crypto.ticket_digest(claim_ticket)
        fingerprint = crypto.fingerprint(
            "signup-request",
            {
                "ticket": ticket_digest,
                "name": crypto.normalize_text(name or ""),
                "email": crypto.normalize_username(email or ""),
                "username": crypto.normalize_username(username),
                "password": crypto.digest("password-request", password),
                "consents": sorted(
                    consents,
                    key=lambda item: (item["code"], item["version"]),
                ),
            },
        )
        has_replay_receipt = P1AuthOperationReceipt.objects.filter(
            operation=P1AuthOperationReceipt.Operation.SIGNUP,
            idempotency_key_hmac=idem_hmac,
        ).exists()
        has_usable_ticket = P1AuthTicket.objects.filter(
            digest=ticket_digest,
            purpose=P1AuthTicket.Purpose.CLAIM,
            consumed_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).exists()
        if not has_replay_receipt and not has_usable_ticket:
            raise cls._verification_failed()
        try:
            with transaction.atomic():
                cls._lock_operation_idempotency(
                    operation=P1AuthOperationReceipt.Operation.SIGNUP,
                    idempotency_key_hmac=idem_hmac,
                )
                receipt = cls._lock_operation_receipt(
                    operation=P1AuthOperationReceipt.Operation.SIGNUP,
                    idempotency_key_hmac=idem_hmac,
                )
                if receipt is not None:
                    return cls._replay_signup_receipt(
                        receipt=receipt,
                        fingerprint=fingerprint,
                        password=password,
                        crypto=crypto,
                    )
                else:
                    ticket = (
                        P1AuthTicket.objects.select_for_update(of=("self",))
                        .filter(
                            digest=ticket_digest,
                            purpose=P1AuthTicket.Purpose.CLAIM,
                        )
                        .select_related("challenge", "customer")
                        .first()
                    )
                    if ticket is None:
                        raise cls._verification_failed()
                    if (
                        ticket.consumed_at is not None
                        or ticket.expires_at <= timezone.now()
                    ):
                        receipt = cls._lock_operation_receipt(
                            operation=P1AuthOperationReceipt.Operation.SIGNUP,
                            idempotency_key_hmac=idem_hmac,
                        )
                        if receipt is not None:
                            return cls._replay_signup_receipt(
                                receipt=receipt,
                                fingerprint=fingerprint,
                                password=password,
                                crypto=crypto,
                            )
                        raise cls._verification_failed()
                    current_target = cls._lock_current_challenge_target(
                        ticket.challenge
                    )
                    if (
                        current_target is None
                        or current_target.customer.pk != ticket.customer_id
                        or current_target.user is not None
                    ):
                        raise cls._verification_failed()
                    if name or email:
                        try:
                            protected_email = (
                                ContractEmailProtectionService.from_settings()
                                .protect(email or "")
                            )
                        except ContractEmailProtectionError:
                            raise cls._verification_failed() from None
                        if (
                            crypto.normalize_text(
                                current_target.customer.customer_name
                            )
                            != crypto.normalize_text(name or "")
                            or not crypto.compare(
                                current_target.contact.email_lookup_hmac,
                                protected_email.email_lookup_hmac,
                            )
                        ):
                            raise cls._verification_failed()
                    customer = current_target.customer
                    receipt = cls._lock_operation_receipt(
                        operation=P1AuthOperationReceipt.Operation.SIGNUP,
                        idempotency_key_hmac=idem_hmac,
                    )
                    if receipt is not None:
                        return cls._replay_signup_receipt(
                            receipt=receipt,
                            fingerprint=fingerprint,
                            password=password,
                            crypto=crypto,
                        )
                    if User.objects.filter(username__iexact=username).exists():
                        raise BackendError(
                            AUTH_IDENTIFIER_UNAVAILABLE,
                            "사용할 수 없는 아이디입니다. 다른 아이디를 입력해 주세요.",
                            status_code=409,
                        )

                    user = User.objects.create_user(
                        username=username,
                        password=password,
                        full_name=customer.customer_name,
                        email="",
                        role_code=User.Role.CUSTOMER,
                        is_synthetic=True,
                    )
                    customer.user = user
                    required_versions = {
                        item["code"]: item["version"]
                        for item in consents
                        if item["agreed"]
                    }
                    customer.consent_version = required_versions.get(
                        P1AccountConsent.Code.PRIVACY_COLLECTION_USE,
                        "",
                    )
                    customer.consented_at = timezone.now()
                    customer.full_clean()
                    customer.save(
                        update_fields=[
                            "user",
                            "consent_version",
                            "consented_at",
                            "updated_at",
                        ]
                    )
                    link = CustomerAccountLink(
                        user=user,
                        customer=customer,
                        link_reason=CustomerAccountLink.LinkReason.SIGN_UP_EMAIL_OTP,
                    )
                    link.full_clean()
                    link.save()
                    P1AccountConsent.objects.bulk_create(
                        [
                            P1AccountConsent(
                                user=user,
                                code=item["code"],
                                version=item["version"],
                                agreed=item["agreed"],
                            )
                            for item in consents
                        ]
                    )
                    ticket.consumed_at = timezone.now()
                    ticket.save(update_fields=["consumed_at", "updated_at"])
                    P1AuthOperationReceipt.objects.create(
                        operation=P1AuthOperationReceipt.Operation.SIGNUP,
                        idempotency_key_hmac=idem_hmac,
                        request_fingerprint_hmac=fingerprint,
                        user=user,
                        auth_version_at_completion=user.auth_version,
                    )
                    AccountAuditEvent.objects.create(
                        target_user=user,
                        actor=user,
                        event_type=AccountAuditEvent.EventType.CREATE,
                        before_values={},
                        after_values={
                            "role_code": user.role_code,
                            "is_active": user.is_active,
                            "is_staff": user.is_staff,
                            "is_superuser": user.is_superuser,
                            "auth_version": user.auth_version,
                            "groups": [],
                            "permissions": [],
                        },
                        changed_fields=["account_created"],
                        reason="P1_EMAIL_OTP_SIGNUP",
                        correlation_id=UUID(correlation_id),
                    )
                    pair = AuthenticationService.issue_pair(user)
        except IntegrityError as exc:
            with transaction.atomic():
                receipt = cls._lock_operation_receipt(
                    operation=P1AuthOperationReceipt.Operation.SIGNUP,
                    idempotency_key_hmac=idem_hmac,
                )
                if receipt is not None:
                    return cls._replay_signup_receipt(
                        receipt=receipt,
                        fingerprint=fingerprint,
                        password=password,
                        crypto=crypto,
                    )
            raise BackendError(
                AUTH_IDENTIFIER_UNAVAILABLE,
                "사용할 수 없는 아이디입니다. 다른 아이디를 입력해 주세요.",
                status_code=409,
            ) from exc

        return SignupResult(user=user, pair=pair, idempotent_replay=False)

    @classmethod
    def login(cls, *, username: str, password: str) -> tuple[User, TokenPair]:
        crypto = P1AuthCrypto.from_settings()
        subject = crypto.digest(
            "login-subject",
            crypto.normalize_username(username),
        )
        login_failed = False
        pair = None
        with transaction.atomic():
            now = timezone.now()
            bucket, _ = P1AuthLoginRateBucket.objects.get_or_create(
                subject_hmac=subject,
                defaults={"window_started_at": now},
            )
            bucket = P1AuthLoginRateBucket.objects.select_for_update(
                of=("self",)
            ).get(pk=bucket.pk)
            window = timedelta(seconds=settings.P1_AUTH_LOGIN_WINDOW_SECONDS)
            if bucket.window_started_at <= now - window:
                bucket.window_started_at = now
                bucket.failure_count = 0
                bucket.last_failed_at = None
            if bucket.failure_count >= settings.P1_AUTH_LOGIN_MAX_FAILURES:
                retry_after = max(
                    1,
                    int((bucket.window_started_at + window - now).total_seconds())
                    + 1,
                )
                raise cls._rate_limited(retry_after)

            user = (
                User.objects.select_for_update(of=("self",))
                .filter(
                    username__iexact=username,
                    is_active=True,
                    role_code=User.Role.CUSTOMER,
                    is_synthetic=True,
                    customer_account_links__is_active=True,
                    customer_profile__deleted_at__isnull=True,
                )
                .first()
            )
            password_ok = check_password(
                password,
                user.password if user is not None else DUMMY_PASSWORD_HASH,
            )
            if user is None or not password_ok:
                P1AuthRateLimitEvent.objects.create(
                    action=P1AuthRateLimitEvent.Action.LOGIN_FAILURE,
                    subject_hmac=subject,
                )
                bucket.failure_count += 1
                bucket.last_failed_at = now
                bucket.save(
                    update_fields=[
                        "window_started_at",
                        "failure_count",
                        "last_failed_at",
                        "updated_at",
                    ]
                )
                login_failed = True
            else:
                P1AuthRateLimitEvent.objects.filter(
                    action=P1AuthRateLimitEvent.Action.LOGIN_FAILURE,
                    subject_hmac=subject,
                ).delete()
                bucket.window_started_at = now
                bucket.failure_count = 0
                bucket.last_failed_at = None
                bucket.save(
                    update_fields=[
                        "window_started_at",
                        "failure_count",
                        "last_failed_at",
                        "updated_at",
                    ]
                )
                pair = AuthenticationService.issue_pair(user)
        if login_failed or user is None or pair is None:
            raise BackendError(
                AUTH_LOGIN_FAILED,
                "아이디 또는 비밀번호를 확인해 주세요.",
                status_code=401,
            )
        return user, pair

    @classmethod
    def confirm_password_reset(
        cls,
        *,
        reset_ticket: str,
        password: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> dict[str, bool]:
        crypto = P1AuthCrypto.from_settings()
        idem_hmac = crypto.digest(
            "idempotency-key", cls._idempotency_key(idempotency_key)
        )
        ticket_digest = crypto.ticket_digest(reset_ticket)
        fingerprint = crypto.fingerprint(
            "password-reset-request",
            {
                "ticket": ticket_digest,
                "password": crypto.digest("password-request", password),
            },
        )
        has_replay_receipt = P1AuthOperationReceipt.objects.filter(
            operation=P1AuthOperationReceipt.Operation.PASSWORD_RESET,
            idempotency_key_hmac=idem_hmac,
        ).exists()
        has_usable_ticket = P1AuthTicket.objects.filter(
            digest=ticket_digest,
            purpose=P1AuthTicket.Purpose.PASSWORD_RESET,
            consumed_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).exists()
        if not has_replay_receipt and not has_usable_ticket:
            raise cls._verification_failed()
        with transaction.atomic():
            cls._lock_operation_idempotency(
                operation=P1AuthOperationReceipt.Operation.PASSWORD_RESET,
                idempotency_key_hmac=idem_hmac,
            )
            receipt = cls._lock_operation_receipt(
                operation=P1AuthOperationReceipt.Operation.PASSWORD_RESET,
                idempotency_key_hmac=idem_hmac,
            )
            if receipt is not None:
                return cls._replay_password_reset_receipt(
                    receipt=receipt,
                    fingerprint=fingerprint,
                    password=password,
                    crypto=crypto,
                )

            ticket = (
                P1AuthTicket.objects.select_for_update(of=("self",))
                .filter(
                    digest=ticket_digest,
                    purpose=P1AuthTicket.Purpose.PASSWORD_RESET,
                )
                .select_related("challenge", "user")
                .first()
            )
            if ticket is None or ticket.user is None:
                raise cls._verification_failed()
            if (
                ticket.consumed_at is not None
                or ticket.expires_at <= timezone.now()
            ):
                receipt = cls._lock_operation_receipt(
                    operation=(
                        P1AuthOperationReceipt.Operation.PASSWORD_RESET
                    ),
                    idempotency_key_hmac=idem_hmac,
                )
                if receipt is not None:
                    return cls._replay_password_reset_receipt(
                        receipt=receipt,
                        fingerprint=fingerprint,
                        password=password,
                        crypto=crypto,
                    )
                raise cls._verification_failed()
            current_target = cls._lock_current_challenge_target(
                ticket.challenge
            )
            if (
                current_target is None
                or current_target.user is None
                or current_target.user.pk != ticket.user_id
                or current_target.customer.pk != ticket.customer_id
                or ticket.auth_version_at_issue != current_target.user.auth_version
            ):
                raise cls._verification_failed()
            user = current_target.user
            receipt = cls._lock_operation_receipt(
                operation=P1AuthOperationReceipt.Operation.PASSWORD_RESET,
                idempotency_key_hmac=idem_hmac,
            )
            if receipt is not None:
                return cls._replay_password_reset_receipt(
                    receipt=receipt,
                    fingerprint=fingerprint,
                    password=password,
                    crypto=crypto,
                )
            before_version = user.auth_version
            user.set_password(password)
            user.auth_version += 1
            user.save(update_fields=["password", "auth_version", "updated_at"])
            outstanding = OutstandingToken.objects.select_for_update(
                of=("self",)
            ).filter(user=user)
            for token in outstanding:
                BlacklistedToken.objects.get_or_create(token=token)
            ticket.consumed_at = timezone.now()
            ticket.save(update_fields=["consumed_at", "updated_at"])
            P1AuthOperationReceipt.objects.create(
                operation=P1AuthOperationReceipt.Operation.PASSWORD_RESET,
                idempotency_key_hmac=idem_hmac,
                request_fingerprint_hmac=fingerprint,
                user=user,
                auth_version_at_completion=user.auth_version,
            )
            AccountAuditEvent.objects.create(
                target_user=user,
                actor=user,
                event_type=AccountAuditEvent.EventType.PASSWORD_RESET,
                before_values={
                    "auth_version": before_version,
                    "credential_changed": False,
                },
                after_values={
                    "auth_version": user.auth_version,
                    "credential_changed": True,
                },
                changed_fields=["auth_version", "credential_changed"],
                reason="P1_EMAIL_OTP_PASSWORD_RESET",
                correlation_id=UUID(correlation_id),
            )
        return {"password_reset": True, "sessions_revoked": True}
