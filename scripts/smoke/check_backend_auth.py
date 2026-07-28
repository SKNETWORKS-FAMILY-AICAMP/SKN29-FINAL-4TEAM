"""실제 Django·PostgreSQL Health/Auth 흐름을 비밀값 출력 없이 점검한다."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import sys
import uuid
from collections.abc import Mapping
from typing import Any

import httpx


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_DEMO_USER_CODE = "DEMO-CUSTOMER-001"
ACCESS_EXPIRES_IN = 60 * 60
REFRESH_EXPIRES_IN = 7 * 24 * 60 * 60
FORBIDDEN_USER_KEYS = {
    "password",
    "phone",
    "address_line1",
    "address_line2",
    "access_token",
    "refresh_token",
}


class SmokeFailure(RuntimeError):
    """비밀값을 포함하지 않는 Smoke 검증 실패."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def require_status(
    response: httpx.Response,
    expected: int,
    step: str,
) -> None:
    require(
        response.status_code == expected,
        f"{step}: expected_status={expected}, "
        f"actual_status={response.status_code}",
    )


def response_json(
    response: httpx.Response,
    step: str,
) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise SmokeFailure(f"{step}: response_is_not_json") from exc
    require(isinstance(payload, dict), f"{step}: response_is_not_object")
    return payload


def require_correlation_id(
    response: httpx.Response,
    *,
    expected: str | None = None,
) -> str:
    correlation_id = response.headers.get("X-Correlation-ID", "")
    try:
        uuid.UUID(correlation_id)
    except ValueError as exc:
        raise SmokeFailure("correlation: response_header_is_not_uuid") from exc
    if expected is not None:
        require(
            correlation_id == expected,
            "correlation: valid_request_id_was_not_reused",
        )
    return correlation_id


def require_success_wrapper(
    response: httpx.Response,
    step: str,
) -> dict[str, Any]:
    require_status(response, 200, step)
    payload = response_json(response, step)
    require(payload.get("success") is True, f"{step}: success_is_not_true")
    require(payload.get("error") is None, f"{step}: error_is_not_null")
    require(isinstance(payload.get("data"), dict), f"{step}: data_missing")

    response_correlation_id = require_correlation_id(response)
    metadata = payload.get("metadata")
    require(isinstance(metadata, dict), f"{step}: metadata_missing")
    require(
        metadata.get("correlation_id") == response_correlation_id,
        f"{step}: wrapper_header_correlation_mismatch",
    )
    return payload["data"]


def require_error_code(
    response: httpx.Response,
    *,
    status_code: int,
    error_code: str,
    step: str,
) -> None:
    require_status(response, status_code, step)
    payload = response_json(response, step)
    require(payload.get("success") is False, f"{step}: success_is_not_false")
    error = payload.get("error")
    require(isinstance(error, dict), f"{step}: error_missing")
    require(error.get("code") == error_code, f"{step}: error_code_mismatch")
    require_correlation_id(response)


def collect_mapping_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            keys.add(str(key))
            keys.update(collect_mapping_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(collect_mapping_keys(child))
    return keys


def jwt_numeric_claim(raw_token: str, claim_name: str, step: str) -> int:
    """서명 검증 용도가 아닌 Smoke 구조 비교용 숫자 Claim을 읽는다."""

    parts = raw_token.split(".")
    require(len(parts) == 3, f"{step}: token_structure_invalid")
    encoded_payload = parts[1]
    encoded_payload += "=" * (-len(encoded_payload) % 4)
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(
                encoded_payload.encode("ascii")
            ).decode("utf-8")
        )
    except (
        binascii.Error,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
    ) as exc:
        raise SmokeFailure(f"{step}: token_payload_invalid") from exc

    require(isinstance(payload, dict), f"{step}: token_payload_not_object")
    value = payload.get(claim_name)
    require(
        isinstance(value, int) and not isinstance(value, bool),
        f"{step}: {claim_name}_claim_invalid",
    )
    return value


