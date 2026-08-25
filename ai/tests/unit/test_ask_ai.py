"""수동 AI 질문 클라이언트가 공개 Analyze 계약을 지키는지 검증한다."""

from __future__ import annotations

import json
from io import BytesIO
from urllib.error import HTTPError
from uuid import UUID

from ai.scripts import ask_ai


class _FakeResponse:
    def __init__(self, body: dict, *, status: int = 200) -> None:
        self.status = status
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self._body


def test_ask_ai_sends_valid_trace_ids_and_printable_question(monkeypatch):
    captured = {}

    def fake_urlopen(request, *, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _FakeResponse({"status": "SUCCEEDED"})

    monkeypatch.setattr(ask_ai, "urlopen", fake_urlopen)

    status, body = ask_ai.ask_ai(
        "  냉수 출수량이 줄었습니다.  ",
        mode="mock",
        selected_symptoms=["출수량 저하"],
    )

    request = captured["request"]
    payload = json.loads(request.data.decode("utf-8"))
    correlation_id = request.get_header("X-correlation-id")
    assert status == 200
    assert body == {"status": "SUCCEEDED"}
    assert request.full_url.endswith("/api/v1/ai/analyze?mode=mock")
    assert captured["timeout"] == 35.0
    assert payload["raw_symptom"] == "냉수 출수량이 줄었습니다."
    assert payload["selected_symptoms"] == ["출수량 저하"]
    assert payload["correlation_id"] == correlation_id
    UUID(payload["inquiry_id"])
    UUID(payload["correlation_id"])


def test_ask_ai_returns_full_error_body(monkeypatch):
    expected = {
        "success": False,
        "error": {
            "code": "AI-FAILED-01",
            "failure_stage": "RETRIEVING",
        },
    }

    def fake_urlopen(request, *, timeout):
        raise HTTPError(
            request.full_url,
            503,
            "Service Unavailable",
            {},
            BytesIO(json.dumps(expected).encode("utf-8")),
        )

    monkeypatch.setattr(ask_ai, "urlopen", fake_urlopen)

    status, body = ask_ai.ask_ai("냉수 출수량이 줄었습니다.")

    assert status == 503
    assert body == expected


def test_build_payload_rejects_blank_question():
    try:
        ask_ai.build_payload("   ")
    except ask_ai.AiClientError as exc:
        assert "문장을 입력" in str(exc)
    else:
        raise AssertionError("빈 질문을 거부해야 합니다.")
