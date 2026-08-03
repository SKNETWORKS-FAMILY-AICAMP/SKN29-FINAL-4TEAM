"""T-017 네 역할 Login·JWT Claim·/me·Refresh·Logout Matrix."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.test import override_settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.models import User


pytestmark = pytest.mark.django_db

ROLE_CASES = (
    ("DEMO-CUSTOMER-001", User.Role.CUSTOMER, True),
    ("DEMO-CONSULTANT-001", User.Role.CONSULTANT, False),
    ("DEMO-TECHNICIAN-001", User.Role.TECHNICIAN, False),
    ("DEMO-OPERATOR-001", User.Role.OPERATOR, False),
)
DEMO_CODES = frozenset(code for code, _, _ in ROLE_CASES)


def assert_token_claims(raw_token, token_class, user, role, token_type):
    token = token_class(raw_token)
    assert token["sub"] == str(user.public_id)
    assert token["role_code"] == role
    assert token["token_type"] == token_type


@override_settings(
    DEMO_LOGIN_ENABLED=True,
    DEMO_LOGIN_CODES=DEMO_CODES,
)
@pytest.mark.parametrize(
    ("demo_code", "expected_role", "has_customer_profile"),
    ROLE_CASES,
    ids=("customer", "consultant", "technician", "operator"),
)
def test_four_role_auth_lifecycle_matrix(
    client,
    demo_code,
    expected_role,
    has_customer_profile,
):
    """Seed 네 역할이 같은 인증 수명주기 계약을 지키는지 검증한다."""

    call_command("seed_demo_accounts", stdout=StringIO())
    user = User.objects.get(username=demo_code)

    login = client.post(
        "/api/v1/auth/demo-login",
        {"demo_user_code": demo_code},
        content_type="application/json",
    )
    assert login.status_code == 200

    session = login.json()["data"]
    assert session["token_type"] == "Bearer"
    assert session["user"]["id"] == str(user.public_id)
    assert session["user"]["role_code"] == expected_role
    assert session["user"]["is_active"] is True
    assert (
        session["user"]["customer_profile"] is not None
    ) is has_customer_profile

    assert_token_claims(
        session["access_token"],
        AccessToken,
        user,
        expected_role,
        "access",
    )
    assert_token_claims(
        session["refresh_token"],
        RefreshToken,
        user,
        expected_role,
        "refresh",
    )

    me = client.get(
        "/api/v1/me",
        HTTP_AUTHORIZATION=f"Bearer {session['access_token']}",
    )
    assert me.status_code == 200
    assert me.json()["data"] == session["user"]

    refresh = client.post(
        "/api/v1/auth/refresh",
        {"refresh_token": session["refresh_token"]},
        content_type="application/json",
    )
    assert refresh.status_code == 200

    replacement = refresh.json()["data"]
    assert replacement["access_token"] != session["access_token"]
    assert replacement["refresh_token"] != session["refresh_token"]
    assert replacement["user"] == session["user"]

    assert_token_claims(
        replacement["access_token"],
        AccessToken,
        user,
        expected_role,
        "access",
    )
    assert_token_claims(
        replacement["refresh_token"],
        RefreshToken,
        user,
        expected_role,
        "refresh",
    )

    refreshed_me = client.get(
        "/api/v1/me",
        HTTP_AUTHORIZATION=f"Bearer {replacement['access_token']}",
    )
    assert refreshed_me.status_code == 200
    assert refreshed_me.json()["data"] == session["user"]

    logout = client.post(
        "/api/v1/auth/logout",
        {"refresh_token": replacement["refresh_token"]},
        content_type="application/json",
    )
    assert logout.status_code == 200
    assert logout.json()["data"] == {"revoked": True}

    replay = client.post(
        "/api/v1/auth/refresh",
        {"refresh_token": replacement["refresh_token"]},
        content_type="application/json",
    )
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "AUTH_REQUIRED"
