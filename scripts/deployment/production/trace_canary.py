"""Emit and query a synthetic Tempo trace without logging payloads or secrets."""

from __future__ import annotations

import re
import sys
import time
import urllib.error
import urllib.request


TRACE_ID = re.compile(r"^[0-9a-f]{32}$")
TEMPO_QUERY_ORIGIN = "http://trace-store:3200"


def emit() -> int:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    provider = TracerProvider(
        resource=Resource.create({"service.name": "waterbridge-deployment-canary"})
    )
    provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(timeout=10)))
    tracer = provider.get_tracer("waterbridge.deployment")
    with tracer.start_as_current_span("deployment-canary") as span:
        trace_id = f"{span.get_span_context().trace_id:032x}"
        span.set_attribute("waterbridge.synthetic", True)
    provider.shutdown()
    if TRACE_ID.fullmatch(trace_id) is None:
        return 1
    print(f"TRACE_CANARY_EXPORTED trace_id={trace_id}")
    return 0


def query(trace_id: str) -> int:
    if TRACE_ID.fullmatch(trace_id) is None:
        print("TRACE_CANARY_QUERY_FAILED", file=sys.stderr)
        return 1
    request = urllib.request.Request(
        f"{TEMPO_QUERY_ORIGIN}/api/v2/traces/{trace_id}",
        headers={"Accept": "application/json"},
    )
    for _ in range(12):
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                body = response.read(1)
                if response.status == 200 and body:
                    print("TRACE_CANARY_QUERY_PASS")
                    return 0
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            pass
        time.sleep(5)
    print("TRACE_CANARY_QUERY_FAILED", file=sys.stderr)
    return 1


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "emit":
        return emit()
    if len(sys.argv) == 3 and sys.argv[1] == "query":
        return query(sys.argv[2])
    print("usage: trace_canary.py emit | query <trace_id>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
