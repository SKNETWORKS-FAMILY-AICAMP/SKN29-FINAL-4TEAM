"""계약 연락처 정책에 따라 OTP 시험 메일을 전달한다."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

from apps.accounts.models import ContractEmailContact, P1AuthOtpChallenge
from apps.accounts.services.contract_email_protection import (
    ContractEmailProtectionService,
)


logger = logging.getLogger("watercare.auth")


class P1AuthEmailService:
    """합성 Redirect와 PM 승인 로컬 수신자를 명시적으로 분리한다."""

    @classmethod
    def deliver_otp(
        cls,
        *,
        challenge: P1AuthOtpChallenge,
        contact: ContractEmailContact,
        otp_code: str,
    ) -> bool:
        protection = ContractEmailProtectionService.from_settings()
        protected_recipient = protection.decrypt(contact.encrypted_email)
        if (
            contact.delivery_policy
            == ContractEmailContact.DeliveryPolicy.RUNTIME_REDIRECT_ONLY
            and contact.data_classification
            == ContractEmailContact.DataClassification.SYNTHETIC
        ):
            recipient = str(settings.P1_AUTH_EMAIL_REDIRECT_TO or "").strip()
        elif (
            settings.DEBUG
            and contact.delivery_policy
            == ContractEmailContact.DeliveryPolicy.APPROVED_TEST_RECIPIENT
            and contact.data_classification
            == ContractEmailContact.DataClassification.APPROVED_TEST_PII
            and not protected_recipient.rsplit("@", 1)[-1].endswith(".invalid")
        ):
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
