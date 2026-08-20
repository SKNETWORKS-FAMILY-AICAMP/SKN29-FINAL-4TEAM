"""MCP Tool for the subscription-owned exact Product Context."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ....integrations.backend import (
    BackendContextClient,
    BackendContextFailureKind,
    BackendProductContext,
)
from .backend_context_common import fetch_backend_context


class LookupProductContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inquiry_id: UUID
    correlation_id: UUID


class LookupProductContextOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    inquiry_id: UUID
    correlation_id: UUID
    product_context: BackendProductContext | None = None
    failure_kind: BackendContextFailureKind | None = None
    retryable: bool = False

    @model_validator(mode="after")
    def validate_result(self) -> "LookupProductContextOutput":
        valid = (
            self.product_context is not None and self.failure_kind is None
            if self.success
            else self.product_context is None and self.failure_kind is not None
        )
        if not valid:
            raise ValueError("Product Context Tool result is inconsistent")
        return self


class LookupProductContextAdapter:
    def __init__(
        self,
        client_factory: Callable[[], BackendContextClient] = (
            BackendContextClient.from_environment
        ),
    ) -> None:
        self.client_factory = client_factory

    def execute(
        self,
        request: LookupProductContextInput,
    ) -> LookupProductContextOutput:
        context, failure_kind, retryable = fetch_backend_context(
            inquiry_id=request.inquiry_id,
            correlation_id=request.correlation_id,
            client_factory=self.client_factory,
        )
        return LookupProductContextOutput(
            success=context is not None,
            inquiry_id=request.inquiry_id,
            correlation_id=request.correlation_id,
            product_context=(context.product_context if context is not None else None),
            failure_kind=failure_kind,
            retryable=retryable,
        )
