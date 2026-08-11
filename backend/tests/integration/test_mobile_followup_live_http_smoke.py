"""Actual-socket smoke for the official Mobile customer inquiry fixture."""

from __future__ import annotations

from contextlib import contextmanager
from io import StringIO
import json
import logging
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import pytest
from django.core.management import call_command

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.management.commands.seed_demo_mobile_followup import (
    DEMO_CHOICE_OPTIONS,
    DEMO_CHOICE_QUESTION_PUBLIC_ID,
    DEMO_CUSTOMER_USERNAME,
    DEMO_FREE_TEXT_QUESTION_PUBLIC_ID,
    DEMO_INQUIRY_PUBLIC_ID,
    DEMO_INITIAL_STATE_VERSION,
    DEMO_SUBSCRIPTION_PUBLIC_ID,
)
from common.logging.filters import RequestContextFilter
from common.logging.formatter import JsonFormatter


pytestmark = pytest.mark.django_db(transaction=True)
OTHER_CUSTOMER_USERNAME = "DEMO-MOBILE-FOLLOWUP-OTHER-001"
CORRELATIONS = {
    "login": "20260811-0000-4000-8000-000000000201",
    "subscription": "20260811-0000-4000-8000-000000000202",
    "snapshot": "20260811-0000-4000-8000-000000000203",
    "questions": "20260811-0000-4000-8000-000000000204",
    "answer": "20260811-0000-4000-8000-000000000205",
    "replay": "20260811-0000-4000-8000-000000000206",
    "invalid": "20260811-0000-4000-8000-000000000207",
    "stale": "20260811-0000-4000-8000-000000000208",
    "choice": "20260811-0000-4000-8000-000000000209",
    "final_questions": "20260811-0000-4000-8000-000000000210",
    "final_snapshot": "20260811-0000-4000-8000-000000000211",
    "other_login": "20260811-0000-4000-8000-000000000212",
    "other_owner": "20260811-0000-4000-8000-000000000213",
    "missing": "20260811-0000-4000-8000-000000000214",
    "query": "20260811-0000-4000-8000-000000000215",
}


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
    expected: str,
) -> None:
    UUID(expected)
    assert headers["X-Correlation-ID"] == expected
    assert payload["metadata"]["correlation_id"] == expected


def api_request(
    base_url: str,
    path: str,
    *,
    correlation: str,
    auth: dict[str, str] | None = None,
    method: str = "GET",
    payload: dict | None = None,
    idempotency_key: str | None = None,
) -> tuple[int, dict]:
    headers = {
        **(auth or {}),
        "X-Correlation-ID": correlation,
    }
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    status, response_headers, response_payload = request_json(
        base_url,
        path,
        method=method,
        payload=payload,
        headers=headers,
    )
    assert_correlation(response_headers, response_payload, correlation)
    return status, response_payload


@contextmanager
def captured_request_logs():
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("watercare.request")
    original = (list(logger.handlers), logger.level, logger.propagate)
    try:
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False
        yield stream
    finally:
        logger.handlers, logger.level, logger.propagate = original


