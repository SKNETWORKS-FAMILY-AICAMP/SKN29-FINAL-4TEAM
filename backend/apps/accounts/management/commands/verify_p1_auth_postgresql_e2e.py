"""로컬 PostgreSQL에서 P1 인증 전 과정을 rollback 검증한다."""

from __future__ import annotations

import json
from unittest.mock import patch
from uuid import UUID, uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.accounts.models import CustomerAccountLink, CustomerProfile, User
from apps.accounts.models.p1_auth import P1AuthOtpChallenge
from apps.accounts.services.p1_auth_crypto import P1AuthCrypto
from apps.accounts.services.p1_auth_service import P1AuthService


CUSTOMER_NUMBER = "SYN-CUSTOMER-P1-001"
CUSTOMER_NAME = "합성 계약고객 P1 001"
CONTRACT_NUMBER = "SYN-CONTRACT-P1-001"
CONTRACT_EMAIL = "customer-p1-001@waterbridge.invalid"


class Command(BaseCommand):
    help = "로컬 PostgreSQL P1 인증 흐름을 실행하고 전부 rollback합니다."

    def handle(self, *args, **options):
        del args, options
        if not settings.DEBUG or connection.vendor != "postgresql":
            raise CommandError("로컬 DEBUG PostgreSQL에서만 실행할 수 있습니다.")

        customer = CustomerProfile.objects.filter(
            customer_no=CUSTOMER_NUMBER,
            is_synthetic=True,
            user_id__isnull=True,
        ).first()
        if customer is None:
            raise CommandError("P1 가입 전 합성 고객 Fixture가 필요합니다.")
        initial = {
            "candidate_user": User.objects.filter(
                username="p1.db.verify.0825"
            ).count(),
            "candidate_link": CustomerAccountLink.objects.filter(
                customer=customer,
                is_active=True,
            ).count(),
        }
        if any(initial.values()):
            raise CommandError("P1 E2E 전용 계정 또는 연결이 이미 존재합니다.")

        result: dict[str, object] = {}
        with transaction.atomic():
            with patch.object(P1AuthCrypto, "generate_otp", return_value="123456"):
                signup_challenge = P1AuthService.create_challenge(
                    purpose=P1AuthOtpChallenge.Purpose.SIGNUP,
                    identity={
                        "customer_number": CUSTOMER_NUMBER,
                        "contract_number": CONTRACT_NUMBER,
                    },
                    idempotency_key=str(uuid4()),
                )
            claim = P1AuthService.verify_signup_challenge(
                challenge_id=UUID(signup_challenge["challenge_id"]),
                otp_code="123456",
            )
            signup = P1AuthService.signup(
                claim_ticket=claim["claim_ticket"],
                name=CUSTOMER_NAME,
                email=CONTRACT_EMAIL,
                username="p1.db.verify.0825",
                password="waterbridge1234",
                consents=[
                    {
                        "code": "TERMS_OF_SERVICE",
                        "version": "v1",
                        "agreed": True,
                    },
                    {
                        "code": "PRIVACY_COLLECTION_USE",
                        "version": "v1",
                        "agreed": True,
                    },
                    {
                        "code": "MARKETING",
                        "version": "v1",
                        "agreed": False,
                    },
                ],
                idempotency_key=str(uuid4()),
                correlation_id=str(uuid4()),
            )
            login_user, login_pair = P1AuthService.login(
                username="p1.db.verify.0825",
                password="waterbridge1234",
            )

            with patch.object(P1AuthCrypto, "generate_otp", return_value="234567"):
                username_challenge = P1AuthService.create_challenge(
                    purpose=P1AuthOtpChallenge.Purpose.USERNAME_RECOVERY,
                    identity={"name": CUSTOMER_NAME, "email": CONTRACT_EMAIL},
                    idempotency_key=str(uuid4()),
                )
            recovered = P1AuthService.verify_username_challenge(
                challenge_id=UUID(username_challenge["challenge_id"]),
                otp_code="234567",
            )

            with patch.object(P1AuthCrypto, "generate_otp", return_value="345678"):
                reset_challenge = P1AuthService.create_challenge(
                    purpose=P1AuthOtpChallenge.Purpose.PASSWORD_RESET,
                    identity={
                        "name": CUSTOMER_NAME,
                        "email": CONTRACT_EMAIL,
                        "username": "p1.db.verify.0825",
                    },
                    idempotency_key=str(uuid4()),
                )
            reset_ticket = P1AuthService.verify_password_reset_challenge(
                challenge_id=UUID(reset_challenge["challenge_id"]),
                otp_code="345678",
            )
            reset = P1AuthService.confirm_password_reset(
                reset_ticket=reset_ticket["reset_ticket"],
                password="newwaterbridge5678",
                idempotency_key=str(uuid4()),
                correlation_id=str(uuid4()),
            )
            user = User.objects.get(pk=signup.user.pk)
            result = {
                "database_vendor": connection.vendor,
                "signup": bool(
                    signup.pair.access_token and signup.pair.refresh_token
                ),
                "login": bool(
                    login_user.pk == signup.user.pk
                    and login_pair.access_token
                    and login_pair.refresh_token
                ),
                "username_recovery_full": (
                    recovered["masked_username"] == "p1.db.verify.0825"
                ),
                "password_reset": (
                    reset["password_reset"]
                    and reset["sessions_revoked"]
                    and user.auth_version == 2
                    and user.check_password("newwaterbridge5678")
                ),
                "inside_candidate_user": User.objects.filter(
                    username="p1.db.verify.0825"
                ).count(),
                "inside_candidate_link": CustomerAccountLink.objects.filter(
                    customer=customer,
                    is_active=True,
                ).count(),
            }
            transaction.set_rollback(True)

        customer.refresh_from_db()
        result["rollback_preserved"] = (
            User.objects.filter(username="p1.db.verify.0825").count()
            == initial["candidate_user"]
            and CustomerAccountLink.objects.filter(
                customer=customer,
                is_active=True,
            ).count()
            == initial["candidate_link"]
            and customer.user_id is None
        )
        if not all(
            result[key]
            for key in (
                "signup",
                "login",
                "username_recovery_full",
                "password_reset",
                "rollback_preserved",
            )
        ):
            raise CommandError("P1 PostgreSQL rollback E2E 검증에 실패했습니다.")
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
