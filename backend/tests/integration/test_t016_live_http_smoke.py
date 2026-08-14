"""Actual-socket smoke for the already implemented T-016 API surface.

This test deliberately uses only existing public routes.  The failure route is
local to this test module so the common 500 envelope can be verified without
adding a production endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import pytest
from django.core.management import call_command
from django.urls import clear_url_caches, path
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from config.urls import urlpatterns as project_urlpatterns


pytestmark = pytest.mark.django_db(transaction=True)
CUSTOMER_CODE = "DEMO-CUSTOMER-001"
CONSULTANT_CODE = "DEMO-CONSULTANT-001"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES_DIR = REPOSITORY_ROOT / "contracts" / "api" / "examples"
ERROR_EXAMPLES = {
    "INVALID_REQUEST": "errors/invalid-request.json",
    "AUTH_REQUIRED": "errors/auth-required.json",
    "FORBIDDEN": "errors/forbidden.json",
    "RESOURCE_NOT_FOUND": "errors/resource-not-found.json",
    "DUPLICATE-EVENT-01": "workflow/idempotency-key-reuse-conflict.json",
    "VALIDATION_ERROR": "subscriptions/query-validation-error.json",
    "INTERNAL_ERROR": "errors/internal-error.json",
}


class RuntimeFailureView(APIView):
    """Test-only failure injection for the common safe 500 response."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        raise RuntimeError("private-database-value-must-not-leak")


urlpatterns = [
    path(
        "api/v1/_test/runtime-failure",
        RuntimeFailureView.as_view(),
        name="t016-runtime-failure",
    ),
    *project_urlpatterns,
]


@dataclass(frozen=True)
class HttpResult:
    status: int
    headers: dict[str, str]
    payload: dict | None
    body: str


