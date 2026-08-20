"""FastAPI bootstrap -> real OTLP/HTTP protobuf export integration test."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "ai" / "scripts" / "verify_runtime_otel_otlp.py"

_REQUIRED_SPANS = {
    "waterbridge.harness.runtime",
    "waterbridge.harness.verify",
    "waterbridge.harness.resume_review",
    "waterbridge.hitl.start",
    "waterbridge.hitl.resume",
    "waterbridge.handoff.create",
}


class _Receiver(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        self.server.received.append((self.path, dict(self.headers.items()), body))
        self.send_response(200)
        self.send_header("Content-Type", "application/x-protobuf")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format, *args):
        del format, args


def _value_to_python(value):
    field = value.WhichOneof("value")
    if field is None:
        return None
    if field == "array_value":
        return [_value_to_python(item) for item in value.array_value.values]
    if field == "kvlist_value":
        return {
            item.key: _value_to_python(item.value)
            for item in value.kvlist_value.values
        }
    return getattr(value, field)


def _decode_requests(received):
    spans = []
    resource_attributes = []

    for path, headers, body in received:
        assert path == "/v1/traces"
        assert "application/x-protobuf" in headers.get("Content-Type", "")
        assert body

        request = ExportTraceServiceRequest()
        request.ParseFromString(body)
        for resource_spans in request.resource_spans:
            resource_attributes.append(
                {
                    item.key: _value_to_python(item.value)
                    for item in resource_spans.resource.attributes
                }
            )
            for scope_spans in resource_spans.scope_spans:
                spans.extend(scope_spans.spans)

    return spans, resource_attributes


def test_fastapi_runtime_exports_reliability_spans_via_otlp_http():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Receiver)
    server.received = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    port = server.server_address[1]
    env = os.environ.copy()
    env.pop("AI_VECTOR_DSN", None)
    env["AI_OTEL_ENABLED"] = "true"
    env["AI_ENV"] = "integration-test"
    env["OTEL_SERVICE_NAME"] = "waterbridge-ai"
    env["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = (
        f"http://127.0.0.1:{port}/v1/traces"
    )

    try:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    combined = completed.stdout + "\n" + completed.stderr
    assert completed.returncode == 0, combined
    assert "OTLP_RUNTIME_SENT" in completed.stdout
    assert server.received, "No OTLP/HTTP export request was received."

    spans, resources = _decode_requests(server.received)
    names = {span.name for span in spans}
    assert _REQUIRED_SPANS.issubset(names), (
        f"missing={sorted(_REQUIRED_SPANS - names)} got={sorted(names)}"
    )

    assert resources
    assert all(
        resource.get("service.name") == "waterbridge-ai"
        for resource in resources
    )
    assert all(
        resource.get("deployment.environment.name") == "integration-test"
        for resource in resources
    )

    exported_attributes = repr(
        [
            {
                item.key: _value_to_python(item.value)
                for item in span.attributes
            }
            for span in spans
        ]
    )
    for forbidden in (
        "OTLP_PRIVATE_SENTINEL",
        "010-9876-5432",
        "otlp-private@example.com",
        "OTLP_PRIVATE_EVIDENCE_BODY",
        "raw_symptom",
        "system_prompt",
    ):
        assert forbidden not in exported_attributes