def run_smoke(
    *,
    base_url: str,
    demo_user_code: str,
) -> dict[str, Any]:
    with httpx.Client(
        base_url=base_url,
        timeout=10.0,
        trust_env=False,
    ) as client:
        health = client.get("/health")
        require_status(health, 200, "health")
        require(health.content == b"", "health: body_is_not_empty")
        require_correlation_id(health)

        requested_correlation_id = str(uuid.uuid4())
        correlated_health = client.get(
            "/health",
            headers={"X-Correlation-ID": requested_correlation_id},
        )
        require_status(correlated_health, 200, "health_correlation")
        require_correlation_id(
            correlated_health,
            expected=requested_correlation_id,
        )

        allowed_origin = "http://localhost:5173"
        allowed_cors = client.get(
            "/health",
            headers={"Origin": allowed_origin},
        )
        require_status(allowed_cors, 200, "cors_allowed")
        require(
            allowed_cors.headers.get("Access-Control-Allow-Origin")
            == allowed_origin,
            "cors_allowed: origin_header_missing",
        )

        denied_cors = client.get(
            "/health",
            headers={"Origin": "https://unapproved.example"},
        )
        require_status(denied_cors, 200, "cors_denied")
        require(
            "Access-Control-Allow-Origin" not in denied_cors.headers,
            "cors_denied: unapproved_origin_was_allowed",
        )

        login = client.post(
            "/api/v1/auth/demo-login",
            json={"demo_user_code": demo_user_code},
        )
        session = require_success_wrapper(login, "demo_login")
        access_token = session.get("access_token")
        refresh_token = session.get("refresh_token")
        require(
            isinstance(access_token, str) and bool(access_token),
            "demo_login: access_token_missing",
        )
        require(
            isinstance(refresh_token, str) and bool(refresh_token),
            "demo_login: refresh_token_missing",
        )
        require(
            session.get("access_expires_in") == ACCESS_EXPIRES_IN,
            "demo_login: access_lifetime_mismatch",
        )
        require(
            session.get("refresh_expires_in") == REFRESH_EXPIRES_IN,
            "demo_login: refresh_lifetime_mismatch",
        )
        original_refresh_exp = jwt_numeric_claim(
            refresh_token,
            "exp",
            "demo_login",
        )

        me = client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user = require_success_wrapper(me, "me")
        require(user.get("role_code") == "CUSTOMER", "me: role_mismatch")
        exposed_keys = collect_mapping_keys(user) & FORBIDDEN_USER_KEYS
        require(not exposed_keys, "me: sensitive_projection_key_exposed")

        refresh = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        replacement = require_success_wrapper(refresh, "refresh")
        replacement_access_token = replacement.get("access_token")
        replacement_refresh_token = replacement.get("refresh_token")
        require(
            replacement_access_token != access_token,
            "refresh: access_token_not_rotated",
        )
        require(
            replacement_refresh_token != refresh_token,
            "refresh: refresh_token_not_rotated",
        )
        require(
            replacement.get("access_expires_in") == ACCESS_EXPIRES_IN,
            "refresh: access_lifetime_mismatch",
        )
        require(
            isinstance(replacement.get("refresh_expires_in"), int)
            and not isinstance(
                replacement.get("refresh_expires_in"),
                bool,
            )
            and 1 <= replacement["refresh_expires_in"]
            <= session["refresh_expires_in"],
            "refresh: remaining_lifetime_out_of_range",
        )
        replacement_refresh_exp = jwt_numeric_claim(
            replacement_refresh_token,
            "exp",
            "refresh",
        )
        require(
            replacement_refresh_exp == original_refresh_exp,
            "refresh: absolute_expiry_was_extended",
        )

        refresh_replay = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        require_error_code(
            refresh_replay,
            status_code=401,
            error_code="AUTH_REQUIRED",
            step="refresh_replay",
        )

        logout = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": replacement_refresh_token},
        )
        logout_data = require_success_wrapper(logout, "logout")
        require(logout_data == {"revoked": True}, "logout: result_mismatch")

        logout_replay = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": replacement_refresh_token},
        )
        require_error_code(
            logout_replay,
            status_code=401,
            error_code="AUTH_REQUIRED",
            step="logout_replay",
        )

        unauthenticated_me = client.get("/api/v1/me")
        require_error_code(
            unauthenticated_me,
            status_code=401,
            error_code="AUTH_REQUIRED",
            step="unauthenticated_me",
        )

        rejected_login = client.post(
            "/api/v1/auth/demo-login",
            json={"demo_user_code": "DEMO-NOT-ALLOWLISTED-999"},
        )
        require_error_code(
            rejected_login,
            status_code=401,
            error_code="AUTH_REQUIRED",
            step="rejected_demo_login",
        )

    return {
        "status": "PASSED",
        "base_url": base_url,
        "checks": {
            "health": {
                "status_code": 200,
                "empty_body": True,
                "correlation_id_issued": True,
                "correlation_id_reused": True,
            },
            "cors": {
                "allowed_origin": True,
                "unapproved_origin_rejected": True,
            },
            "demo_login": {
                "status_code": 200,
                "role_code": "CUSTOMER",
                "access_expires_in": ACCESS_EXPIRES_IN,
                "refresh_expires_in": REFRESH_EXPIRES_IN,
                "tokens_redacted": True,
            },
            "me": {
                "status_code": 200,
                "sensitive_projection_keys_absent": True,
            },
            "refresh": {
                "rotated": True,
                "remaining_lifetime_in_range": True,
                "absolute_expiry_preserved": True,
                "previous_token_replay_status": 401,
            },
            "logout": {
                "revoked": True,
                "revoked_token_replay_status": 401,
            },
            "errors": {
                "missing_auth_status": 401,
                "unapproved_demo_status": 401,
                "error_code": "AUTH_REQUIRED",
            },
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--demo-user-code",
        default=DEFAULT_DEMO_USER_CODE,
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    try:
        result = run_smoke(
            base_url=args.base_url.rstrip("/"),
            demo_user_code=args.demo_user_code,
        )
    except (SmokeFailure, httpx.HTTPError) as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "tokens_redacted": True,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
