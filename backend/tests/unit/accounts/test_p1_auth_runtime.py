"""P1 계약 이메일 OTP 인증 Runtime API 회귀 테스트."""

from __future__ import annotations

import os
import re
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from django.core import mail
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from apps.accounts.models import (
    ContractEmailContact,
    CustomerAccountLink,
    CustomerProfile,
    P1AuthEmailOutbox,
    P1AccountConsent,
    P1AuthChallengeRateBucket,
    P1AuthIdempotencyLock,
    P1AuthLoginRateBucket,
    P1AuthOtpChallenge,
    P1AuthTicket,
    User,
)
from apps.subscriptions.models import CustomerSubscription
from apps.accounts.services.p1_auth_email_outbox_service import (
    P1AuthEmailOutboxService,
)
from apps.accounts.services.contract_email_protection import (
    ContractEmailProtectionService,
)


pytestmark = pytest.mark.django_db

CUSTOMER_NUMBER = "SYN-CUSTOMER-P1-001"
CONTRACT_NUMBER = "SYN-CONTRACT-P1-001"
CUSTOMER_NAME = "합성 계약고객 P1 001"
CONTRACT_EMAIL = "customer-p1-001@waterbridge.invalid"
USERNAME = "customer.p1"
PASSWORD = "waterbridge1234"
NEW_PASSWORD = "newwaterbridge5678"
THIRD_PASSWORD = "thirdwaterbridge9012"
CONSENTS = [
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
]


def _seed() -> None:
    call_command("seed_p1_account_link_fixture", verbosity=0)


def _convert_seed_contact_to_approved_test(email: str) -> ContractEmailContact:
    contact = ContractEmailContact.objects.get(
        customer__customer_no=CUSTOMER_NUMBER
    )
    protected = (
        ContractEmailProtectionService.from_settings().protect_approved_test(
            email
        )
    )
    contact.encrypted_email = protected.encrypted_email
    contact.email_lookup_hmac = protected.email_lookup_hmac
    contact.key_version = protected.key_version
    contact.delivery_policy = (
        ContractEmailContact.DeliveryPolicy.APPROVED_TEST_RECIPIENT
    )
    contact.data_classification = (
        ContractEmailContact.DataClassification.APPROVED_TEST_PII
    )
    contact.source_system = "PM_APPROVED_LOCAL_E2E_TEST"
    contact.full_clean()
    contact.save()
    return contact


