"""Synchronous Pipeline facade for Backend Context MCP Tools."""

from __future__ import annotations

import asyncio
import json
import os
from enum import Enum
from time import monotonic
from typing import Any, Callable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError

from ...common.timeout import CancellationToken
from ..backend import (
    BackendContextFailureKind,
    BackendInquiryPayload,
    BackendProductContext,
)
from .client import WaterBridgeMCPClient
from .session_manager import get_shared_mcp_session_manager
from .tools.get_inquiry_context import GetInquiryContextOutput
from .tools.lookup_product_context import LookupProductContextOutput


class McpBackendContextToolName(str, Enum):
    LOOKUP_PRODUCT_CONTEXT = "lookup_product_context"
    GET_INQUIRY_CONTEXT = "get_inquiry_context"


class McpBackendContextError(RuntimeError):
    """Sanitized Backend Context Tool failure consumed by PipelineRouter."""

    def __init__(
        self,
        *,
        tool_name: McpBackendContextToolName,
        kind: BackendContextFailureKind,
        retryable: bool,
    ) -> None:
        self.tool_name = tool_name
        self.kind = kind
        self.retryable = retryable
        super().__init__(
            f"MCP Backend Context failed ({tool_name.value}/{kind.value})"
        )


class ResolvedBackendContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inquiry_id: UUID
    correlation_id: UUID
    inquiry_code: str
    status_code: str
    state_version: int
    product_context: BackendProductContext
    inquiry_context: BackendInquiryPayload


