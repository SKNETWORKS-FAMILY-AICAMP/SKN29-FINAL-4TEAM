"""Actual stdio MCP subprocess -> HTTP Context -> Pipeline fail-closed smoke."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from uuid import UUID, uuid4

from ai.app.orchestration.pipeline_router import PipelineRouter


def test_mcp_transport_calls_http_context_then_fails_closed_without_vector(
    monkeypatch,
):
    inquiry_id = UUID("018f2f9b-7c30-7981-b541-1a987c88b401")
    correlation_id = UUID("018f2f9b-7c30-7981-b541-1a987c88b402")
    subscription_id = uuid4()
    product_model_id = uuid4()
    token = "test-mcp-context-token"
    observed = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            observed.append(
                {
                    "path": self.path,
                    "token": self.headers.get("X-AI-Handoff-Token"),
                    "correlation_id": self.headers.get("X-Correlation-ID"),
                }
            )
            payload = {
                "success": True,
                "data": {
                    "inquiry_id": str(inquiry_id),
                    "inquiry_code": "INQ-MCP-STDIO",
                    "status_code": "QUESTIONNAIRE_IN_PROGRESS",
                    "state_version": 2,
                    "correlation_id": str(correlation_id),
                    "product_context": {
                        "subscription_id": str(subscription_id),
                        "subscription_status_code": "ACTIVE",
                        "management_type_code": "SELF_MANAGED",
                        "product_model_id": str(product_model_id),
                        "model_code": "WPUJAC104DWH",
                        "model_name": "JAC104",
                        "product_family": "DIRECT_WATER_PURIFIER",
                        "generation_code": "D",
                        "manufacturer": "SK매직",
                        "features": {
                            "model_family": "WPU-JAC104",
                            "water_modes": ["COLD"],
                            "supported_functions": ["COLD_WATER"],
                        },
                    },
                    "inquiry_context": {
                        "customer_query": "냉수가 미지근합니다.",
                        "symptom_type": "COLD_WATER_TEMPERATURE",
                        "selected_symptoms": ["COLD_WATER_TEMPERATURE"],
                        "previous_answers": [],
                    },
                },
                "error": None,
                "metadata": {"correlation_id": str(correlation_id)},
            }
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Correlation-ID", str(correlation_id))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("AI_RETRIEVAL_TRANSPORT", "mcp")
        monkeypatch.setenv(
            "AI_BACKEND_BASE_URL",
            f"http://127.0.0.1:{server.server_port}",
        )
        monkeypatch.setenv("AI_HANDOFF_INTERNAL_TOKEN", token)
        monkeypatch.setenv("AI_BACKEND_CONTEXT_TIMEOUT_SECONDS", "2")
        monkeypatch.setenv("AI_MCP_CONTEXT_TIMEOUT_SECONDS", "6")
        monkeypatch.delenv("AI_VECTOR_DSN", raising=False)

        result = PipelineRouter(search_service=None).run_pipeline(
            inquiry_id=inquiry_id,
            correlation_id=correlation_id,
            ai_request_id="mcp-stdio-pipeline",
            state_version=2,
            raw_symptom="냉수가 미지근합니다.",
            model_code="WPUJAC104DWH",
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    harness = result.reliability_runtime.harness_runtime.harness
    assert len(observed) == 2
    assert all(item["path"].endswith(f"/{inquiry_id}/context") for item in observed)
    assert all(item["token"] == token for item in observed)
    assert all(
        item["correlation_id"] == str(correlation_id)
        for item in observed
    )
    assert result.context.model_code == "WPUJAC104DWH"
    assert result.context.evidence_references == []
    assert harness.error_code.value == "MCP_TOOL_FAILURE"
    assert result.reliability_runtime.harness_runtime.handoff is not None