def create_other_customer() -> None:
    user = User.objects.create_user(
        username=OTHER_CUSTOMER_USERNAME,
        full_name="Synthetic Mobile other customer",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    CustomerProfile.objects.create(
        user=user,
        customer_no=OTHER_CUSTOMER_USERNAME,
        customer_name="합성 Mobile 타 고객",
        is_synthetic=True,
    )


def login(base_url: str, username: str, correlation: str) -> dict[str, str]:
    status, payload = api_request(
        base_url,
        "/api/v1/auth/demo-login",
        method="POST",
        payload={"demo_user_code": username},
        correlation=correlation,
    )
    assert status == 200
    return {"Authorization": f"Bearer {payload['data']['access_token']}"}


def test_mobile_followup_fixture_passes_actual_http_smoke(
    live_server,
    settings,
):
    settings.DEMO_LOGIN_ENABLED = True
    settings.DEMO_LOGIN_CODES = frozenset(
        {DEMO_CUSTOMER_USERNAME, OTHER_CUSTOMER_USERNAME}
    )
    call_command("seed_demo_accounts", verbosity=0)
    call_command("seed_demo_mobile_followup", verbosity=0)
    create_other_customer()

    answer_text = "오늘 아침부터 증상이 계속됩니다."
    expected_status = {
        CORRELATIONS["login"]: 200,
        CORRELATIONS["subscription"]: 200,
        CORRELATIONS["snapshot"]: 200,
        CORRELATIONS["questions"]: 200,
        CORRELATIONS["answer"]: 200,
        CORRELATIONS["replay"]: 200,
        CORRELATIONS["invalid"]: 422,
        CORRELATIONS["stale"]: 409,
        CORRELATIONS["choice"]: 200,
        CORRELATIONS["final_questions"]: 200,
        CORRELATIONS["final_snapshot"]: 200,
        CORRELATIONS["other_login"]: 200,
        CORRELATIONS["other_owner"]: 404,
        CORRELATIONS["missing"]: 404,
        CORRELATIONS["query"]: 422,
    }

    with captured_request_logs() as stream:
        auth = login(
            live_server.url,
            DEMO_CUSTOMER_USERNAME,
            CORRELATIONS["login"],
        )
        subscription_status, subscription_payload = api_request(
            live_server.url,
            "/api/v1/me/subscriptions",
            auth=auth,
            correlation=CORRELATIONS["subscription"],
        )
        assert subscription_status == 200
        assert subscription_payload["data"]["items"][0][
            "subscription_id"
        ] == str(DEMO_SUBSCRIPTION_PUBLIC_ID)

        snapshot_status, snapshot_payload = api_request(
            live_server.url,
            f"/api/v1/me/inquiries/{DEMO_INQUIRY_PUBLIC_ID}",
            auth=auth,
            correlation=CORRELATIONS["snapshot"],
        )
        assert snapshot_status == 200
        assert snapshot_payload["data"]["state_version"] == (
            DEMO_INITIAL_STATE_VERSION
        )

        questions_status, questions_payload = api_request(
            live_server.url,
            f"/api/v1/me/inquiries/{DEMO_INQUIRY_PUBLIC_ID}/questions",
            auth=auth,
            correlation=CORRELATIONS["questions"],
        )
        assert questions_status == 200
        assert [
            item["question_id"] for item in questions_payload["data"]["questions"]
        ] == [
            str(DEMO_FREE_TEXT_QUESTION_PUBLIC_ID),
            str(DEMO_CHOICE_QUESTION_PUBLIC_ID),
        ]

        free_answer = {
            "state_version": DEMO_INITIAL_STATE_VERSION,
            "answers": [
                {
                    "question_id": str(DEMO_FREE_TEXT_QUESTION_PUBLIC_ID),
                    "answer_text": answer_text,
                }
            ],
        }
        with patch(
            "apps.inquiries.services.inquiry_ai_service."
            "InquiryAIService.analyze_inquiry"
        ) as analyze:
            answer_status, answer_payload = api_request(
                live_server.url,
                f"/api/v1/inquiries/{DEMO_INQUIRY_PUBLIC_ID}/answers",
                method="POST",
                payload=free_answer,
                auth=auth,
                idempotency_key="demo-mobile-followup-free-v1",
                correlation=CORRELATIONS["answer"],
            )
            assert answer_status == 200
            assert answer_payload["data"]["state_version"] == 3
            assert answer_payload["data"]["idempotent_replay"] is False

            replay_status, replay_payload = api_request(
                live_server.url,
                f"/api/v1/inquiries/{DEMO_INQUIRY_PUBLIC_ID}/answers",
                method="POST",
                payload=free_answer,
                auth=auth,
                idempotency_key="demo-mobile-followup-free-v1",
                correlation=CORRELATIONS["replay"],
            )
            assert replay_status == 200
            assert replay_payload["data"]["idempotent_replay"] is True

            invalid_status, invalid_payload = api_request(
                live_server.url,
                f"/api/v1/inquiries/{DEMO_INQUIRY_PUBLIC_ID}/answers",
                method="POST",
                payload={
                    "state_version": 3,
                    "answers": [
                        {
                            "question_id": str(
                                DEMO_CHOICE_QUESTION_PUBLIC_ID
                            ),
                            "answer_payload": {
                                "selected_option": "계약에 없는 선택지"
                            },
                        }
                    ],
                },
                auth=auth,
                idempotency_key="demo-mobile-followup-invalid-v1",
                correlation=CORRELATIONS["invalid"],
            )
            assert invalid_status == 422
            assert invalid_payload["error"]["code"] == (
                "INVALID_FOLLOWUP_ANSWERS"
            )

            choice_answer = {
                "answers": [
                    {
                        "question_id": str(DEMO_CHOICE_QUESTION_PUBLIC_ID),
                        "answer_payload": {
                            "selected_option": DEMO_CHOICE_OPTIONS[0]
                        },
                    }
                ]
            }
            stale_status, stale_payload = api_request(
                live_server.url,
                f"/api/v1/inquiries/{DEMO_INQUIRY_PUBLIC_ID}/answers",
                method="POST",
                payload={
                    "state_version": DEMO_INITIAL_STATE_VERSION,
                    **choice_answer,
                },
                auth=auth,
                idempotency_key="demo-mobile-followup-stale-v1",
                correlation=CORRELATIONS["stale"],
            )
            assert stale_status == 409
            assert stale_payload["error"]["code"] == "STATE-CONFLICT-01"

            choice_status, choice_payload = api_request(
                live_server.url,
                f"/api/v1/inquiries/{DEMO_INQUIRY_PUBLIC_ID}/answers",
                method="POST",
                payload={"state_version": 3, **choice_answer},
                auth=auth,
                idempotency_key="demo-mobile-followup-choice-v1",
                correlation=CORRELATIONS["choice"],
            )
            assert choice_status == 200
            assert choice_payload["data"]["state_version"] == 4
            assert analyze.call_count == 2

        final_questions_status, final_questions_payload = api_request(
            live_server.url,
            f"/api/v1/me/inquiries/{DEMO_INQUIRY_PUBLIC_ID}/questions",
            auth=auth,
            correlation=CORRELATIONS["final_questions"],
        )
        assert final_questions_status == 200
        assert final_questions_payload["data"]["questions"] == []

        final_snapshot_status, final_snapshot_payload = api_request(
            live_server.url,
            f"/api/v1/me/inquiries/{DEMO_INQUIRY_PUBLIC_ID}",
            auth=auth,
            correlation=CORRELATIONS["final_snapshot"],
        )
        assert final_snapshot_status == 200
        assert final_snapshot_payload["data"]["state_version"] == 4

        other_auth = login(
            live_server.url,
            OTHER_CUSTOMER_USERNAME,
            CORRELATIONS["other_login"],
        )
        other_status, other_payload = api_request(
            live_server.url,
            f"/api/v1/me/inquiries/{DEMO_INQUIRY_PUBLIC_ID}",
            auth=other_auth,
            correlation=CORRELATIONS["other_owner"],
        )
        assert other_status == 404
        assert other_payload["error"]["code"] == "RESOURCE_NOT_FOUND"

        missing_status, missing_payload = api_request(
            live_server.url,
            f"/api/v1/me/inquiries/{uuid4()}",
            auth=auth,
            correlation=CORRELATIONS["missing"],
        )
        assert missing_status == 404
        assert missing_payload["error"]["code"] == "RESOURCE_NOT_FOUND"

        query_status, query_payload = api_request(
            live_server.url,
            (
                f"/api/v1/me/inquiries/{DEMO_INQUIRY_PUBLIC_ID}/questions"
                "?unknown=1"
            ),
            auth=auth,
            correlation=CORRELATIONS["query"],
        )
        assert query_status == 422
        assert query_payload["error"]["code"] == "VALIDATION_ERROR"

    logs = [
        json.loads(line)
        for line in stream.getvalue().splitlines()
        if line.strip()
    ]
    for correlation_id, status_code in expected_status.items():
        matched = [
            log
            for log in logs
            if log.get("correlation_id") == correlation_id
        ]
        assert len(matched) == 1
        assert matched[0]["status_code"] == status_code
    rendered_logs = stream.getvalue()
    assert auth["Authorization"].removeprefix("Bearer ") not in rendered_logs
    assert answer_text not in rendered_logs
