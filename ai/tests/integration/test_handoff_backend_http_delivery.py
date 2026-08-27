"""Real HTTP socket test for AI -> Backend handoff delivery."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import UUID

from ai.app.integrations.backend.handoff_client import (
    BACKEND_BASE_URL_ENV,
    HANDOFF_ENABLED_ENV,
    HANDOFF_TOKEN_ENV,
    HandoffPublishStatus,
    publish_consultation_handoff,
)
from ai.app.orchestration.handoff import ConsultationHandoffResult


TOKEN = "socket-test-handoff-secret"


class _Receiver(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.received.append(
            {
                "path": self.path,
                "headers": dict(self.headers.items()),
                "body": body,
            }
        )
        is_first_attempt = len(self.server.received) == 1
        status = 409 if is_first_attempt else 201
        response_body = (
            json.dumps(
                {"error": {"code": "AI_HANDOFF_NOT_READY"}}
            ).encode("utf-8")
            if is_first_attempt
            else b""
        )
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, format, *args):
        del format, args


def _handoff() -> ConsultationHandoffResult:
    return ConsultationHandoffResult(
        inquiry_id=UUID("018f2f9b-7c30-7981-b541-1a987c88b201"),
        correlation_id=UUID("018f2f9b-7c30-7981-b541-1a987c88e001"),
        ai_request_id="ai-handoff-socket-001",
        state_version=4,
        routing_reason="HARNESS_ESCALATE",
        model_code="WPUJAC104DWH",
        product_family="DIRECT_WATER_PURIFIER",
        customer_symptom_summary="출수량 저하 상담 확인 필요",
        questionnaire_answers=[],
        self_help_actions=[],
        evidence=[],
        safety_level="unknown",
        safety_requires_consultation=False,
        safety_notes=[],
        escalation_reason="NO_EVIDENCE",
        consultant_priority_checks=["출수 환경 확인"],
        source_chunk_ids=[],
    )


def test_real_socket_retries_409_then_delivers_201(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Receiver)
    server.received = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    port = server.server_address[1]
    monkeypatch.setenv(HANDOFF_ENABLED_ENV, "true")
    monkeypatch.setenv(
        BACKEND_BASE_URL_ENV,
        f"http://127.0.0.1:{port}",
    )
    monkeypatch.setenv(HANDOFF_TOKEN_ENV, TOKEN)

    try:
        result = publish_consultation_handoff(
            _handoff(),
            sleep_fn=lambda _seconds: None,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == HandoffPublishStatus.DELIVERED
    assert result.attempts == 2
    assert result.status_code == 201
    assert len(server.received) == 2

    second = server.received[1]
    assert second["path"].endswith(
        "/api/v1/internal/ai/inquiries/"
        "018f2f9b-7c30-7981-b541-1a987c88b201/"
        "consultation-handoffs"
    )
    assert second["headers"]["X-AI-Handoff-Token"] == TOKEN
    assert second["headers"]["Idempotency-Key"] == (
        "ai-handoff-socket-001"
    )
    payload = json.loads(second["body"].decode("utf-8"))
    assert payload["schema_version"] == "2.0.0"
    assert payload["state_version"] == 4
    assert payload["routing_reason"] == "HARNESS_ESCALATE"
    assert payload["context_synthesis"] is None
    assert payload["model_code"] == "WPUJAC104DWH"
    assert "system_prompt" not in payload
    assert "raw_output_text" not in payload
