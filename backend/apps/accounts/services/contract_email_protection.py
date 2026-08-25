"""P1-A 합성 계약 이메일 암호화·검색 HMAC 경계."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
from dataclasses import dataclass
from unicodedata import normalize

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


class ContractEmailProtectionError(ValueError):
    """보호 키 또는 암호문이 유효하지 않을 때 사용하는 안전한 오류."""


@dataclass(frozen=True)
class ProtectedContractEmail:
    """DB에 저장할 계약 이메일 보호 결과."""

    encrypted_email: str
    email_lookup_hmac: str
    key_version: str


def normalize_synthetic_contract_email(value: str) -> str:
    """합성 계약 이메일을 결정적으로 정규화하고 실주소를 차단한다."""

    normalized = normalize("NFKC", str(value)).strip().casefold()
    try:
        validate_email(normalized)
    except ValidationError as exc:
        raise ContractEmailProtectionError(
            "합성 계약 이메일 형식이 올바르지 않습니다."
        ) from exc
    domain = normalized.rsplit("@", 1)[-1]
    if not domain.endswith(".invalid"):
        raise ContractEmailProtectionError(
            "P1-A에서는 .invalid 합성 이메일만 허용합니다."
        )
    return normalized


def _decode_32_byte_key(value: str, *, setting_name: str) -> bytes:
    """Secret 원문을 노출하지 않고 URL-safe base64 키를 검증한다."""

    try:
        decoded = base64.urlsafe_b64decode(str(value).encode("ascii"))
    except (UnicodeEncodeError, ValueError, binascii.Error) as exc:
        raise ContractEmailProtectionError(
            f"{setting_name} 설정이 올바르지 않습니다."
        ) from exc
    if len(decoded) != 32:
        raise ContractEmailProtectionError(
            f"{setting_name} 설정이 올바르지 않습니다."
        )
    return decoded


class ContractEmailProtectionService:
    """Fernet 암호화와 독립 HMAC 키로 계약 이메일을 보호한다."""

    def __init__(
        self,
        *,
        encryption_key: str,
        hmac_key: str,
        key_version: str,
    ) -> None:
        encryption_bytes = _decode_32_byte_key(
            encryption_key,
            setting_name="CONTRACT_EMAIL_ENCRYPTION_KEY",
        )
        self._fernet = Fernet(
            base64.urlsafe_b64encode(encryption_bytes)
        )
        self._hmac_key = _decode_32_byte_key(
            hmac_key,
            setting_name="CONTRACT_EMAIL_HMAC_KEY",
        )
        self._key_version = str(key_version).strip()
        if not self._key_version:
            raise ContractEmailProtectionError(
                "CONTRACT_EMAIL_KEY_VERSION 설정이 올바르지 않습니다."
            )

    @classmethod
    def from_settings(cls) -> "ContractEmailProtectionService":
        return cls(
            encryption_key=settings.CONTRACT_EMAIL_ENCRYPTION_KEY,
            hmac_key=settings.CONTRACT_EMAIL_HMAC_KEY,
            key_version=settings.CONTRACT_EMAIL_KEY_VERSION,
        )

    def protect(self, email: str) -> ProtectedContractEmail:
        normalized = normalize_synthetic_contract_email(email)
        encoded = normalized.encode("utf-8")
        return ProtectedContractEmail(
            encrypted_email=self._fernet.encrypt(encoded).decode("ascii"),
            email_lookup_hmac=hmac.new(
                self._hmac_key,
                encoded,
                hashlib.sha256,
            ).hexdigest(),
            key_version=self._key_version,
        )

    def decrypt(self, encrypted_email: str) -> str:
        try:
            plaintext = self._fernet.decrypt(
                str(encrypted_email).encode("ascii")
            )
            return plaintext.decode("utf-8")
        except (InvalidToken, UnicodeEncodeError, UnicodeDecodeError) as exc:
            raise ContractEmailProtectionError(
                "계약 이메일 암호문을 확인할 수 없습니다."
            ) from exc

    def matches(self, email: str, expected_hmac: str) -> bool:
        normalized = normalize_synthetic_contract_email(email)
        actual = hmac.new(
            self._hmac_key,
            normalized.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(actual, str(expected_hmac))
