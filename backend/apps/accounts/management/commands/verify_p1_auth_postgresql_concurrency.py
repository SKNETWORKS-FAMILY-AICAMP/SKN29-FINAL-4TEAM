"""로컬 PostgreSQL에서 P1 인증 잠금 경계를 동시 실행 검증한다."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connection, transaction

from apps.accounts.models import (
    CustomerAccountLink,
    CustomerProfile,
    P1AuthChallengeRateBucket,
    P1AuthEmailOutbox,
    P1AuthLoginRateBucket,
    P1AuthOtpChallenge,
    P1AuthRateLimitEvent,
    User,
)
from apps.accounts.services.p1_auth_crypto import P1AuthCrypto
from apps.accounts.services.p1_auth_service import P1AuthService
from common.exceptions.base import BackendError


IDENTITY = {
    "name": "합성 계약고객 P1 001",
    "email": "customer-p1-001@waterbridge.invalid",
}


class Command(BaseCommand):
    help = "로컬 PostgreSQL P1 동시성 경계를 검증하고 전용 행을 정리합니다."

    @staticmethod
    def _challenge_worker(barrier: Barrier, key: str) -> dict[str, object]:
        close_old_connections()
        try:
            barrier.wait()
            data = P1AuthService.create_challenge(
                purpose=P1AuthOtpChallenge.Purpose.SIGNUP,
                identity=IDENTITY,
                idempotency_key=key,
            )
            return {"status": 202, "challenge_id": data["challenge_id"]}
        except BackendError as exc:
            return {"status": exc.status_code, "code": exc.code}
        finally:
            close_old_connections()

    @staticmethod
    def _login_worker(barrier: Barrier, username: str) -> int:
        close_old_connections()
        try:
            barrier.wait()
            P1AuthService.login(username=username, password="always-wrong")
            return 200
        except BackendError as exc:
            return exc.status_code
        finally:
            close_old_connections()

    @staticmethod
    def _cleanup_challenges(idempotency_keys: list[str]) -> None:
        crypto = P1AuthCrypto.from_settings()
        idempotency_hmacs = [
            crypto.digest("idempotency-key", key)
            for key in idempotency_keys
        ]
        challenges = P1AuthOtpChallenge.objects.filter(
            purpose=P1AuthOtpChallenge.Purpose.SIGNUP,
            idempotency_key_hmac__in=idempotency_hmacs,
        )
        fingerprints = list(
            challenges.values_list("request_fingerprint_hmac", flat=True)
        )
        P1AuthEmailOutbox.objects.filter(challenge__in=challenges).delete()
        challenges.delete()
        P1AuthChallengeRateBucket.objects.filter(
            purpose=P1AuthOtpChallenge.Purpose.SIGNUP,
            request_fingerprint_hmac__in=fingerprints,
        ).delete()

    def handle(self, *args, **options):
        del args, options
        if not settings.DEBUG or connection.vendor != "postgresql":
            raise CommandError("로컬 DEBUG PostgreSQL에서만 실행할 수 있습니다.")
        candidate = CustomerProfile.objects.filter(
            customer_no="SYN-CUSTOMER-P1-001",
            user_id__isnull=True,
            is_synthetic=True,
        ).first()
        if candidate is None:
            raise CommandError("P1 가입 전 합성 고객 Fixture가 필요합니다.")

        challenge_keys: list[str] = []
        login_username = f"p1.concurrent.{uuid4().hex[:12]}"
        user = None
        profile = None
        result: dict[str, object] = {"database_vendor": connection.vendor}
        try:
            same_key = str(uuid4())
            challenge_keys.append(same_key)
            barrier = Barrier(2)
            with ThreadPoolExecutor(max_workers=2) as pool:
                same_results = list(
                    pool.map(
                        lambda _: self._challenge_worker(barrier, same_key),
                        range(2),
                    )
                )
            same_ids = {item.get("challenge_id") for item in same_results}
            result["same_key"] = {
                "statuses": sorted(item["status"] for item in same_results),
                "one_challenge_id": len(same_ids) == 1,
            }
            self._cleanup_challenges(challenge_keys)
            challenge_keys.clear()

            different_keys = [str(uuid4()), str(uuid4())]
            challenge_keys.extend(different_keys)
            barrier = Barrier(2)
            with ThreadPoolExecutor(max_workers=2) as pool:
                different_results = list(
                    pool.map(
                        lambda key: self._challenge_worker(barrier, key),
                        different_keys,
                    )
                )
            challenge_count = P1AuthOtpChallenge.objects.filter(
                idempotency_key_hmac__in=[
                    P1AuthCrypto.from_settings().digest("idempotency-key", key)
                    for key in different_keys
                ]
            ).count()
            result["different_key"] = {
                "statuses": sorted(
                    item["status"] for item in different_results
                ),
                "challenge_count": challenge_count,
            }
            self._cleanup_challenges(challenge_keys)
            challenge_keys.clear()

            with transaction.atomic():
                user = User.objects.create_user(
                    username=login_username,
                    password="valid-password-1234",
                    full_name="Synthetic concurrent login user",
                    role_code=User.Role.CUSTOMER,
                    is_synthetic=True,
                )
                profile = CustomerProfile.objects.create(
                    user=user,
                    customer_no=f"SYN-CONCURRENT-{uuid4().hex[:12]}",
                    customer_name="Synthetic concurrent login customer",
                    is_synthetic=True,
                )
                CustomerAccountLink.objects.create(
                    user=user,
                    customer=profile,
                    is_active=True,
                    link_reason=CustomerAccountLink.LinkReason.LEGACY_BACKFILL,
                )
            attempts = settings.P1_AUTH_LOGIN_MAX_FAILURES + 2
            barrier = Barrier(attempts)
            with ThreadPoolExecutor(max_workers=attempts) as pool:
                login_statuses = list(
                    pool.map(
                        lambda _: self._login_worker(barrier, login_username),
                        range(attempts),
                    )
                )
            result["login_burst"] = {
                "statuses": sorted(login_statuses),
                "failure_count": P1AuthLoginRateBucket.objects.get(
                    subject_hmac=P1AuthCrypto.from_settings().digest(
                        "login-subject",
                        P1AuthCrypto.normalize_username(login_username),
                    ),
                    failure_count=settings.P1_AUTH_LOGIN_MAX_FAILURES
                ).failure_count,
            }
        finally:
            self._cleanup_challenges(challenge_keys)
            subject = P1AuthCrypto.from_settings().digest(
                "login-subject",
                P1AuthCrypto.normalize_username(login_username),
            )
            P1AuthRateLimitEvent.objects.filter(subject_hmac=subject).delete()
            P1AuthLoginRateBucket.objects.filter(subject_hmac=subject).delete()
            if profile is not None:
                CustomerAccountLink.objects.filter(customer=profile).delete()
                profile.delete()
            if user is not None:
                user.delete()

        expected_login = [401] * settings.P1_AUTH_LOGIN_MAX_FAILURES + [429, 429]
        passed = (
            result.get("same_key")
            == {"statuses": [202, 202], "one_challenge_id": True}
            and result.get("different_key")
            == {"statuses": [202, 429], "challenge_count": 1}
            and result.get("login_burst")
            == {
                "statuses": expected_login,
                "failure_count": settings.P1_AUTH_LOGIN_MAX_FAILURES,
            }
        )
        result["passed"] = passed
        if not passed:
            raise CommandError(
                "P1 PostgreSQL 동시성 검증에 실패했습니다: "
                + json.dumps(result, ensure_ascii=False, sort_keys=True)
            )
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
