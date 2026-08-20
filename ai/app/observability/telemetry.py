"""OpenTelemetry runtime bootstrap for the WaterBridge AI service."""

from __future__ import annotations

import os
from threading import Lock

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


ENABLED_ENV = "AI_OTEL_ENABLED"
TRACES_ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"
SERVICE_NAME_ENV = "OTEL_SERVICE_NAME"

_DEFAULT_SERVICE_NAME = "waterbridge-ai"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})

_lock = Lock()
_provider: TracerProvider | None = None
_shutdown = False


def telemetry_enabled() -> bool:
    return os.getenv(ENABLED_ENV, "false").strip().lower() in _TRUE_VALUES


def configure_telemetry() -> TracerProvider | None:
    global _provider

    if not telemetry_enabled():
        return None

    with _lock:
        if _provider is not None:
            return _provider
        if _shutdown:
            raise RuntimeError(
                "OpenTelemetry provider was already shut down in this process."
            )

        endpoint = os.getenv(TRACES_ENDPOINT_ENV, "").strip()
        if not endpoint:
            raise RuntimeError(
                f"{TRACES_ENDPOINT_ENV} is required when {ENABLED_ENV}=true."
            )

        service_name = (
            os.getenv(SERVICE_NAME_ENV, _DEFAULT_SERVICE_NAME).strip()
            or _DEFAULT_SERVICE_NAME
        )
        environment = os.getenv("AI_ENV", "development").strip() or "development"

        resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": "1.0.0",
                "deployment.environment.name": environment,
            }
        )
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _provider = provider
        return provider


def force_flush_telemetry(timeout_millis: int = 5000) -> bool:
    provider = _provider
    if provider is None:
        return True
    return provider.force_flush(timeout_millis=timeout_millis)


def shutdown_telemetry() -> None:
    global _shutdown

    with _lock:
        provider = _provider
        if provider is None or _shutdown:
            return
        provider.shutdown()
        _shutdown = True
