"""T-017 Demo 로그인·JWT rotation·폐기·현재 사용자 API 검증."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from django.test import override_settings
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.models import CustomerProfile, User


pytestmark = pytest.mark.django_db

DEMO_CODE = "DEMO-CUSTOMER-001"


@pytest.fixture
def demo_customer():
    user = User.objects.create_user(
        id="DEMO-USR-001",
        username=DEMO_CODE,
        full_name="합성 고객 001",
        role_code=User.Role.CUSTOMER,
    )
    CustomerProfile.objects.create(
        id="DEMO-CUS-001",
        user=user,
        customer_no="SYN-CUSTOMER-001",
        customer_name="합성 고객 001",
        is_synthetic=True,
    )
    return user


def login(client):
    return client.post(
        "/api/v1/auth/demo-login",
        {"demo_user_code": DEMO_CODE},
        content_type="application/json",
    )


@override_settings(
    DEMO_LOGIN_ENABLED=True,
    DEMO_LOGIN_CODES={DEMO_CODE},
)
def test_demo_login_issues_role_bound_token_pair(client, demo_customer):
    response = login(client)

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    session = payload["data"]
    access = AccessToken(session["access_token"])
    refresh = RefreshToken(session["refresh_token"])
    assert session["token_type"] == "Bearer"
    assert session["access_expires_in"] == 60 * 60
    assert session["refresh_expires_in"] == 7 * 24 * 60 * 60
    assert access["sub"] == demo_customer.pk
    assert access["role_code"] == User.Role.CUSTOMER
    assert refresh["role_code"] == User.Role.CUSTOMER


def test_demo_login_is_disabled_by_default(client, demo_customer):
    response = login(client)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@override_settings(
    DEMO_LOGIN_ENABLED=True,
    DEMO_LOGIN_CODES={"DEMO-OTHER-001"},
)
def test_demo_login_rejects_non_allowlisted_user(client, demo_customer):
    response = login(client)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


@override_settings(
    DEMO_LOGIN_ENABLED=True,
    DEMO_LOGIN_CODES={DEMO_CODE},
)
def test_me_returns_safe_projection_only(client, demo_customer):
    session = login(client).json()["data"]
    response = client.get(
        "/api/v1/me",
        HTTP_AUTHORIZATION=f"Bearer {session['access_token']}",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == demo_customer.pk
    assert data["role_code"] == User.Role.CUSTOMER
    assert data["customer_profile"]["customer_no"] == "SYN-CUSTOMER-001"
    serialized = response.content.decode("utf-8")
    for forbidden in (
        "password",
        "phone",
        "address_line1",
        "address_line2",
        "access_token",
        "refresh_token",
    ):
        assert forbidden not in serialized


def test_me_requires_valid_bearer_token(client, demo_customer):
    missing = client.get("/api/v1/me")
    malformed = client.get(
        "/api/v1/me",
        HTTP_AUTHORIZATION="Bearer not-a-jwt",
    )

    assert missing.status_code == 401
    assert malformed.status_code == 401
    assert missing.json()["error"]["code"] == "AUTH_REQUIRED"
    assert malformed.json()["error"]["code"] == "AUTH_REQUIRED"


@override_settings(
    DEMO_LOGIN_ENABLED=True,
    DEMO_LOGIN_CODES={DEMO_CODE},
)
def test_refresh_rotates_and_blacklists_previous_token(
    client,
    demo_customer,
):
    original = login(client).json()["data"]
    refreshed = client.post(
        "/api/v1/auth/refresh",
        {"refresh_token": original["refresh_token"]},
        content_type="application/json",
    )

    assert refreshed.status_code == 200
    replacement = refreshed.json()["data"]
    assert replacement["refresh_token"] != original["refresh_token"]
    assert replacement["access_token"] != original["access_token"]

    replay = client.post(
        "/api/v1/auth/refresh",
        {"refresh_token": original["refresh_token"]},
        content_type="application/json",
    )
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "AUTH_REQUIRED"


@override_settings(
    DEMO_LOGIN_ENABLED=True,
    DEMO_LOGIN_CODES={DEMO_CODE},
)
def test_refresh_rotation_preserves_first_absolute_expiry(
    client,
    demo_customer,
):
    original = login(client).json()["data"]
    original_refresh = RefreshToken(original["refresh_token"])
    original_exp = int(original_refresh["exp"])
    two_hours_later = datetime.fromtimestamp(
        int(original_refresh["iat"]),
        tz=timezone.utc,
    ) + timedelta(hours=2)

    with patch(
        "rest_framework_simplejwt.tokens.aware_utcnow",
        return_value=two_hours_later,
    ):
        response = client.post(
            "/api/v1/auth/refresh",
            {"refresh_token": original["refresh_token"]},
            content_type="application/json",
        )

    assert response.status_code == 200
    replacement = response.json()["data"]
    replacement_refresh = RefreshToken(
        replacement["refresh_token"],
        verify=False,
    )
    assert int(replacement_refresh["exp"]) == original_exp
    assert replacement["refresh_expires_in"] == (
        original_exp - int(replacement_refresh["iat"])
    )
    assert replacement["refresh_expires_in"] == (
        7 * 24 * 60 * 60 - 2 * 60 * 60
    )

    outstanding = OutstandingToken.objects.get(
        jti=str(replacement_refresh["jti"])
    )
    assert int(outstanding.expires_at.timestamp()) == original_exp


@override_settings(
    DEMO_LOGIN_ENABLED=True,
    DEMO_LOGIN_CODES={DEMO_CODE},
)
def test_logout_revokes_refresh_token(client, demo_customer):
    session = login(client).json()["data"]
    logout = client.post(
        "/api/v1/auth/logout",
        {"refresh_token": session["refresh_token"]},
        content_type="application/json",
    )
    replay = client.post(
        "/api/v1/auth/refresh",
        {"refresh_token": session["refresh_token"]},
        content_type="application/json",
    )

    assert logout.status_code == 200
    assert logout.json()["data"] == {"revoked": True}
    assert replay.status_code == 401


@override_settings(
    DEMO_LOGIN_ENABLED=True,
    DEMO_LOGIN_CODES={DEMO_CODE},
)
@pytest.mark.parametrize("change", ["inactive", "role"])
def test_access_token_rechecks_current_user_state(
    client,
    demo_customer,
    change,
):
    access_token = login(client).json()["data"]["access_token"]
    if change == "inactive":
        demo_customer.is_active = False
        demo_customer.save(update_fields=["is_active"])
    else:
        demo_customer.role_code = User.Role.CONSULTANT
        demo_customer.employee_no = "DEMO-EMP-CNS-001"
        demo_customer.save(
            update_fields=["role_code", "employee_no"]
        )

    response = client.get(
        "/api/v1/me",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


@override_settings(
    DEMO_LOGIN_ENABLED=True,
    DEMO_LOGIN_CODES={DEMO_CODE},
)
def test_refresh_rechecks_current_role(client, demo_customer):
    refresh_token = login(client).json()["data"]["refresh_token"]
    demo_customer.role_code = User.Role.CONSULTANT
    demo_customer.employee_no = "DEMO-EMP-CNS-002"
    demo_customer.save(update_fields=["role_code", "employee_no"])

    response = client.post(
        "/api/v1/auth/refresh",
        {"refresh_token": refresh_token},
        content_type="application/json",
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"
