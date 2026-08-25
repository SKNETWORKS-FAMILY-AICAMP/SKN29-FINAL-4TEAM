"""합성 계약 연락처 OTP를 환경변수 수신함으로만 전달한다."""

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
    """DB 이메일과 실제 시험 수신함을 분리해 개인정보 저장을 피한다."""

    @classmethod
    def deliver_otp(
        cls,
        *,
        challenge: P1AuthOtpChallenge,
        contact: ContractEmailContact,
        otp_code: str,
    ) -> bool:
        redirect_to = str(settings.P1_AUTH_EMAIL_REDIRECT_TO or "").strip()
        if not redirect_to:
            return False

        # 암호문이 현재 키로 복호화되는지 먼저 검증한다. 주소 원문은 발송,
        # 응답, 로그에 사용하지 않고 합성 계약 연락처의 무결성 확인에만 쓴다.
        ContractEmailProtectionService.from_settings().decrypt(
            contact.encrypted_email
        )
        try:
            sent = send_mail(
                subject="[WaterBridge] 이메일 인증번호",
                message=(
                    "WaterBridge 이메일 인증번호는 "
                    f"{otp_code} 입니다. "
                    f"{settings.P1_AUTH_OTP_TTL_SECONDS}초 안에 입력해 주세요."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[redirect_to],
                fail_silently=False,
            )
        except Exception:
            logger.warning(
                "p1_auth_email_delivery_failed",
                extra={"challenge_id": str(challenge.public_id)},
            )
            return False
        return sent == 1