def _challenge(
    client,
    path: str,
    *,
    payload: dict | None = None,
    idempotency_key: str | None = None,
):
    return client.post(
        path,
        payload
        or {
            "customer_number": CUSTOMER_NUMBER,
            "contract_number": CONTRACT_NUMBER,
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=idempotency_key or str(uuid4()),
    )


def _otp_from_latest_email() -> str:
    matches = re.findall(r"(?<![0-9])[0-9]{6}(?![0-9])", mail.outbox[-1].body)
    assert len(matches) == 1
    return matches[0]


def _process_outbox() -> None:
    call_command(
        "process_p1_auth_email_outbox",
        "--once",
        "--batch-size=100",
        verbosity=0,
    )


def _signup(
    client,
    django_capture_on_commit_callbacks,
    *,
    identity_payload: dict | None = None,
    signup_idempotency_key: str | None = None,
):
    _seed()
    with django_capture_on_commit_callbacks(execute=True):
        challenge = _challenge(
            client,
            "/api/v1/auth/contract-verification/challenges",
            payload=identity_payload
            or {"name": CUSTOMER_NAME, "email": CONTRACT_EMAIL},
        )
    _process_outbox()
    otp = _otp_from_latest_email()
    verified = client.post(
        "/api/v1/auth/contract-verification/challenges/"
        f"{challenge.json()['data']['challenge_id']}/verify",
        {"otp_code": otp},
        content_type="application/json",
    )
    response = client.post(
        "/api/v1/auth/signup",
        {
            "claim_ticket": verified.json()["data"]["claim_ticket"],
            "name": CUSTOMER_NAME,
            "email": CONTRACT_EMAIL,
            "username": USERNAME,
            "password": PASSWORD,
            "consents": CONSENTS,
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=signup_idempotency_key or str(uuid4()),
    )
    return challenge, verified, response


def test_contract_challenge_conceals_existence_and_never_returns_otp(
    client,
    django_capture_on_commit_callbacks,
):
    _seed()
    with django_capture_on_commit_callbacks(execute=True):
        known = _challenge(
            client,
            "/api/v1/auth/contract-verification/challenges",
        )
    unknown = _challenge(
        client,
        "/api/v1/auth/contract-verification/challenges",
        payload={
            "customer_number": "SYN-UNKNOWN",
            "contract_number": "SYN-UNKNOWN",
        },
    )
    pending_rows = list(P1AuthEmailOutbox.objects.order_by("created_at"))
    assert len(mail.outbox) == 0
    assert len(pending_rows) == 2
    assert [row.status for row in pending_rows] == [
        P1AuthEmailOutbox.Status.PENDING,
        P1AuthEmailOutbox.Status.SUPPRESSED,
    ]
    assert not re.fullmatch(r"[0-9]{6}", pending_rows[0].encrypted_otp)
    assert pending_rows[1].encrypted_otp == ""
    _process_outbox()

    assert known.status_code == unknown.status_code == 202
    for response in (known, unknown):
        assert set(response.json()["data"]) == {
            "challenge_id",
            "expires_in",
            "resend_after",
            "message",
        }
        serialized = response.content.decode("utf-8")
        assert CONTRACT_EMAIL not in serialized
        assert "otp" not in serialized.casefold()
        assert response["Cache-Control"] == "no-store"
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["p1-auth-test@waterbridge.invalid"]
    assert P1AuthOtpChallenge.objects.filter(target_resolved=True).count() == 1
    assert P1AuthOtpChallenge.objects.filter(target_resolved=False).count() == 1
    assert P1AuthEmailOutbox.objects.filter(
        status=P1AuthEmailOutbox.Status.SENT,
        encrypted_otp="",
    ).count() == 1
    assert P1AuthEmailOutbox.objects.filter(
        status=P1AuthEmailOutbox.Status.SUPPRESSED,
        encrypted_otp="",
    ).count() == 1


def test_approved_test_contact_delivers_to_decrypted_recipient_in_debug(
    client,
    django_capture_on_commit_callbacks,
    settings,
):
    approved_email = "approved-recipient@example.com"
    settings.DEBUG = True
    _seed()
    _convert_seed_contact_to_approved_test(approved_email)

    with django_capture_on_commit_callbacks(execute=True):
        challenge = _challenge(
            client,
            "/api/v1/auth/contract-verification/challenges",
            payload={"name": CUSTOMER_NAME, "email": approved_email},
        )
    _process_outbox()

    assert challenge.status_code == 202
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [approved_email]
    assert approved_email not in challenge.content.decode("utf-8")
    assert P1AuthEmailOutbox.objects.get().status == (
        P1AuthEmailOutbox.Status.SENT
    )


def test_approved_test_contact_delivery_fails_closed_outside_debug(
    client,
    django_capture_on_commit_callbacks,
    settings,
):
    approved_email = "approved-recipient@example.com"
    settings.DEBUG = False
    _seed()
    _convert_seed_contact_to_approved_test(approved_email)

    with django_capture_on_commit_callbacks(execute=True):
        challenge = _challenge(
            client,
            "/api/v1/auth/contract-verification/challenges",
            payload={"name": CUSTOMER_NAME, "email": approved_email},
        )
    _process_outbox()
    outbox = P1AuthEmailOutbox.objects.get()

    assert challenge.status_code == 202
    assert len(mail.outbox) == 0
    assert outbox.status == P1AuthEmailOutbox.Status.PENDING
    assert outbox.attempt_count == 1
    assert outbox.last_error_code == "DELIVERY_FAILED"


def test_signup_creates_real_password_account_link_consents_and_session(
    client,
    django_capture_on_commit_callbacks,
):
    challenge, verified, response = _signup(
        client,
        django_capture_on_commit_callbacks,
    )

    assert challenge.status_code == 202
    assert verified.status_code == 200
    assert response.status_code == 201
    session = response.json()["data"]
    assert session["access_token"]
    assert session["refresh_token"]
    assert session["user"]["display_name"] == CUSTOMER_NAME
    user = User.objects.get(username=USERNAME)
    customer = CustomerProfile.objects.get(customer_no=CUSTOMER_NUMBER)
    assert user.check_password(PASSWORD)
    assert user.email == ""
    assert customer.user == user
    assert CustomerAccountLink.objects.filter(
        customer=customer,
        user=user,
        is_active=True,
    ).count() == 1
    assert P1AccountConsent.objects.filter(user=user).count() == 3


def test_frozen_mobile_contract_identity_completes_signup_and_database_login(
    client,
    django_capture_on_commit_callbacks,
):
    challenge, verified, signup = _signup(
        client,
        django_capture_on_commit_callbacks,
        identity_payload={
            "customer_number": CUSTOMER_NUMBER,
            "contract_number": CONTRACT_NUMBER,
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        {"username": USERNAME, "password": PASSWORD},
        content_type="application/json",
    )

    assert challenge.status_code == 202
    assert verified.status_code == 200
    assert signup.status_code == 201
    assert login.status_code == 200
    assert login.json()["data"]["user"]["role_code"] == "CUSTOMER"


def test_signup_rechecks_mobile_name_and_email_against_verified_ticket(client):
    _seed()
    challenge = _challenge(
        client,
        "/api/v1/auth/contract-verification/challenges",
        payload={"name": CUSTOMER_NAME, "email": CONTRACT_EMAIL},
    )
    _process_outbox()
    verified = client.post(
        "/api/v1/auth/contract-verification/challenges/"
        f"{challenge.json()['data']['challenge_id']}/verify",
        {"otp_code": _otp_from_latest_email()},
        content_type="application/json",
    )
    signup = client.post(
        "/api/v1/auth/signup",
        {
            "claim_ticket": verified.json()["data"]["claim_ticket"],
            "name": "다른 고객 이름",
            "email": CONTRACT_EMAIL,
            "username": USERNAME,
            "password": PASSWORD,
            "consents": CONSENTS,
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )

    assert verified.status_code == 200
    assert signup.status_code == 401
    assert signup.json()["error"]["code"] == "AUTH_VERIFICATION_FAILED"
    assert User.objects.count() == 0
    assert P1AuthTicket.objects.get().consumed_at is None


def test_password_login_uses_database_credentials_and_generic_failure(
    client,
    django_capture_on_commit_callbacks,
):
    _signup(client, django_capture_on_commit_callbacks)

    success = client.post(
        "/api/v1/auth/login",
        {"username": USERNAME, "password": PASSWORD},
        content_type="application/json",
    )
    missing = client.post(
        "/api/v1/auth/login",
        {"username": "not-found", "password": "wrong"},
        content_type="application/json",
    )
    wrong = client.post(
        "/api/v1/auth/login",
        {"username": USERNAME, "password": "wrong"},
        content_type="application/json",
    )

    assert success.status_code == 200
    assert missing.status_code == wrong.status_code == 401
    assert missing.json()["error"] == wrong.json()["error"]
    assert wrong.json()["error"]["code"] == "AUTH_LOGIN_FAILED"


def test_login_rate_bucket_blocks_after_limit_and_resets_after_window(
    client,
    django_capture_on_commit_callbacks,
    settings,
):
    settings.P1_AUTH_LOGIN_MAX_FAILURES = 2
    settings.P1_AUTH_LOGIN_WINDOW_SECONDS = 300
    _signup(client, django_capture_on_commit_callbacks)

    failures = [
        client.post(
            "/api/v1/auth/login",
            {"username": USERNAME, "password": "wrong"},
            content_type="application/json",
        )
        for _ in range(2)
    ]
    limited = client.post(
        "/api/v1/auth/login",
        {"username": USERNAME, "password": PASSWORD},
        content_type="application/json",
    )
    bucket = P1AuthLoginRateBucket.objects.get()

    assert [response.status_code for response in failures] == [401, 401]
    assert limited.status_code == 429
    assert bucket.failure_count == 2

    bucket.window_started_at = timezone.now() - timedelta(seconds=301)
    bucket.save(update_fields=["window_started_at", "updated_at"])
    recovered = client.post(
        "/api/v1/auth/login",
        {"username": USERNAME, "password": PASSWORD},
        content_type="application/json",
    )
    bucket.refresh_from_db()

    assert recovered.status_code == 200
    assert bucket.failure_count == 0


def test_username_recovery_returns_full_username_only_after_email_otp(
    client,
    django_capture_on_commit_callbacks,
):
    _signup(client, django_capture_on_commit_callbacks)
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        challenge = _challenge(
            client,
            "/api/v1/auth/account-recovery/username/challenges",
            payload={"name": CUSTOMER_NAME, "email": CONTRACT_EMAIL},
        )
    _process_outbox()
    response = client.post(
        "/api/v1/auth/account-recovery/username/challenges/"
        f"{challenge.json()['data']['challenge_id']}/verify",
        {"otp_code": _otp_from_latest_email()},
        content_type="application/json",
    )
    replay = client.post(
        "/api/v1/auth/account-recovery/username/challenges/"
        f"{challenge.json()['data']['challenge_id']}/verify",
        {"otp_code": _otp_from_latest_email()},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["data"] == {"masked_username": USERNAME}
    assert response["Cache-Control"] == "no-store"
    assert replay.status_code == 401


def test_password_reset_matches_name_email_username_and_revokes_sessions(
    client,
    django_capture_on_commit_callbacks,
):
    _, _, signup = _signup(client, django_capture_on_commit_callbacks)
    original_refresh = signup.json()["data"]["refresh_token"]
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        challenge = _challenge(
            client,
            "/api/v1/auth/password-reset/challenges",
            payload={
                "name": CUSTOMER_NAME,
                "email": CONTRACT_EMAIL,
                "username": USERNAME,
            },
        )
    _process_outbox()
    verified = client.post(
        "/api/v1/auth/password-reset/challenges/"
        f"{challenge.json()['data']['challenge_id']}/verify",
        {"otp_code": _otp_from_latest_email()},
        content_type="application/json",
    )
    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        {
            "reset_ticket": verified.json()["data"]["reset_ticket"],
            "password": NEW_PASSWORD,
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "password_reset": True,
        "sessions_revoked": True,
    }
    user = User.objects.get(username=USERNAME)
    assert user.check_password(NEW_PASSWORD)
    assert user.auth_version == 2
    assert BlacklistedToken.objects.filter(token__user=user).exists()
    refresh = client.post(
        "/api/v1/auth/refresh",
        {"refresh_token": original_refresh},
        content_type="application/json",
    )
    assert refresh.status_code == 401


def test_challenge_idempotency_replays_without_second_delivery(
    client,
    django_capture_on_commit_callbacks,
):
    _seed()
    key = str(uuid4())
    with django_capture_on_commit_callbacks(execute=True):
        first = _challenge(
            client,
            "/api/v1/auth/contract-verification/challenges",
            idempotency_key=key,
        )
    _process_outbox()
    second = _challenge(
        client,
        "/api/v1/auth/contract-verification/challenges",
        idempotency_key=key,
    )
    conflict = _challenge(
        client,
        "/api/v1/auth/contract-verification/challenges",
        payload={
            "customer_number": "SYN-OTHER",
            "contract_number": "SYN-OTHER",
        },
        idempotency_key=key,
    )
    _process_outbox()

    assert first.json()["data"] == second.json()["data"]
    assert len(mail.outbox) == 1
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "DUPLICATE-EVENT-01"


def test_wrong_otp_is_limited_and_otp_is_never_persisted_plaintext(
    client,
    django_capture_on_commit_callbacks,
):
    _seed()
    with django_capture_on_commit_callbacks(execute=True):
        challenge_response = _challenge(
            client,
            "/api/v1/auth/contract-verification/challenges",
        )
    _process_outbox()
    challenge_id = challenge_response.json()["data"]["challenge_id"]
    issued_otp = _otp_from_latest_email()
    responses = [
        client.post(
            "/api/v1/auth/contract-verification/challenges/"
            f"{challenge_id}/verify",
            {"otp_code": "000000" if issued_otp != "000000" else "999999"},
            content_type="application/json",
        )
        for _ in range(5)
    ]
    challenge = P1AuthOtpChallenge.objects.get(public_id=challenge_id)

    assert [response.status_code for response in responses] == [
        401,
        401,
        401,
        401,
        429,
    ]
    assert responses[-1]["Retry-After"] == "60"
    assert challenge.failure_count == 5
    assert issued_otp not in challenge.otp_digest


def test_cancelled_contract_does_not_borrow_another_active_contract_status(
    client,
):
    _seed()
    active = CustomerSubscription.objects.get(contract_no=CONTRACT_NUMBER)
    CustomerSubscription.objects.create(
        contract_no="SYN-CONTRACT-P1-CANCELLED",
        customer=active.customer,
        product_model=active.product_model,
        serial_no="SYN-P1-CANCELLED-SERIAL",
        management_type_code=active.management_type_code,
        status_code=CustomerSubscription.Status.CANCELLED,
        started_on=active.started_on,
        ended_on=active.started_on,
    )

    response = _challenge(
        client,
        "/api/v1/auth/contract-verification/challenges",
        payload={
            "customer_number": CUSTOMER_NUMBER,
            "contract_number": "SYN-CONTRACT-P1-CANCELLED",
        },
    )
    challenge = P1AuthOtpChallenge.objects.get(
        public_id=response.json()["data"]["challenge_id"]
    )
    _process_outbox()

    assert response.status_code == 202
    assert challenge.target_resolved is False
    assert len(mail.outbox) == 0
    assert P1AuthEmailOutbox.objects.get(challenge=challenge).status == (
        P1AuthEmailOutbox.Status.SUPPRESSED
    )


def test_corrupt_contract_ciphertext_does_not_poison_outbox_worker(client):
    _seed()
    response = _challenge(
        client,
        "/api/v1/auth/contract-verification/challenges",
    )
    challenge = P1AuthOtpChallenge.objects.get(
        public_id=response.json()["data"]["challenge_id"]
    )
    row = P1AuthEmailOutbox.objects.get(challenge=challenge)
    row.max_attempts = 1
    row.save(update_fields=["max_attempts", "updated_at"])
    challenge.contact.encrypted_email = "corrupt-ciphertext"
    challenge.contact.save(update_fields=["encrypted_email", "updated_at"])

    _process_outbox()
    row.refresh_from_db()

    assert len(mail.outbox) == 0
    assert row.status == P1AuthEmailOutbox.Status.FAILED
    assert row.attempt_count == 1
    assert row.encrypted_otp == ""
    assert row.last_error_code == "PROTECTED_DELIVERY_DATA_INVALID"


def test_contract_revocation_before_worker_suppresses_email_delivery(client):
    _seed()
    response = _challenge(
        client,
        "/api/v1/auth/contract-verification/challenges",
    )
    challenge = P1AuthOtpChallenge.objects.get(
        public_id=response.json()["data"]["challenge_id"]
    )
    subscription = CustomerSubscription.objects.get(contract_no=CONTRACT_NUMBER)
    subscription.status_code = CustomerSubscription.Status.CANCELLED
    subscription.ended_on = subscription.started_on
    subscription.save(
        update_fields=["status_code", "ended_on", "updated_at"]
    )

    _process_outbox()
    row = P1AuthEmailOutbox.objects.get(challenge=challenge)

    assert response.status_code == 202
    assert len(mail.outbox) == 0
    assert row.status == P1AuthEmailOutbox.Status.SUPPRESSED
    assert row.encrypted_otp == ""
    assert row.last_error_code == "CHALLENGE_NOT_DELIVERABLE"


def test_invalid_tickets_do_not_create_idempotency_lock_rows(client):
    signup = client.post(
        "/api/v1/auth/signup",
        {
            "claim_ticket": "x" * 32,
            "username": USERNAME,
            "password": PASSWORD,
            "consents": CONSENTS,
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )
    reset = client.post(
        "/api/v1/auth/password-reset/confirm",
        {
            "reset_ticket": "y" * 32,
            "password": NEW_PASSWORD,
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )

    assert signup.status_code == reset.status_code == 401
    assert P1AuthIdempotencyLock.objects.count() == 0


def test_old_signup_idempotency_request_cannot_restore_session_after_reset(
    client,
    django_capture_on_commit_callbacks,
):
    signup_key = str(uuid4())
    _, signup_verified, signup = _signup(
        client,
        django_capture_on_commit_callbacks,
        signup_idempotency_key=signup_key,
    )
    mail.outbox.clear()

    reset_challenge = _challenge(
        client,
        "/api/v1/auth/password-reset/challenges",
        payload={
            "name": CUSTOMER_NAME,
            "email": CONTRACT_EMAIL,
            "username": USERNAME,
        },
    )
    _process_outbox()
    reset_verified = client.post(
        "/api/v1/auth/password-reset/challenges/"
        f"{reset_challenge.json()['data']['challenge_id']}/verify",
        {"otp_code": _otp_from_latest_email()},
        content_type="application/json",
    )
    reset = client.post(
        "/api/v1/auth/password-reset/confirm",
        {
            "reset_ticket": reset_verified.json()["data"]["reset_ticket"],
            "password": NEW_PASSWORD,
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )
    replay = client.post(
        "/api/v1/auth/signup",
        {
            "claim_ticket": signup_verified.json()["data"]["claim_ticket"],
            "name": CUSTOMER_NAME,
            "email": CONTRACT_EMAIL,
            "username": USERNAME,
            "password": PASSWORD,
            "consents": CONSENTS,
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=signup_key,
    )

    assert signup.status_code == 201
    assert reset.status_code == 200
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "AUTH_VERIFICATION_FAILED"


def test_challenge_rate_bucket_limits_distinct_idempotency_keys(
    client,
    settings,
):
    settings.P1_AUTH_CHALLENGE_MAX_PER_WINDOW = 2
    settings.P1_AUTH_OTP_RESEND_SECONDS = 60
    _seed()

    first = _challenge(
        client,
        "/api/v1/auth/contract-verification/challenges",
    )
    bucket = P1AuthChallengeRateBucket.objects.get()
    bucket.last_requested_at = timezone.now() - timedelta(seconds=61)
    bucket.save(update_fields=["last_requested_at", "updated_at"])
    second = _challenge(
        client,
        "/api/v1/auth/contract-verification/challenges",
    )
    bucket.refresh_from_db()
    bucket.last_requested_at = timezone.now() - timedelta(seconds=61)
    bucket.save(update_fields=["last_requested_at", "updated_at"])
    third = _challenge(
        client,
        "/api/v1/auth/contract-verification/challenges",
    )

    assert first.status_code == second.status_code == 202
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "AUTH_RATE_LIMITED"
    assert P1AuthOtpChallenge.objects.count() == 2
    assert P1AuthEmailOutbox.objects.count() == 2


def test_outbox_terminal_state_constraints_reject_encrypted_otp(client):
    _seed()
    response = _challenge(
        client,
        "/api/v1/auth/contract-verification/challenges",
    )
    challenge = P1AuthOtpChallenge.objects.get(
        public_id=response.json()["data"]["challenge_id"]
    )
    row = P1AuthEmailOutbox.objects.get(challenge=challenge)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            P1AuthEmailOutbox.objects.filter(pk=row.pk).update(
                status=P1AuthEmailOutbox.Status.SUPPRESSED,
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            P1AuthEmailOutbox.objects.filter(pk=row.pk).update(
                status=P1AuthEmailOutbox.Status.SENT,
                encrypted_otp="",
                sent_at=None,
                attempt_count=1,
            )


def test_local_file_email_otp_is_scrubbed_after_ttl(settings):
    email_root = (
        Path(settings.BASE_DIR)
        / ".runtime"
        / f"p1-auth-emails-test-{uuid4()}"
    )
    email_root.mkdir(parents=True)
    expired = email_root / "expired-message"
    fresh = email_root / "fresh-message"
    try:
        expired.write_text("OTP 123456", encoding="utf-8")
        fresh.write_text("OTP 654321", encoding="utf-8")
        settings.EMAIL_BACKEND = (
            "django.core.mail.backends.filebased.EmailBackend"
        )
        settings.EMAIL_FILE_PATH = email_root
        settings.P1_AUTH_OTP_TTL_SECONDS = 300
        old_timestamp = (
            timezone.now() - timedelta(seconds=301)
        ).timestamp()
        os.utime(expired, (old_timestamp, old_timestamp))

        removed = P1AuthEmailOutboxService.scrub_expired_local_email_files()

        assert removed == 1
        assert not expired.exists()
        assert fresh.exists()
    finally:
        for candidate in email_root.iterdir():
            candidate.unlink(missing_ok=True)
        email_root.rmdir()


def test_exact_contract_revocation_blocks_otp_verify_even_if_another_is_active(
    client,
):
    _seed()
    challenge_response = _challenge(
        client,
        "/api/v1/auth/contract-verification/challenges",
    )
    _process_outbox()
    otp_code = _otp_from_latest_email()
    challenged = P1AuthOtpChallenge.objects.get(
        public_id=challenge_response.json()["data"]["challenge_id"]
    )
    active = CustomerSubscription.objects.get(contract_no=CONTRACT_NUMBER)
    assert challenged.subscription_id == active.pk
    CustomerSubscription.objects.create(
        contract_no="SYN-CONTRACT-P1-OTHER-ACTIVE",
        customer=active.customer,
        product_model=active.product_model,
        serial_no="SYN-P1-OTHER-ACTIVE-SERIAL",
        management_type_code=active.management_type_code,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=active.started_on,
    )
    active.status_code = CustomerSubscription.Status.CANCELLED
    active.ended_on = active.started_on
    active.save(update_fields=["status_code", "ended_on", "updated_at"])

    verified = client.post(
        "/api/v1/auth/contract-verification/challenges/"
        f"{challenge_response.json()['data']['challenge_id']}/verify",
        {"otp_code": otp_code},
        content_type="application/json",
    )

    assert verified.status_code == 401
    assert verified.json()["error"]["code"] == "AUTH_VERIFICATION_FAILED"
    assert P1AuthTicket.objects.count() == 0


def test_contact_revocation_after_verify_blocks_signup_ticket(client):
    _seed()
    challenge_response = _challenge(
        client,
        "/api/v1/auth/contract-verification/challenges",
    )
    _process_outbox()
    verified = client.post(
        "/api/v1/auth/contract-verification/challenges/"
        f"{challenge_response.json()['data']['challenge_id']}/verify",
        {"otp_code": _otp_from_latest_email()},
        content_type="application/json",
    )
    contact = ContractEmailContact.objects.get()
    contact.is_primary = False
    contact.is_active = False
    contact.save(update_fields=["is_primary", "is_active", "updated_at"])

    signup = client.post(
        "/api/v1/auth/signup",
        {
            "claim_ticket": verified.json()["data"]["claim_ticket"],
            "username": USERNAME,
            "password": PASSWORD,
            "consents": CONSENTS,
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )

    assert verified.status_code == 200
    assert signup.status_code == 401
    assert User.objects.count() == 0
    assert CustomerAccountLink.objects.count() == 0
    assert P1AccountConsent.objects.count() == 0


def test_link_revocation_after_verify_blocks_password_reset(
    client,
    django_capture_on_commit_callbacks,
):
    _signup(client, django_capture_on_commit_callbacks)
    mail.outbox.clear()
    challenge_response = _challenge(
        client,
        "/api/v1/auth/password-reset/challenges",
        payload={
            "name": CUSTOMER_NAME,
            "email": CONTRACT_EMAIL,
            "username": USERNAME,
        },
    )
    _process_outbox()
    verified = client.post(
        "/api/v1/auth/password-reset/challenges/"
        f"{challenge_response.json()['data']['challenge_id']}/verify",
        {"otp_code": _otp_from_latest_email()},
        content_type="application/json",
    )
    link = CustomerAccountLink.objects.get(is_active=True)
    link.is_active = False
    link.revoked_at = timezone.now()
    link.save(update_fields=["is_active", "revoked_at", "updated_at"])

    reset = client.post(
        "/api/v1/auth/password-reset/confirm",
        {
            "reset_ticket": verified.json()["data"]["reset_ticket"],
            "password": NEW_PASSWORD,
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )
    user = User.objects.get(username=USERNAME)

    assert verified.status_code == 200
    assert reset.status_code == 401
    assert user.auth_version == 1
    assert user.check_password(PASSWORD)


def test_older_reset_ticket_cannot_overwrite_a_newer_password(
    client,
    django_capture_on_commit_callbacks,
):
    _signup(client, django_capture_on_commit_callbacks)
    reset_tickets = []
    for index in range(2):
        mail.outbox.clear()
        if index:
            bucket = P1AuthChallengeRateBucket.objects.get(
                purpose=P1AuthOtpChallenge.Purpose.PASSWORD_RESET
            )
            bucket.last_requested_at = timezone.now() - timedelta(seconds=61)
            bucket.save(update_fields=["last_requested_at", "updated_at"])
        challenge_response = _challenge(
            client,
            "/api/v1/auth/password-reset/challenges",
            payload={
                "name": CUSTOMER_NAME,
                "email": CONTRACT_EMAIL,
                "username": USERNAME,
            },
        )
        _process_outbox()
        verified = client.post(
            "/api/v1/auth/password-reset/challenges/"
            f"{challenge_response.json()['data']['challenge_id']}/verify",
            {"otp_code": _otp_from_latest_email()},
            content_type="application/json",
        )
        assert verified.status_code == 200
        reset_tickets.append(verified.json()["data"]["reset_ticket"])

    first = client.post(
        "/api/v1/auth/password-reset/confirm",
        {"reset_ticket": reset_tickets[0], "password": NEW_PASSWORD},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )
    stale = client.post(
        "/api/v1/auth/password-reset/confirm",
        {"reset_ticket": reset_tickets[1], "password": THIRD_PASSWORD},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )
    user = User.objects.get(username=USERNAME)

    assert first.status_code == 200
    assert stale.status_code == 401
    assert user.auth_version == 2
    assert user.check_password(NEW_PASSWORD)
    assert not user.check_password(THIRD_PASSWORD)
