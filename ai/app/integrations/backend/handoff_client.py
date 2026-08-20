"""Outbound AI -> Backend consultation handoff delivery.

The public AI analysis response never contains ConsultationHandoffResult.
When enabled, the FastAPI route schedules this client as a post-response
BackgroundTask so Backend can first finalize the matching AIRun.

Transport failures never raise into the customer-facing analysis response.
One bounded retry is allowed for the AIRun-finalization race and transient
network/backend failures.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit

import httpx
from opentelemetry import trace

from ...orchestration.handoff import ConsultationHandoffResult


HANDOFF_ENABLED_ENV = "AI_HANDOFF_BACKEND_ENABLED"
BACKEND_BASE_URL_ENV = "AI_BACKEND_BASE_URL"
HANDOFF_TOKEN_ENV = "AI_HANDOFF_INTERNAL_TOKEN"
HANDOFF_TIMEOUT_ENV = "AI_HANDOFF_TIMEOUT_SECONDS"

MAX_ATTEMPTS = 2
INITIAL_DELAY_SECONDS = 0.20
RETRY_DELAY_SECONDS = 0.75

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_RETRYABLE_STATUS_CODES = frozenset({409, 429, 500, 502, 503, 504})
_PHONE = re.compile(
    r"(?<!\d)(?:01[016789])[- ]?\d{3,4}[- ]?\d{4}(?!\d)"
)
_EMAIL = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)

_TRACER = trace.get_tracer("waterbridge.ai.handoff.delivery", "1.0.0")


class HandoffPublishStatus(str, Enum):
    DISABLED = "DISABLED"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


class HandoffPublishFailureKind(str, Enum):
    CONFIGURATION = "CONFIGURATION"
    PII_DETECTED = "PII_DETECTED"
    TIMEOUT = "TIMEOUT"
    NETWORK = "NETWORK"
    BACKEND_REJECTED = "BACKEND_REJECTED"
    BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
    UNEXPECTED = "UNEXPECTED"


@dataclass(frozen=True, slots=True)
class HandoffPublishResult:
    status: HandoffPublishStatus
    attempts: int
    status_code: int | None = None
    failure_kind: HandoffPublishFailureKind | None = None

    @property
    def delivered(self) -> bool:
        return self.status == HandoffPublishStatus.DELIVERED


@dataclass(frozen=True, slots=True)
class _HandoffBackendConfig:
    base_url: str
    token: str
    timeout_seconds: float


def handoff_delivery_enabled() -> bool:
    """Return whether this process opted in to Backend handoff delivery."""

    return (
        os.getenv(HANDOFF_ENABLED_ENV, "false").strip().lower()
        in _TRUE_VALUES
    )


def _load_config() -> _HandoffBackendConfig | None:
    base_url = os.getenv(BACKEND_BASE_URL_ENV, "").strip().rstrip("/")
    token = os.getenv(HANDOFF_TOKEN_ENV, "").strip()
    raw_timeout = os.getenv(HANDOFF_TIMEOUT_ENV, "2.0").strip()

    try:
        timeout_seconds = float(raw_timeout)
    except ValueError:
        return None

    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or not token
        or not (0.1 <= timeout_seconds <= 10.0)
    ):
        return None

    return _HandoffBackendConfig(
        base_url=base_url,
        token=token,
        timeout_seconds=timeout_seconds,
    )


def _iter_string_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _iter_string_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_string_values(item)


def _contains_direct_contact_pii(payload: dict) -> bool:
    return any(
        _PHONE.search(value) is not None
        or _EMAIL.search(value) is not None
        for value in _iter_string_values(payload)
    )


def _result_for_status(
    *,
    status_code: int,
    attempts: int,
) -> HandoffPublishResult:
    if status_code in {200, 201}:
        return HandoffPublishResult(
            status=HandoffPublishStatus.DELIVERED,
            attempts=attempts,
            status_code=status_code,
        )
    if status_code >= 500:
        failure = HandoffPublishFailureKind.BACKEND_UNAVAILABLE
    else:
        failure = HandoffPublishFailureKind.BACKEND_REJECTED
    return HandoffPublishResult(
        status=HandoffPublishStatus.FAILED,
        attempts=attempts,
        status_code=status_code,
        failure_kind=failure,
    )


def publish_consultation_handoff(
    handoff: ConsultationHandoffResult,
    *,
    http_client: httpx.Client | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> HandoffPublishResult:
    """Deliver one sanitized handoff without affecting the analysis response."""

    with _TRACER.start_as_current_span(
        "waterbridge.handoff.publish"
    ) as span:
        span.set_attribute(
            "waterbridge.inquiry.id",
            str(handoff.inquiry_id),
        )
        span.set_attribute(
            "waterbridge.model.code",
            handoff.model_code,
        )

        result = _publish_untraced(
            handoff,
            http_client=http_client,
            sleep_fn=sleep_fn,
        )

        span.set_attribute(
            "waterbridge.handoff.publish.status",
            result.status.value,
        )
        span.set_attribute(
            "waterbridge.handoff.publish.attempts",
            result.attempts,
        )
        if result.status_code is not None:
            span.set_attribute(
                "waterbridge.handoff.publish.http_status_code",
                result.status_code,
            )
        if result.failure_kind is not None:
            span.set_attribute(
                "waterbridge.handoff.publish.failure_kind",
                result.failure_kind.value,
            )
        return result


def _publish_untraced(
    handoff: ConsultationHandoffResult,
    *,
    http_client: httpx.Client | None,
    sleep_fn: Callable[[float], None],
) -> HandoffPublishResult:
    if not handoff_delivery_enabled():
        return HandoffPublishResult(
            status=HandoffPublishStatus.DISABLED,
            attempts=0,
        )

    config = _load_config()
    if config is None:
        return HandoffPublishResult(
            status=HandoffPublishStatus.FAILED,
            attempts=0,
            failure_kind=HandoffPublishFailureKind.CONFIGURATION,
        )

    payload = handoff.model_dump(mode="json")
    if _contains_direct_contact_pii(payload):
        return HandoffPublishResult(
            status=HandoffPublishStatus.FAILED,
            attempts=0,
            failure_kind=HandoffPublishFailureKind.PII_DETECTED,
        )

    url = (
        f"{config.base_url}/api/v1/internal/ai/inquiries/"
        f"{handoff.inquiry_id}/consultation-handoffs"
    )
    headers = {
        "X-AI-Handoff-Token": config.token,
        "Idempotency-Key": handoff.ai_request_id,
        "X-Correlation-ID": str(handoff.correlation_id),
    }

    owned_client = http_client is None
    client = http_client or httpx.Client(
        timeout=config.timeout_seconds,
        trust_env=False,
    )
    attempts = 0
    last_failure = HandoffPublishFailureKind.UNEXPECTED

    try:
        # BackgroundTasks starts after the analysis response. The small delay
        # lets Backend finalize the matching AIRun before this callback.
        sleep_fn(INITIAL_DELAY_SECONDS)

        for attempt in range(1, MAX_ATTEMPTS + 1):
            attempts = attempt
            try:
                response = client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=config.timeout_seconds,
                )
            except httpx.TimeoutException:
                last_failure = HandoffPublishFailureKind.TIMEOUT
                if attempt < MAX_ATTEMPTS:
                    sleep_fn(RETRY_DELAY_SECONDS)
                    continue
                return HandoffPublishResult(
                    status=HandoffPublishStatus.FAILED,
                    attempts=attempts,
                    failure_kind=last_failure,
                )
            except httpx.RequestError:
                last_failure = HandoffPublishFailureKind.NETWORK
                if attempt < MAX_ATTEMPTS:
                    sleep_fn(RETRY_DELAY_SECONDS)
                    continue
                return HandoffPublishResult(
                    status=HandoffPublishStatus.FAILED,
                    attempts=attempts,
                    failure_kind=last_failure,
                )
            except Exception:
                return HandoffPublishResult(
                    status=HandoffPublishStatus.FAILED,
                    attempts=attempts,
                    failure_kind=HandoffPublishFailureKind.UNEXPECTED,
                )

            if response.status_code in {200, 201}:
                return _result_for_status(
                    status_code=response.status_code,
                    attempts=attempts,
                )

            if (
                response.status_code in _RETRYABLE_STATUS_CODES
                and attempt < MAX_ATTEMPTS
            ):
                sleep_fn(RETRY_DELAY_SECONDS)
                continue

            return _result_for_status(
                status_code=response.status_code,
                attempts=attempts,
            )

        return HandoffPublishResult(
            status=HandoffPublishStatus.FAILED,
            attempts=attempts,
            failure_kind=last_failure,
        )
    finally:
        if owned_client:
            client.close()