class McpBackendContextService:
    """Resolve Product and Inquiry Context through one MCP client session."""

    TIMEOUT_ENV = "AI_MCP_CONTEXT_TIMEOUT_SECONDS"
    DEFAULT_TIMEOUT_SECONDS = 8.0

    def __init__(
        self,
        *,
        client_factory: Callable[[], WaterBridgeMCPClient] = WaterBridgeMCPClient,
        timeout_seconds: float | None = None,
    ) -> None:
        self._client_factory = client_factory
        self.timeout_seconds = (
            self._timeout_from_environment()
            if timeout_seconds is None
            else timeout_seconds
        )
        if not 0.1 <= self.timeout_seconds <= 30.0:
            raise McpBackendContextError(
                tool_name=McpBackendContextToolName.LOOKUP_PRODUCT_CONTEXT,
                kind=BackendContextFailureKind.UNAVAILABLE,
                retryable=False,
            )

    def resolve(
        self,
        *,
        inquiry_id: UUID,
        correlation_id: UUID,
        expected_state_version: int,
        expected_model_code: str,
        cancellation_token: CancellationToken | None = None,
    ) -> ResolvedBackendContext:
        token = cancellation_token or CancellationToken()
        token.raise_if_cancelled()
        try:
            if self._client_factory is WaterBridgeMCPClient:
                product, inquiry = self._call_tools_persistent(
                    inquiry_id=inquiry_id,
                    correlation_id=correlation_id,
                )
            else:
                product, inquiry = asyncio.run(
                    asyncio.wait_for(
                        self._call_tools(
                            inquiry_id=inquiry_id,
                            correlation_id=correlation_id,
                        ),
                        timeout=self.timeout_seconds,
                    )
                )
        except TimeoutError as exc:
            raise McpBackendContextError(
                tool_name=McpBackendContextToolName.LOOKUP_PRODUCT_CONTEXT,
                kind=BackendContextFailureKind.TIMEOUT,
                retryable=True,
            ) from exc
        except (ConnectionError, OSError) as exc:
            raise McpBackendContextError(
                tool_name=McpBackendContextToolName.LOOKUP_PRODUCT_CONTEXT,
                kind=BackendContextFailureKind.UNAVAILABLE,
                retryable=True,
            ) from exc
        except McpBackendContextError:
            raise
        except Exception as exc:
            raise McpBackendContextError(
                tool_name=McpBackendContextToolName.LOOKUP_PRODUCT_CONTEXT,
                kind=BackendContextFailureKind.EXECUTION_ERROR,
                retryable=False,
            ) from exc

        token.raise_if_cancelled()
        valid_identity = (
            product.inquiry_id == inquiry_id
            and inquiry.inquiry_id == inquiry_id
            and product.correlation_id == correlation_id
            and inquiry.correlation_id == correlation_id
            and inquiry.state_version == expected_state_version
            and product.product_context is not None
            and product.product_context.model_code == expected_model_code
        )
        if not valid_identity:
            raise McpBackendContextError(
                tool_name=McpBackendContextToolName.GET_INQUIRY_CONTEXT,
                kind=BackendContextFailureKind.INVALID_RESPONSE,
                retryable=False,
            )
        if (
            inquiry.inquiry_code is None
            or inquiry.status_code is None
            or inquiry.state_version is None
            or inquiry.inquiry_context is None
        ):
            raise McpBackendContextError(
                tool_name=McpBackendContextToolName.GET_INQUIRY_CONTEXT,
                kind=BackendContextFailureKind.INVALID_RESPONSE,
                retryable=False,
            )
        return ResolvedBackendContext(
            inquiry_id=inquiry_id,
            correlation_id=correlation_id,
            inquiry_code=inquiry.inquiry_code,
            status_code=inquiry.status_code,
            state_version=inquiry.state_version,
            product_context=product.product_context,
            inquiry_context=inquiry.inquiry_context,
        )

    def _call_tools_persistent(
        self,
        *,
        inquiry_id: UUID,
        correlation_id: UUID,
    ) -> tuple[LookupProductContextOutput, GetInquiryContextOutput]:
        """Resolve both Backend Context Tools on the shared MCP stdio session."""

        manager = get_shared_mcp_session_manager()
        deadline = monotonic() + self.timeout_seconds
        arguments = {
            "inquiry_id": str(inquiry_id),
            "correlation_id": str(correlation_id),
        }

        def remaining_timeout() -> float:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError("MCP Backend Context timeout")
            return remaining

        product_result = manager.call_tool(
            McpBackendContextToolName.LOOKUP_PRODUCT_CONTEXT.value,
            arguments,
            timeout_seconds=remaining_timeout(),
        )
        product = self._parse_output(
            product_result,
            LookupProductContextOutput,
            McpBackendContextToolName.LOOKUP_PRODUCT_CONTEXT,
        )
        self._raise_tool_failure(
            product,
            McpBackendContextToolName.LOOKUP_PRODUCT_CONTEXT,
        )

        inquiry_result = manager.call_tool(
            McpBackendContextToolName.GET_INQUIRY_CONTEXT.value,
            arguments,
            timeout_seconds=remaining_timeout(),
        )
        inquiry = self._parse_output(
            inquiry_result,
            GetInquiryContextOutput,
            McpBackendContextToolName.GET_INQUIRY_CONTEXT,
        )
        self._raise_tool_failure(
            inquiry,
            McpBackendContextToolName.GET_INQUIRY_CONTEXT,
        )

        return product, inquiry
    async def _call_tools(
        self,
        *,
        inquiry_id: UUID,
        correlation_id: UUID,
    ) -> tuple[LookupProductContextOutput, GetInquiryContextOutput]:
        arguments = {
            "inquiry_id": str(inquiry_id),
            "correlation_id": str(correlation_id),
        }
        async with self._client_factory() as client:
            product_result = await client.call_tool(
                McpBackendContextToolName.LOOKUP_PRODUCT_CONTEXT.value,
                arguments,
            )
            product = self._parse_output(
                product_result,
                LookupProductContextOutput,
                McpBackendContextToolName.LOOKUP_PRODUCT_CONTEXT,
            )
            self._raise_tool_failure(
                product,
                McpBackendContextToolName.LOOKUP_PRODUCT_CONTEXT,
            )

            inquiry_result = await client.call_tool(
                McpBackendContextToolName.GET_INQUIRY_CONTEXT.value,
                arguments,
            )
            inquiry = self._parse_output(
                inquiry_result,
                GetInquiryContextOutput,
                McpBackendContextToolName.GET_INQUIRY_CONTEXT,
            )
            self._raise_tool_failure(
                inquiry,
                McpBackendContextToolName.GET_INQUIRY_CONTEXT,
            )
            return product, inquiry

    @classmethod
    def _parse_output(
        cls,
        result: Any,
        schema: type[BaseModel],
        tool_name: McpBackendContextToolName,
    ) -> Any:
        if bool(
            getattr(result, "isError", False)
            or getattr(result, "is_error", False)
        ):
            raise McpBackendContextError(
                tool_name=tool_name,
                kind=BackendContextFailureKind.EXECUTION_ERROR,
                retryable=False,
            )
        payload = getattr(result, "structuredContent", None)
        if payload is None:
            payload = getattr(result, "structured_content", None)
        if payload is None:
            payload = cls._text_payload(result, tool_name)
        try:
            return schema.model_validate(payload)
        except (ValidationError, TypeError, ValueError) as exc:
            raise McpBackendContextError(
                tool_name=tool_name,
                kind=BackendContextFailureKind.INVALID_RESPONSE,
                retryable=False,
            ) from exc

    @staticmethod
    def _text_payload(
        result: Any,
        tool_name: McpBackendContextToolName,
    ) -> Any:
        content = getattr(result, "content", None)
        if isinstance(content, list):
            for item in content:
                text = getattr(item, "text", None)
                if not isinstance(text, str):
                    continue
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    continue
        raise McpBackendContextError(
            tool_name=tool_name,
            kind=BackendContextFailureKind.INVALID_RESPONSE,
            retryable=False,
        )

    @staticmethod
    def _raise_tool_failure(
        output: LookupProductContextOutput | GetInquiryContextOutput,
        tool_name: McpBackendContextToolName,
    ) -> None:
        if output.success:
            return
        raise McpBackendContextError(
            tool_name=tool_name,
            kind=output.failure_kind or BackendContextFailureKind.INVALID_RESPONSE,
            retryable=output.retryable,
        )

    @classmethod
    def _timeout_from_environment(cls) -> float:
        try:
            return float(os.getenv(cls.TIMEOUT_ENV, str(cls.DEFAULT_TIMEOUT_SECONDS)))
        except ValueError as exc:
            raise McpBackendContextError(
                tool_name=McpBackendContextToolName.LOOKUP_PRODUCT_CONTEXT,
                kind=BackendContextFailureKind.UNAVAILABLE,
                retryable=False,
            ) from exc
