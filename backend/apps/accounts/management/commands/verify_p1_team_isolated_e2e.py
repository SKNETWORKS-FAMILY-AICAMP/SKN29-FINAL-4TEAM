"""Rollback-only P1 signup, login, and inquiry verification on the isolated DB."""

from __future__ import annotations

import json
import secrets
from unittest.mock import patch
from uuid import UUID, uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from rest_framework.test import APIClient

from apps.accounts.management.commands.prepare_p1_team_isolated_runtime import (
    ISOLATED_DATABASE_NAME,
    PRESERVE_PREFIX,
)
from apps.accounts.models import (
    ContractEmailContact,
    CustomerAccountLink,
    CustomerProfile,
    P1AuthOtpChallenge,
    User,
)
from apps.accounts.services.contract_email_protection import (
    ContractEmailProtectionService,
)
from apps.accounts.services.p1_auth_crypto import P1AuthCrypto
from apps.accounts.services.p1_auth_service import P1AuthService
from apps.inquiries.models import Inquiry
from apps.subscriptions.models import CustomerSubscription


class Command(BaseCommand):
    help = (
        "P1 격리 DB에서 미가입 팀 고객 1명의 OTP 가입·ID/PW 로그인·문의 생성을 "
        "실행한 뒤 전체 rollback합니다."
    )

    def handle(self, *args, **options) -> None:
        del args, options
        database_name = str(connection.settings_dict.get("NAME") or "")
        if (
            not settings.DEBUG
            or connection.vendor != "postgresql"
            or database_name != ISOLATED_DATABASE_NAME
        ):
            raise CommandError("정확한 DEBUG P1 격리 PostgreSQL에서만 실행됩니다.")

        customer = (
            CustomerProfile.objects.filter(
                customer_no__startswith=PRESERVE_PREFIX,
                is_synthetic=True,
                user_id__isnull=True,
            )
            .exclude(account_links__is_active=True)
            .order_by("customer_no")
            .first()
        )
        if customer is None:
            raise CommandError("가입 전 P1 팀 고객이 없습니다.")
        contact = ContractEmailContact.objects.filter(
            customer=customer,
            is_active=True,
            is_primary=True,
        ).first()
        subscription = CustomerSubscription.objects.filter(
            customer=customer,
            status_code=CustomerSubscription.Status.ACTIVE,
        ).first()
        if contact is None or subscription is None:
            raise CommandError("P1 팀 고객의 연락처 또는 활성 구독이 없습니다.")

        protection = ContractEmailProtectionService.from_settings()
        email = protection.decrypt(contact.encrypted_email)
        username = f"p1.isolated.verify.{uuid4().hex[:10]}"
        password = f"Wb{secrets.token_urlsafe(18)}7"
        before = {
            "users": User.objects.count(),
            "links": CustomerAccountLink.objects.count(),
            "inquiries": Inquiry.objects.count(),
        }
        result: dict[str, object] = {}

        with transaction.atomic():
            with patch.object(P1AuthCrypto, "generate_otp", return_value="123456"):
                challenge = P1AuthService.create_challenge(
                    purpose=P1AuthOtpChallenge.Purpose.SIGNUP,
                    identity={
                        "customer_number": customer.customer_no,
                        "contract_number": subscription.contract_no,
                    },
                    idempotency_key=str(uuid4()),
                )
            claim = P1AuthService.verify_signup_challenge(
                challenge_id=UUID(challenge["challenge_id"]),
                otp_code="123456",
            )
            signup = P1AuthService.signup(
                claim_ticket=claim["claim_ticket"],
                name=customer.customer_name,
                email=email,
                username=username,
                password=password,
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
                username=username,
                password=password,
            )

            client = APIClient()
            client.force_authenticate(user=login_user)
            inquiry_response = client.post(
                "/api/v1/inquiries",
                {
                    "subscription_id": str(subscription.public_id),
                    "channel_code": "MOBILE",
                    "raw_text": "정수기 출수량이 평소보다 감소했습니다.",
                    "representative_symptom_code": "LOW_FLOW",
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY=f"p1-isolated-{uuid4()}",
                HTTP_HOST="localhost",
            )
            inquiry_data = (
                inquiry_response.json().get("data")
                if inquiry_response.status_code == 201
                else None
            )

            consultant = User.objects.filter(
                role_code=User.Role.CONSULTANT,
                is_synthetic=True,
                is_active=True,
                employee_no__isnull=False,
            ).order_by("username").first()
            if consultant is None:
                raise CommandError("합성 상담사 계정이 없습니다.")
            consultant_password = f"Wb{secrets.token_urlsafe(18)}9"
            consultant.set_password(consultant_password)
            consultant.auth_version += 1
            consultant.save(
                update_fields=["password", "auth_version", "updated_at"]
            )
            consultant_client = APIClient()
            consultant_login = consultant_client.post(
                "/api/v1/auth/login",
                {
                    "username": consultant.username,
                    "password": consultant_password,
                },
                format="json",
                HTTP_HOST="localhost",
            )
            consultant_data = (
                consultant_login.json().get("data")
                if consultant_login.status_code == 200
                else None
            )
            result = {
                "database_name": database_name,
                "customer_number": customer.customer_no,
                "signup": bool(
                    signup.pair.access_token and signup.pair.refresh_token
                ),
                "login": bool(
                    login_user.pk == signup.user.pk
                    and login_pair.access_token
                    and login_pair.refresh_token
                ),
                "inquiry_created": inquiry_response.status_code == 201,
                "inquiry_status": (
                    inquiry_data.get("status_code") if inquiry_data else None
                ),
                "inquiry_state_version": (
                    inquiry_data.get("state_version") if inquiry_data else None
                ),
                "consultant_login": (
                    consultant_login.status_code == 200
                    and consultant_data is not None
                    and consultant_data["user"]["role_code"] == "CONSULTANT"
                ),
                "email_exposed": False,
                "secret_exposed": False,
                "ai_called": False,
            }
            transaction.set_rollback(True)

        customer.refresh_from_db()
        result["rollback_preserved"] = (
            User.objects.count() == before["users"]
            and CustomerAccountLink.objects.count() == before["links"]
            and Inquiry.objects.count() == before["inquiries"]
            and customer.user_id is None
        )
        required = (
            result["signup"],
            result["login"],
            result["inquiry_created"],
            result["inquiry_status"] == "DRAFT",
            result["inquiry_state_version"] == 1,
            result["consultant_login"],
            result["rollback_preserved"],
        )
        if not all(required):
            raise CommandError("P1 격리 DB rollback E2E 검증에 실패했습니다.")
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
