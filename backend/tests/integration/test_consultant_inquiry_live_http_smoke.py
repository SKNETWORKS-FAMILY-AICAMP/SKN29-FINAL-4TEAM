"""Actual-socket smoke for the shared consultant inquiry read scenario."""

from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import pytest
from django.core.management import call_command

from apps.inquiries.management.commands.seed_demo_consultant_inquiry import (
    DEMO_CONSULTANT_USERNAME,
    DEMO_INQUIRY_PUBLIC_ID,
)


pytestmark = pytest.mark.django_db(transaction=True)
LIST_CORRELATION_ID = "20260810-0000-4000-8000-000000000101"
DETAIL_CORRELATION_ID = "20260810-0000-4000-8000-000000000102"
MISSING_CORRELATION_ID = "20260810-0000-4000-8000-000000000404"
QUERY_CORRELATION_ID = "20260810-0000-4000-8000-000000000422"


def request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], dict]:
    request_headers = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = Request(
        f"{base_url}{path}",
        data=data,
        headers=request_headers,
        method=method,
    )
    try:
        response = urlopen(request, timeout=5)
    except HTTPError as exc:
        status = exc.code
        response_headers = dict(exc.headers.items())
        raw = exc.read()
    else:
        with response:
            status = response.status
            response_headers = dict(response.headers.items())
            raw = response.read()
    return status, response_headers, json.loads(raw.decode("utf-8"))


def assert_correlation(
    headers: dict[str, str],
    payload: dict,
    *,
    expected: str | None = None,
) -> None:
    correlation_id = headers["X-Correlation-ID"]
    UUID(correlation_id)
    assert payload["metadata"]["correlation_id"] == correlation_id
    if expected is not None:
        assert correlation_id == expected


def test_consultant_inquiry_seed_passes_actual_http_smoke(
    live_server,
    settings,
):
    settings.DEMO_LOGIN_ENABLED = True
    settings.DEMO_LOGIN_CODES = frozenset(
        {"DEMO-CUSTOMER-001", DEMO_CONSULTANT_USERNAME}
    )
    call_command("seed_demo_accounts", verbosity=0)
    call_command("seed_demo_consultant_inquiry", verbosity=0)

    login_status, login_headers, login_payload = request_json(
        live_server.url,
        "/api/v1/auth/demo-login",
        method="POST",
        payload={"demo_user_code": DEMO_CONSULTANT_USERNAME},
        headers={"X-Correlation-ID": str(uuid4())},
    )
    assert login_status == 200
    assert_correlation(login_headers, login_payload)
    auth = {
        "Authorization": f"Bearer {login_payload['data']['access_token']}"
    }

    list_status, list_headers, list_payload = request_json(
        live_server.url,
        "/api/v1/inquiries",
        headers={**auth, "X-Correlation-ID": LIST_CORRELATION_ID},
    )
    assert list_status == 200
    assert_correlation(
        list_headers,
        list_payload,
        expected=LIST_CORRELATION_ID,
    )
    assert list_payload["data"]["page_info"]["total"] == 1
    assert list_payload["data"]["items"][0]["inquiry_id"] == str(
        DEMO_INQUIRY_PUBLIC_ID
    )

    detail_status, detail_headers, detail_payload = request_json(
        live_server.url,
        f"/api/v1/inquiries/{DEMO_INQUIRY_PUBLIC_ID}",
        headers={**auth, "X-Correlation-ID": DETAIL_CORRELATION_ID},
    )
    assert detail_status == 200
    assert_correlation(
        detail_headers,
        detail_payload,
        expected=DETAIL_CORRELATION_ID,
    )
    customer = detail_payload["data"]["customer"]
    assert customer["phone"] == "010-****-0000"
    assert customer["phone_masked"] == "010-****-0000"

    missing_status, missing_headers, missing_payload = request_json(
        live_server.url,
        f"/api/v1/inquiries/{uuid4()}",
        headers={**auth, "X-Correlation-ID": MISSING_CORRELATION_ID},
    )
    assert missing_status == 404
    assert missing_payload["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert_correlation(
        missing_headers,
        missing_payload,
        expected=MISSING_CORRELATION_ID,
    )

    query_status, query_headers, query_payload = request_json(
        live_server.url,
        "/api/v1/inquiries?unknown=1",
        headers={**auth, "X-Correlation-ID": QUERY_CORRELATION_ID},
    )
    assert query_status == 422
    assert query_payload["error"]["code"] == "VALIDATION_ERROR"
    assert_correlation(
        query_headers,
        query_payload,
        expected=QUERY_CORRELATION_ID,
    )
