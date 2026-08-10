"""Probe the live Week 4 Web-to-Backend service boundary safely.

The command uses only seeded synthetic demo accounts.  Authentication tokens
are held in memory and are never included in the JSON result.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from typing import Any

import httpx


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
CUSTOMER_CODE = "SYN-CUSTOMER-001"
CONSULTANT_CODE = "DEMO-CONSULTANT-001"


class SmokeFailure(RuntimeError):
    """A live verification failure that contains no credentials."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def payload(response: httpx.Response, step: str) -> dict[str, Any]:
    try:
        value = response.json()
    except ValueError as exc:
        raise SmokeFailure(f"{step}: response_is_not_json") from exc
    require(isinstance(value, dict), f"{step}: response_is_not_object")
    return value


def require_status(
    response: httpx.Response,
    expected: int,
    step: str,
) -> dict[str, Any]:
    require(
        response.status_code == expected,
        f"{step}: expected={expected}, actual={response.status_code}",
    )
    return payload(response, step)


def require_error(
    response: httpx.Response,
    *,
    expected_status: int,
    expected_code: str,
    step: str,
) -> None:
    body = require_status(response, expected_status, step)
    error = body.get("error")
    require(isinstance(error, dict), f"{step}: error_missing")
    require(
        error.get("code") == expected_code,
        f"{step}: expected_code={expected_code}, "
        f"actual_code={error.get('code')}",
    )


def login(client: httpx.Client, demo_user_code: str) -> str:
    body = require_status(
        client.post(
            "/api/v1/auth/demo-login",
            json={"demo_user_code": demo_user_code},
        ),
        200,
        f"login:{demo_user_code}",
    )
    data = body.get("data")
    require(isinstance(data, dict), "login: data_missing")
    token = data.get("access_token")
    require(isinstance(token, str) and token, "login: token_missing")
    return token


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def route_probe(
    client: httpx.Client,
    *,
    token: str,
    inquiry_id: str,
) -> list[dict[str, Any]]:
    headers = authorization(token)
    write_headers = {
        **headers,
        "Idempotency-Key": f"qa-route-{uuid.uuid4().hex}",
        "X-Correlation-ID": str(uuid.uuid4()),
    }
    fake_visit_id = str(uuid.uuid4())
    requests = (
        ("consultant_list", "GET", "/api/v1/inquiries", None, headers),
        (
            "consultant_detail",
            "GET",
            f"/api/v1/inquiries/{inquiry_id}",
            None,
            headers,
        ),
        (
            "start_consultation",
            "POST",
            f"/api/v1/inquiries/{inquiry_id}/start-consultation",
            {"state_version": 2},
            write_headers,
        ),
        (
            "save_consultation",
            "PATCH",
            f"/api/v1/inquiries/{inquiry_id}/consultation-summary",
            {"state_version": 2, "consultant_note": "합성 QA 메모"},
            write_headers,
        ),
        (
            "complete_consultation",
            "POST",
            f"/api/v1/inquiries/{inquiry_id}/complete-consultation",
            {"state_version": 2, "resolution_code": "GUIDANCE_ONLY"},
            write_headers,
        ),
        (
            "request_visit_review",
            "POST",
            f"/api/v1/inquiries/{inquiry_id}/visit-review",
            {"state_version": 2},
            write_headers,
        ),
        (
            "create_visit",
            "POST",
            f"/api/v1/inquiries/{inquiry_id}/visits",
            {"state_version": 2, "preferred_date": "2026-08-17"},
            write_headers,
        ),
        (
            "update_visit_schedule",
            "PATCH",
            f"/api/v1/visits/{fake_visit_id}/schedule",
            {"state_version": 1, "preferred_date": "2026-08-17"},
            write_headers,
        ),
    )

    results = []
    for name, method, path, body, request_headers in requests:
        response = client.request(
            method,
            path,
            json=body,
            headers=request_headers,
        )
        try:
            response_body = response.json()
        except ValueError:
            response_body = {}
        error = (
            response_body.get("error")
            if isinstance(response_body, dict)
            else None
        )
        results.append(
            {
                "name": name,
                "method": method,
                "path_template": path.replace(inquiry_id, "{inquiry_id}")
                .replace(fake_visit_id, "{visit_id}"),
                "status_code": response.status_code,
                "error_code": (
                    error.get("code") if isinstance(error, dict) else None
                ),
                "success_response": 200 <= response.status_code < 300,
            }
        )
    return results


