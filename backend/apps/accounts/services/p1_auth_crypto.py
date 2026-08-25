"""P1 인증용 원문 비저장 HMAC·OTP·Ticket 도구."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from collections.abc import Mapping
from typing import Any
from unicodedata import normalize

from django.conf import settings


class P1AuthCryptoError(ValueError):
    """P1 인증 Secret 구성이 안전하지 않을 때 발생한다."""


class P1AuthCrypto:
    def __init__(self, secret: str) -> None:
        normalized = str(secret or "").encode("utf-8")
        if len(normalized) < 32:
            raise P1AuthCryptoError(
                "P1_AUTH_HMAC_SECRET은 32-byte 이상이어야 합니다."
            )
        self._secret = normalized

    @classmethod
    def from_settings(cls) -> "P1AuthCrypto":
        return cls(settings.P1_AUTH_HMAC_SECRET)

    @staticmethod
    def normalize_text(value: str) -> str:
        return normalize("NFKC", str(value or "")).strip()

    @classmethod
    def normalize_username(cls, value: str) -> str:
        return cls.normalize_text(value).casefold()

    def digest(self, namespace: str, value: str) -> str:
        payload = f"{namespace}\x00{value}".encode("utf-8")
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def fingerprint(self, namespace: str, value: Mapping[str, Any]) -> str:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return self.digest(namespace, encoded)

    def otp_digest(self, challenge_id: str, purpose: str, otp_code: str) -> str:
        return self.digest("otp", f"{challenge_id}:{purpose}:{otp_code}")

    def ticket_digest(self, raw_ticket: str) -> str:
        return self.digest("ticket", str(raw_ticket))

    @staticmethod
    def generate_otp() -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

    @staticmethod
    def generate_ticket() -> str:
        return secrets.token_urlsafe(48)

    @staticmethod
    def compare(left: str, right: str) -> bool:
        return hmac.compare_digest(str(left), str(right))
