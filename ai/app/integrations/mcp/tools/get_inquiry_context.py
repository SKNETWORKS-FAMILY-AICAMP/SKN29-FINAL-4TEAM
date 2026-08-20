"""MCP Tool for privacy-minimized Inquiry and questionnaire Context."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ....integrations.backend import (
    BackendContextClient,
    BackendContextFailureKind,
    BackendInquiryPayload,
)
from .backend_context_common import fetch_backend_context


class GetInquiryContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inquiry_id: UUID
    correlation_id: UUID


class GetInquiryContextOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    inquiry_id: UUID
    correlation_id: UUID
    inquiry_code: str | None = Field(None, max_length=50)
    status_code: str | None = Field(None, max_length=40)
    state_version: int | None = Field(None, ge=1)
    inquiry_context: BackendInquiryPayload | None = None
    failure_kind: BackendContextFailureKind | None = None
    retryable: bool = False

    @model_validator(mode="after")
    def validate_result(self) -> "GetInquiryContextOutput":
        success_fields = (
            self.inquiry_code is not None
            and self.status_code is not None
            and self.state_version is not None
            and self.inquiry_context is not None
            and self.failure_kind is None
        )
        failure_fields = (
            self.inquiry_code is None
            and self.status_code is None
            and self.state_version is None
            and self.inquiry_context is None
            and self.failure_kind is not None
        )
        if not (success_fields if self.success else failure_fields):
            raise ValueError("Inquiry Context Tool result is inconsistent")
        return self


class GetInquiryContextAdapter:
    def __init__(
        self,
        client_factory: Callable[[], BackendContextClient] = (
            BackendContextClient.from_environment
        ),
    ) -> None:
        self.client_factory = client_factory

    def execute(
        self,
        request: GetInquiryContextInput,
    ) -> GetInquiryContextOutput:
        context, failure_kind, retryable = fetch_backend_context(
            inquiry_id=request.inquiry_id,
            correlation_id=request.correlation_id,
            client_factory=self.client_factory,
        )
        return GetInquiryContextOutput(
            success=context is not None,
            inquiry_id=request.inquiry_id,
            correlation_id=request.correlation_id,
            inquiry_code=(context.inquiry_code if context is not None else None),
            status_code=(context.status_code if context is not None else None),
            state_version=(context.state_version if context is not None else None),
            inquiry_context=(context.inquiry_context if context is not None else None),
            failure_kind=failure_kind,
            retryable=retryable,
        )