def run(base_url: str) -> dict[str, Any]:
    with httpx.Client(
        base_url=base_url,
        timeout=10.0,
        trust_env=False,
    ) as client:
        customer_token = login(client, CUSTOMER_CODE)
        consultant_token = login(client, CONSULTANT_CODE)
        customer_headers = authorization(customer_token)

        subscriptions = require_status(
            client.get(
                "/api/v1/me/subscriptions",
                headers=customer_headers,
            ),
            200,
            "subscription_list",
        )
        subscription_data = subscriptions.get("data")
        require(
            isinstance(subscription_data, dict),
            "subscription_list: data_missing",
        )
        items = subscription_data.get("items")
        require(isinstance(items, list), "subscription_list: items_missing")
        demo_items = [
            item
            for item in items
            if isinstance(item, dict)
            and isinstance(item.get("product"), dict)
            and item["product"].get("model_code") == "WPUJAC104DWH"
        ]
        require(
            len(demo_items) == 1,
            "subscription_list: seeded_demo_subscription_not_unique",
        )
        subscription_id = demo_items[0].get("subscription_id")
        require(
            isinstance(subscription_id, str),
            "subscription_list: subscription_id_missing",
        )

        suffix = uuid.uuid4().hex
        create_key = f"qa-create-{suffix}"
        correlation_id = str(uuid.uuid4())
        create_body = {
            "subscription_id": subscription_id,
            "channel_code": "WEB",
            "raw_text": "Synthetic QA: water flow is lower than usual.",
            "representative_symptom_code": "LOW_FLOW",
        }
        create_headers = {
            **customer_headers,
            "Idempotency-Key": create_key,
            "X-Correlation-ID": correlation_id,
        }
        created_response = client.post(
            "/api/v1/inquiries",
            json=create_body,
            headers=create_headers,
        )
        created = require_status(created_response, 201, "create_inquiry")
        created_data = created.get("data")
        require(isinstance(created_data, dict), "create_inquiry: data_missing")
        inquiry_id = created_data.get("inquiry_id")
        require(isinstance(inquiry_id, str), "create_inquiry: id_missing")
        require(
            created_response.headers.get("X-Correlation-ID")
            == correlation_id,
            "create_inquiry: correlation_header_mismatch",
        )
        require(
            created_data.get("state_version") == 1,
            "create_inquiry: state_version_mismatch",
        )

        replay = require_status(
            client.post(
                "/api/v1/inquiries",
                json=create_body,
                headers=create_headers,
            ),
            201,
            "create_replay",
        )
        replay_data = replay.get("data")
        require(isinstance(replay_data, dict), "create_replay: data_missing")
        require(
            replay_data.get("inquiry_id") == inquiry_id
            and replay_data.get("idempotent_replay") is True,
            "create_replay: duplicate_side_effect_risk",
        )

        require_error(
            client.post(
                "/api/v1/inquiries",
                json={**create_body, "raw_text": "Synthetic changed input."},
                headers=create_headers,
            ),
            expected_status=409,
            expected_code="DUPLICATE-EVENT-01",
            step="create_key_reuse",
        )
        require_error(
            client.post(
                "/api/v1/inquiries",
                json={"channel_code": "WEB", "raw_text": "Synthetic QA"},
                headers={
                    **customer_headers,
                    "Idempotency-Key": f"qa-invalid-{suffix}",
                },
            ),
            expected_status=422,
            expected_code="VALIDATION_ERROR",
            step="invalid_input",
        )
        require_error(
            client.post(
                "/api/v1/inquiries",
                json=create_body,
                headers={
                    **authorization(consultant_token),
                    "Idempotency-Key": f"qa-forbidden-{suffix}",
                },
            ),
            expected_status=403,
            expected_code="FORBIDDEN",
            step="consultant_cannot_create_customer_inquiry",
        )

        require_error(
            client.post(
                f"/api/v1/inquiries/{inquiry_id}/submit",
                json={"state_version": 2},
                headers={
                    **customer_headers,
                    "Idempotency-Key": f"qa-stale-{suffix}",
                },
            ),
            expected_status=409,
            expected_code="STATE-CONFLICT-01",
            step="stale_state_version",
        )
        submit_key = f"qa-submit-{suffix}"
        submitted = require_status(
            client.post(
                f"/api/v1/inquiries/{inquiry_id}/submit",
                json={"state_version": 1},
                headers={
                    **customer_headers,
                    "Idempotency-Key": submit_key,
                },
            ),
            200,
            "submit_symptom",
        )
        submitted_data = submitted.get("data")
        require(
            isinstance(submitted_data, dict)
            and submitted_data.get("state_version") == 2,
            "submit_symptom: state_version_mismatch",
        )
        submitted_replay = require_status(
            client.post(
                f"/api/v1/inquiries/{inquiry_id}/submit",
                json={"state_version": 1},
                headers={
                    **customer_headers,
                    "Idempotency-Key": submit_key,
                },
            ),
            200,
            "submit_replay",
        )
        submitted_replay_data = submitted_replay.get("data")
        require(
            isinstance(submitted_replay_data, dict)
            and submitted_replay_data.get("idempotent_replay") is True,
            "submit_replay: duplicate_side_effect_risk",
        )

        probes = route_probe(
            client,
            token=consultant_token,
            inquiry_id=inquiry_id,
        )

    successful_routes = [
        item["name"] for item in probes if item["success_response"]
    ]
    return {
        "status": (
            "PASSED"
            if len(successful_routes) == len(probes)
            else "PARTIAL_WITH_RUNTIME_BLOCKERS"
        ),
        "environment": {
            "base_url": base_url,
            "synthetic_accounts_only": True,
            "tokens_redacted": True,
        },
        "verified": {
            "subscription_list": True,
            "inquiry_create_persisted": True,
            "idempotent_replay": True,
            "idempotency_key_reuse_conflict": True,
            "input_validation": True,
            "role_permission": True,
            "state_version_conflict": True,
            "symptom_submit_persisted": True,
        },
        "trace": {
            "correlation_id": correlation_id,
            "idempotency_key": create_key,
            "inquiry_id": inquiry_id,
        },
        "route_probes": probes,
        "successful_service_routes": successful_routes,
        "not_testable": {
            "ai_error": "No live Backend-AI service route in this slice.",
            "evidence_projection": (
                "Evidence endpoint contract and runtime route are absent."
            ),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        result = run(args.base_url.rstrip("/"))
    except (SmokeFailure, httpx.HTTPError) as exc:
        result = {
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "tokens_redacted": True,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
