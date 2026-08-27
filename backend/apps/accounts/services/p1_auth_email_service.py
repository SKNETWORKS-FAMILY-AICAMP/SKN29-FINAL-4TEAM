"""계약 연락처 정책에 따라 OTP 시험 메일을 전달한다."""

from __future__ import annotations

import hmac
import logging

from django.conf import settings
from django.core.mail import send_mail

from apps.accounts.models import ContractEmailContact, P1AuthOtpChallenge
from apps.accounts.services.contract_email_protection import (
    ContractEmailProtectionService,
)


logger = logging.getLogger("watercare.auth")


class P1AuthEmailService:
    """합성 Redirect와 승인된 로컬/AWS 수신자를 분리한다."""

    @staticmethod
    def _approved_test_recipient_delivery_allowed(
        contact: ContractEmailContact,
    ) -> bool:
        if settings.DEBUG:
            return True
        if settings.P1_AUTH_RUNTIME_ENVIRONMENT != "AWS_NONPROD":
            return False
        if not settings.P1_AUTH_APPROVED_TEST_RECIPIENT_DELIVERY_ENABLED:
            return False
        return any(
            hmac.compare_digest(contact.email_lookup_hmac, approved_hmac)
            for approved_hmac in (
                settings.P1_AUTH_APPROVED_TEST_RECIPIENT_ALLOWLIST_HMACS
            )
        )

    @classmethod
    def deliver_otp(
        cls,
        *,
        challenge: P1AuthOtpChallenge,
        contact: ContractEmailContact,
        otp_code: str,
    ) -> bool:
        protection = ContractEmailProtectionService.from_settings()
        if (
            contact.delivery_policy
            == ContractEmailContact.DeliveryPolicy.RUNTIME_REDIRECT_ONLY
            and contact.data_classification
            == ContractEmailContact.DataClassification.SYNTHETIC
        ):
            protection.decrypt(contact.encrypted_email)
            recipient = str(settings.P1_AUTH_EMAIL_REDIRECT_TO or "").strip()
        elif (
            contact.delivery_policy
            == ContractEmailContact.DeliveryPolicy.APPROVED_TEST_RECIPIENT
            and contact.data_classification
            == ContractEmailContact.DataClassification.APPROVED_TEST_PII
        ):
            if not cls._approved_test_recipient_delivery_allowed(contact):
                return False
            protected_recipient = protection.decrypt(contact.encrypted_email)
            if protected_recipient.rsplit("@", 1)[-1].endswith(".invalid"):
                return False
            recipient = protected_recipient
        else:
            return False
        if not recipient:
            return False

        try:
            sent = send_mail(
                subject="[WaterBridge] 이메일 인증번호",
                message=(
                    "WaterBridge 이메일 인증번호는 "
                    f"{otp_code} 입니다. "
                    f"{settings.P1_AUTH_OTP_TTL_SECONDS}초 안에 입력해 주세요."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
        except Exception:
            logger.warning(
                "p1_auth_email_delivery_failed",
                extra={"challenge_id": str(challenge.public_id)},
            )
            return False
        return sent == 1