def request_http(
    base_url: str,
    path_value: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    raw_body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> HttpResult:
    request_headers = dict(headers or {})
    data = raw_body
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    if data is not None:
        request_headers.setdefault("Content-Type", "application/json")

    request = Request(
        f"{base_url}{path_value}",
        data=data,
        headers=request_headers,
        method=method,
    )
    try:
        response = urlopen(request, timeout=5)
    except HTTPError as exc:
        status = exc.code
        response_headers = dict(exc.headers.items())
        raw_response = exc.read()
    else:
        with response:
            status = response.status
            response_headers = dict(response.headers.items())
            raw_response = response.read()

    body = raw_response.decode("utf-8")
    parsed = json.loads(body) if body else None
    return HttpResult(status, response_headers, parsed, body)


def traced(result: HttpResult, expected_status: int) -> dict | None:
    assert result.status == expected_status, result.body
    correlation_id = result.headers["X-Correlation-ID"]
    UUID(correlation_id)
    if result.payload is not None:
        assert result.payload["metadata"]["correlation_id"] == correlation_id
    return result.payload


def traced_error(
    result: HttpResult,
    expected_status: int,
    expected_code: str,
) -> dict:
    payload = traced(result, expected_status)
    assert set(payload) == {"success", "data", "error", "metadata"}
    assert payload["success"] is False
    assert payload["data"] is None
    assert set(payload["error"]) == {"code", "message", "details"}
    assert payload["error"]["code"] == expected_code

    example = json.loads(
        (EXAMPLES_DIR / ERROR_EXAMPLES[expected_code]).read_text(
            encoding="utf-8"
        )
    )
    assert payload["error"]["code"] == example["error"]["code"]
    assert payload["error"]["message"] == example["error"]["message"]
    return payload


def login(base_url: str, demo_code: str) -> str:
    result = request_http(
        base_url,
        "/api/v1/auth/demo-login",
        method="POST",
        payload={"demo_user_code": demo_code},
        headers={"X-Correlation-ID": str(uuid4())},
    )
    return traced(result, 200)["data"]["access_token"]


def bearer(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def create_inquiry(
    base_url: str,
    access_token: str,
    subscription: CustomerSubscription,
    *,
    key: str,
    raw_text: str,
) -> HttpResult:
    return request_http(
        base_url,
        "/api/v1/inquiries",
        method="POST",
        payload={
            "subscription_id": str(subscription.public_id),
            "channel_code": "WEB",
            "raw_text": raw_text,
            "representative_symptom_code": "LOW_FLOW",
        },
        headers={
            **bearer(access_token),
            "Idempotency-Key": key,
            "X-Correlation-ID": str(uuid4()),
        },
    )


def test_t016_existing_routes_pass_actual_http_and_error_matrix(
    live_server,
    settings,
):
    """Exercise existing routes through a real socket and an isolated test DB."""

    settings.ROOT_URLCONF = __name__
    settings.DEMO_LOGIN_ENABLED = True
    settings.DEMO_LOGIN_CODES = frozenset(
        {CUSTOMER_CODE, CONSULTANT_CODE}
    )
    clear_url_caches()

    call_command("seed_demo_accounts", verbosity=0)
    customer = User.objects.get(username=CUSTOMER_CODE)
    product = ProductModel.objects.create(
        model_code="WPUJAC104DWH",
        model_name="T016 live smoke purifier",
        generation_code="D",
        manufacturer="SK magic",
        is_supported_mvp=True,
        is_active=True,
    )
    subscription = CustomerSubscription.objects.create(
        contract_no="T016-LIVE-SMOKE-001",
        customer=customer.customer_profile,
        product_model=product,
        serial_no="T016-LIVE-SERIAL-001",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 8, 1),
    )

    requested_correlation_id = str(uuid4())
    health = request_http(
        live_server.url,
        "/health",
        headers={"X-Correlation-ID": requested_correlation_id},
    )
    traced(health, 200)
    assert health.headers["X-Correlation-ID"] == requested_correlation_id

    customer_access = login(live_server.url, CUSTOMER_CODE)
    consultant_access = login(live_server.url, CONSULTANT_CODE)

    me = request_http(
        live_server.url,
        "/api/v1/me",
        headers=bearer(customer_access),
    )
    assert traced(me, 200)["data"]["role_code"] == "CUSTOMER"

    subscription_list = request_http(
        live_server.url,
        "/api/v1/me/subscriptions",
        headers=bearer(customer_access),
    )
    list_data = traced(subscription_list, 200)["data"]
    assert list_data["total"] == 1
    assert list_data["items"][0]["subscription_id"] == str(
        subscription.public_id
    )

    subscription_detail = request_http(
        live_server.url,
        f"/api/v1/me/subscriptions/{subscription.public_id}",
        headers=bearer(customer_access),
    )
    assert traced(subscription_detail, 200)["data"][
        "subscription_id"
    ] == str(subscription.public_id)

    anonymous = request_http(
        live_server.url,
        "/api/v1/me/subscriptions",
    )
    traced_error(anonymous, 401, "AUTH_REQUIRED")

    forbidden = request_http(
        live_server.url,
        "/api/v1/me/subscriptions",
        headers=bearer(consultant_access),
    )
    traced_error(forbidden, 403, "FORBIDDEN")

    missing = request_http(
        live_server.url,
        f"/api/v1/me/subscriptions/{uuid4()}",
        headers=bearer(customer_access),
    )
    traced_error(missing, 404, "RESOURCE_NOT_FOUND")

    malformed_json = request_http(
        live_server.url,
        "/api/v1/auth/demo-login",
        method="POST",
        raw_body=b"{",
    )
    traced_error(malformed_json, 400, "INVALID_REQUEST")

    invalid_query = request_http(
        live_server.url,
        "/api/v1/me/subscriptions?page=0",
        headers=bearer(customer_access),
    )
    traced_error(invalid_query, 422, "VALIDATION_ERROR")

    first = create_inquiry(
        live_server.url,
        customer_access,
        subscription,
        key="t016-live-create-conflict",
        raw_text="The water flow is lower than usual.",
    )
    first_data = traced(first, 201)["data"]

    conflict = create_inquiry(
        live_server.url,
        customer_access,
        subscription,
        key="t016-live-create-conflict",
        raw_text="The water flow stopped completely.",
    )
    traced_error(conflict, 409, "DUPLICATE-EVENT-01")

    # T-016 verifies the common Backend socket and response boundary.  Keep
    # the separately owned Backend-AI live HTTP gate out of this smoke test.
    with patch(
        "apps.inquiries.services.inquiry_ai_service."
        "InquiryAIService.analyze_inquiry"
    ):
        submitted = request_http(
            live_server.url,
            f"/api/v1/inquiries/{first_data['inquiry_id']}/submit",
            method="POST",
            payload={"state_version": 1},
            headers={
                **bearer(customer_access),
                "Idempotency-Key": "t016-live-submit",
            },
        )
    assert traced(submitted, 200)["data"]["state"] == (
        "QUESTIONNAIRE_IN_PROGRESS"
    )

    cancellable = create_inquiry(
        live_server.url,
        customer_access,
        subscription,
        key="t016-live-create-cancel",
        raw_text="Cancel this separate smoke inquiry.",
    )
    cancellable_data = traced(cancellable, 201)["data"]
    cancelled = request_http(
        live_server.url,
        f"/api/v1/inquiries/{cancellable_data['inquiry_id']}/cancel",
        method="POST",
        payload={
            "state_version": 1,
            "reason_code": "CUSTOMER_REQUEST",
            "reason_detail": "Smoke test cleanup",
        },
        headers={
            **bearer(customer_access),
            "Idempotency-Key": "t016-live-cancel",
        },
    )
    assert traced(cancelled, 200)["data"]["state"] == "CANCELLED"

    failure = request_http(
        live_server.url,
        "/api/v1/_test/runtime-failure",
    )
    traced_error(failure, 500, "INTERNAL_ERROR")
    assert "private-database-value-must-not-leak" not in failure.body
