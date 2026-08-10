"""T-017 Demo 로그인·JWT rotation·폐기·현재 사용자 API 검증."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone as django_timezone
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.models import CustomerProfile, User
from apps.accounts.repositories.account_repository import AccountRepository


pytestmark = pytest.mark.django_db

DEMO_CODE = "DEMO-CUSTOMER-001"
SYNTHETIC_CUSTOMER_CODE = "SYN-CUSTOMER-001"
IMPORTED_USERNAME = "CUS-0001"


@pytest.fixture
def demo_customer():
    user = User.objects.create_user(
        username=DEMO_CODE,
        full_name="합성 고객 001",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    CustomerProfile.objects.create(
        user=user,
        customer_no="SYN-CUSTOMER-001",
        customer_name="합성 고객 001",
        is_synthetic=True,
    )
    return user


@pytest.fixture
def imported_customer():
    user = User.objects.create_user(
        username=IMPORTED_USERNAME,
        full_name="합성 적재 고객 001",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    CustomerProfile.objects.create(
        user=user,
        customer_no=SYNTHETIC_CUSTOMER_CODE,
        customer_name="합성 적재 고객 001",
        is_synthetic=True,
    )
    return user


def login(client):
    return client.post(
        "/api/v1/auth/demo-login",
        {"demo_user_code": DEMO_CODE},
        content_type="application/json",
    )


def login_with_code(client, code):
    return client.post(
        "/api/v1/auth/demo-login",
        {"demo_user_code": code},
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
    assert access["sub"] == str(demo_customer.public_id)
    assert access["role_code"] == User.Role.CUSTOMER
    assert refresh["role_code"] == User.Role.CUSTOMER


@override_settings(
    DEMO_LOGIN_ENABLED=True,
    DEMO_LOGIN_CODES={DEMO_CODE},
)
def test_demo_login_keeps_access_lifetime_across_second_boundary(
    client,
    demo_customer,
):
    refresh_time = datetime(
        2026,
        7,
        29,
        0,
        0,
        0,
        900_000,
        tzinfo=timezone.utc,
    )
    access_time = refresh_time + timedelta(milliseconds=200)

    with patch(
        "rest_framework_simplejwt.tokens.aware_utcnow",
        side_effect=(refresh_time, access_time),
    ):
        response = login(client)

    assert response.status_code == 200
    session = response.json()["data"]
    access = AccessToken(session["access_token"], verify=False)
    assert session["access_expires_in"] == 60 * 60
    assert int(access["exp"]) - int(access["iat"]) == 60 * 60


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
    DEMO_LOGIN_CODES={SYNTHETIC_CUSTOMER_CODE},
)
def test_synthetic_customer_code_authenticates_imported_customer_username(
    client,
    imported_customer,
):
    response = login_with_code(client, SYNTHETIC_CUSTOMER_CODE)

    assert response.status_code == 200
    session = response.json()["data"]
    access = AccessToken(session["access_token"])
    assert imported_customer.username == IMPORTED_USERNAME
    assert access["sub"] == str(imported_customer.public_id)
    assert access["role_code"] == User.Role.CUSTOMER
    assert session["user"]["customer_profile"]["customer_no"] == (
        SYNTHETIC_CUSTOMER_CODE
    )


@override_settings(
    DEMO_LOGIN_ENABLED=True,
    DEMO_LOGIN_CODES={IMPORTED_USERNAME},
)
def test_direct_imported_username_remains_rejected(
    client,
    imported_customer,
):
    response = login_with_code(client, IMPORTED_USERNAME)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


@override_settings(
    DEMO_LOGIN_ENABLED=True,
    DEMO_LOGIN_CODES={SYNTHETIC_CUSTOMER_CODE},
)
@pytest.mark.parametrize("invalid_state", ["inactive", "deleted", "role"])
def test_synthetic_customer_code_rejects_invalid_account_or_profile_state(
    client,
    imported_customer,
    invalid_state,
):
    if invalid_state == "inactive":
        User.objects.filter(pk=imported_customer.pk).update(is_active=False)
    elif invalid_state == "deleted":
        CustomerProfile.objects.filter(user=imported_customer).update(
            deleted_at=django_timezone.now()
        )
    else:
        User.objects.filter(pk=imported_customer.pk).update(
            role_code=User.Role.CONSULTANT,
            employee_no="SYN-EMP-101",
        )

    response = login_with_code(client, SYNTHETIC_CUSTOMER_CODE)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_synthetic_alias_repository_requires_synthetic_profile():
    with patch(
        "apps.accounts.repositories.account_repository.User.objects.filter"
    ) as filter_mock:
        related = filter_mock.return_value.select_related.return_value
        related.first.return_value = None
        AccountRepository.find_active_by_demo_code(SYNTHETIC_CUSTOMER_CODE)

    filter_mock.assert_called_once_with(
        is_active=True,
        is_synthetic=True,
        role_code=User.Role.CUSTOMER,
        customer_profile__customer_no=SYNTHETIC_CUSTOMER_CODE,
        customer_profile__is_synthetic=True,
        customer_profile__deleted_at__isnull=True,
    )


def test_demo_repository_requires_synthetic_user_boundary():
    with patch(
        "apps.accounts.repositories.account_repository.User.objects.filter"
    ) as filter_mock:
        related = filter_mock.return_value.select_related.return_value
        related.first.return_value = None
        AccountRepository.find_active_by_demo_code(DEMO_CODE)

    filter_mock.assert_called_once_with(
        username=DEMO_CODE,
        is_active=True,
        is_synthetic=True,
    )


def test_subject_repository_rejects_non_uuid_without_pk_fallback():
    with patch(
        "apps.accounts.repositories.account_repository.User.objects.filter"
    ) as filter_mock:
        user = AccountRepository.find_active_by_subject("DEMO-USR-001")

    assert user is None
    filter_mock.assert_not_called()


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
    assert data["id"] == str(demo_customer.public_id)
    assert data["customer_profile"]["id"] == str(
        demo_customer.customer_profile.public_id
    )
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


def test_me_rejects_legacy_string_primary_key_subject(
    client,
    demo_customer,
):
    legacy_access = AccessToken.for_user(demo_customer)
    legacy_access["sub"] = "DEMO-USR-001"
    legacy_access["role_code"] = demo_customer.role_code

    response = client.get(
        "/api/v1/me",
        HTTP_AUTHORIZATION=f"Bearer {legacy_access}",
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


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


def test_refresh_rejects_legacy_string_primary_key_subject(
    client,
    demo_customer,
):
    legacy_refresh = RefreshToken.for_user(demo_customer)
    legacy_refresh["sub"] = "DEMO-USR-001"
    legacy_refresh["role_code"] = demo_customer.role_code
    raw_legacy_refresh = str(legacy_refresh)

    response = client.post(
        "/api/v1/auth/refresh",
        {"refresh_token": raw_legacy_refresh},
        content_type="application/json",
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


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
