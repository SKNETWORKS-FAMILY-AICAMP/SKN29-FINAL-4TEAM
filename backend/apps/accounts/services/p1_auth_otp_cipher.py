"""Outbox에 넣는 OTP 원문을 짧게 암호화하는 경계."""

from __future__ import annotations

import base64
import binascii

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class P1AuthOtpCipherError(ValueError):
    pass


class P1AuthOtpCipher:
    def __init__(self, key: str) -> None:
        try:
            decoded = base64.urlsafe_b64decode(str(key).encode("ascii"))
        except (binascii.Error, ValueError, UnicodeEncodeError) as exc:
            raise P1AuthOtpCipherError(
                "P1_AUTH_OTP_ENCRYPTION_KEY 설정이 올바르지 않습니다."
            ) from exc
        if len(decoded) != 32:
            raise P1AuthOtpCipherError(
                "P1_AUTH_OTP_ENCRYPTION_KEY 설정이 올바르지 않습니다."
            )
        self._fernet = Fernet(base64.urlsafe_b64encode(decoded))

    @classmethod
    def from_settings(cls) -> "P1AuthOtpCipher":
        return cls(settings.P1_AUTH_OTP_ENCRYPTION_KEY)

    def encrypt(self, otp_code: str) -> str:
        return self._fernet.encrypt(str(otp_code).encode("ascii")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            value = self._fernet.decrypt(str(ciphertext).encode("ascii"))
            otp_code = value.decode("ascii")
        except (
            binascii.Error,
            InvalidToken,
            ValueError,
            UnicodeEncodeError,
            UnicodeDecodeError,
        ) as exc:
            raise P1AuthOtpCipherError("OTP 암호문을 확인할 수 없습니다.") from exc
        if len(otp_code) != 6 or not otp_code.isdigit():
            raise P1AuthOtpCipherError("OTP 암호문을 확인할 수 없습니다.")
        return otp_code
