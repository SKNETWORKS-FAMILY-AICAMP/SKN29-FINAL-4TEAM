"""Privacy-minimized read-only Backend Inquiry Context client."""

from __future__ import annotations

import os
from enum import Enum
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class BackendContextFailureKind(str, Enum):
    """Sanitized failure categories safe to cross the MCP boundary."""

    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    EXECUTION_ERROR = "EXECUTION_ERROR"


class BackendContextClientError(RuntimeError):
    """Backend Context lookup failed without exposing URL, token, or response body."""

    def __init__(
        self,
        *,
        kind: BackendContextFailureKind,
        retryable: bool,
    ) -> None:
        self.kind = kind
        self.retryable = retryable
        super().__init__(f"Backend Context lookup failed ({kind.value})")


class BackendPreviousAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(..., min_length=1, max_length=100)
    answer_text: str = Field(..., min_length=1, max_length=1000)


class BackendProductFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_family: str | None = Field(None, max_length=100)
    water_modes: list[str] = Field(default_factory=list, max_length=20)
    supported_functions: list[str] = Field(default_factory=list, max_length=40)


class BackendProductContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscription_id: UUID
    subscription_status_code: str = Field(..., min_length=1, max_length=40)
    management_type_code: str = Field(..., min_length=1, max_length=40)
    product_model_id: UUID
    model_code: str = Field(..., min_length=1, max_length=60)
    model_name: str = Field(..., min_length=1, max_length=150)
    product_family: Literal[
        "DIRECT_WATER_PURIFIER",
        "ICE_WATER_PURIFIER",
        "UNKNOWN",
    ]
    generation_code: str | None = Field(None, max_length=40)
    manufacturer: str = Field(..., min_length=1, max_length=100)
    features: BackendProductFeatures


class BackendInquiryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_query: str = Field(..., min_length=1, max_length=4000)
    symptom_type: str | None = Field(None, max_length=200)
    selected_symptoms: list[str] = Field(default_factory=list, max_length=30)
    previous_answers: list[BackendPreviousAnswer] = Field(
        default_factory=list,
        max_length=50,
    )


class BackendInquiryContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inquiry_id: UUID
    inquiry_code: str = Field(..., min_length=1, max_length=50)
    status_code: str = Field(..., min_length=1, max_length=40)
    state_version: int = Field(..., ge=1)
    correlation_id: UUID
    product_context: BackendProductContext
    inquiry_context: BackendInquiryPayload


class _BackendContextMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: UUID


class _BackendContextEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: Literal[True]
    data: BackendInquiryContext
    error: None
    metadata: _BackendContextMetadata


class BackendContextClient:
    """Call the protected Backend Context endpoint with process-injected secrets."""

    BASE_URL_ENV = "AI_BACKEND_BASE_URL"
    TOKEN_ENV = "AI_HANDOFF_INTERNAL_TOKEN"
    TIMEOUT_ENV = "AI_BACKEND_CONTEXT_TIMEOUT_SECONDS"
    DEFAULT_TIMEOUT_SECONDS = 3.0

    def __init__(
        self,
        *,
        base_url: str,
        handoff_token: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = self._validated_base_url(base_url)
        self._handoff_token = self._validated_token(handoff_token)
        if not 0.1 <= timeout_seconds <= 30.0:
            raise BackendContextClientError(
                kind=BackendContextFailureKind.UNAVAILABLE,
                retryable=False,
            )
        self.timeout_seconds = timeout_seconds
        self._http_client = http_client
        self._owns_http_client = http_client is None

    @classmethod
    def from_environment(cls) -> "BackendContextClient":
        raw_timeout = os.getenv(
            cls.TIMEOUT_ENV,
            str(cls.DEFAULT_TIMEOUT_SECONDS),
        )
        try:
            timeout_seconds = float(raw_timeout)
        except ValueError as exc:
            raise BackendContextClientError(
                kind=BackendContextFailureKind.UNAVAILABLE,
                retryable=False,
            ) from exc
        return cls(
            base_url=os.getenv(cls.BASE_URL_ENV, ""),
            handoff_token=os.getenv(cls.TOKEN_ENV, ""),
            timeout_seconds=timeout_seconds,
        )

    def get_context(
        self,
        *,
        inquiry_id: UUID,
        correlation_id: UUID,
    ) -> BackendInquiryContext:
        client = self._http_client or httpx.Client()
        if self._http_client is None:
            self._http_client = client
        try:
            response = client.get(
                (
                    f"{self.base_url}/api/v1/internal/ai/inquiries/"
                    f"{inquiry_id}/context"
                ),
                headers={
                    "X-AI-Handoff-Token": self._handoff_token,
                    "X-Correlation-ID": str(correlation_id),
                },
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise BackendContextClientError(
                kind=BackendContextFailureKind.TIMEOUT,
                retryable=True,
            ) from exc
        except httpx.TransportError as exc:
            raise BackendContextClientError(
                kind=BackendContextFailureKind.UNAVAILABLE,
                retryable=True,
            ) from exc

        self._raise_for_status(response.status_code)
        if response.headers.get("X-Correlation-ID") != str(correlation_id):
            raise BackendContextClientError(
                kind=BackendContextFailureKind.INVALID_RESPONSE,
                retryable=False,
            )
        try:
            envelope = _BackendContextEnvelope.model_validate(response.json())
        except (ValidationError, TypeError, ValueError) as exc:
            raise BackendContextClientError(
                kind=BackendContextFailureKind.INVALID_RESPONSE,
                retryable=False,
            ) from exc

        context = envelope.data
        if (
            context.inquiry_id != inquiry_id
            or context.correlation_id != correlation_id
            or envelope.metadata.correlation_id != correlation_id
        ):
            raise BackendContextClientError(
                kind=BackendContextFailureKind.INVALID_RESPONSE,
                retryable=False,
            )
        return context

    def close(self) -> None:
        if self._owns_http_client and self._http_client is not None:
            self._http_client.close()
            self._http_client = None

    def __enter__(self) -> "BackendContextClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    @staticmethod
    def _validated_base_url(value: str) -> str:
        candidate = value.strip().rstrip("/")
        parsed = urlsplit(candidate)
        valid = (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
            and parsed.path in {"", "/"}
        )
        if not valid:
            raise BackendContextClientError(
                kind=BackendContextFailureKind.UNAVAILABLE,
                retryable=False,
            )
        return candidate

    @staticmethod
    def _validated_token(value: str) -> str:
        if (
            not value.strip()
            or value != value.strip()
            or "\r" in value
            or "\n" in value
            or len(value) > 4096
        ):
            raise BackendContextClientError(
                kind=BackendContextFailureKind.UNAVAILABLE,
                retryable=False,
            )
        return value

    @staticmethod
    def _raise_for_status(status_code: int) -> None:
        if status_code < 400:
            return
        if status_code in {408, 504}:
            kind = BackendContextFailureKind.TIMEOUT
            retryable = True
        elif status_code in {409, 429} or status_code >= 500:
            kind = BackendContextFailureKind.UNAVAILABLE
            retryable = True
        elif status_code in {401, 403}:
            kind = BackendContextFailureKind.UNAVAILABLE
            retryable = False
        else:
            kind = BackendContextFailureKind.EXECUTION_ERROR
            retryable = False
        raise BackendContextClientError(kind=kind, retryable=retryable)
