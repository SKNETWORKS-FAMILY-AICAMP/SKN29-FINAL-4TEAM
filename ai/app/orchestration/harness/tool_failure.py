"""Sanitized MCP Tool failure contract consumed by the Harness.

Raw exception messages are intentionally not part of this contract so they cannot
leak into counselor-facing Handoff payloads.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class McpToolName(str, Enum):
    SEARCH_OFFICIAL_EVIDENCE = "search_official_evidence"
    LOOKUP_PRODUCT_CONTEXT = "lookup_product_context"
    GET_INQUIRY_CONTEXT = "get_inquiry_context"


class McpToolFailureKind(str, Enum):
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    EXECUTION_ERROR = "EXECUTION_ERROR"


class McpToolFailure(BaseModel):
    """Fail-closed, sanitized Tool failure metadata.

    Only allowlisted Tool names and failure kinds are accepted. Raw exception
    messages, stack traces, prompts, request payloads, and PII are deliberately
    excluded via ``extra='forbid'``.
    """

    model_config = ConfigDict(extra="forbid")

    tool_name: McpToolName
    kind: McpToolFailureKind
    retryable: bool = False

    @property
    def retrieval_retry_allowed(self) -> bool:
        """Only the evidence-search Tool is eligible for one Harness retrieval retry."""

        return self.retryable and self.tool_name == McpToolName.SEARCH_OFFICIAL_EVIDENCE
