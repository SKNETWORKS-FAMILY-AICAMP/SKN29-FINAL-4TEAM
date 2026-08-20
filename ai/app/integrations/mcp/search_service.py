"""Synchronous Retrieval SearchService facade backed by the WaterBridge MCP Tool.

The orchestration pipeline is synchronous today, while the MCP SDK client is
async.  This adapter bridges that boundary without changing the existing
``search_service.search(RetrievalQuery)`` contract.

Raw MCP exceptions are never exposed to the Harness.  They are converted to a
small sanitized failure object and translated to ``McpToolFailure`` only at the
orchestration boundary.
"""

from __future__ import annotations

import asyncio
import json
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...common.timeout import CancellationToken
from ...retrieval.models.retrieval_query import RetrievalQuery
from ...retrieval.models.retrieved_chunk import RetrievedChunk
from ...schemas import EvidenceReference
from .client import WaterBridgeMCPClient


class _SearchOfficialEvidenceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    """MCP transport boundary response shape."""

    evidence_references: list[EvidenceReference] = Field(default_factory=list)
    vector_search_executed: bool = False
    search_result_found: bool = False
    evidence_found: bool = False
    policy_blocked: bool = False
    policy_execution_path: str | None = None
    applied_rule_id: str | None = None
    block_reason: str | None = None


class McpEvidenceFailureKind(str, Enum):
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    EXECUTION_ERROR = "EXECUTION_ERROR"


class McpEvidenceSearchError(RuntimeError):
    """Sanitized exception crossing MCP -> orchestration."""

    def __init__(
        self,
        *,
        kind: McpEvidenceFailureKind,
        retryable: bool,
    ) -> None:
        self.kind = kind
        self.retryable = retryable
        super().__init__(f"MCP evidence search failed ({kind.value})")


class McpEvidenceSearchService:
    """Expose ``search()`` while executing the MCP ``search_official_evidence`` Tool."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], WaterBridgeMCPClient] = WaterBridgeMCPClient,
    ) -> None:
        self._client_factory = client_factory

    def search(
        self,
        query: RetrievalQuery,
        *,
        cancellation_token: CancellationToken | None = None,
    ) -> list[RetrievedChunk]:
        token = cancellation_token or CancellationToken()
        token.raise_if_cancelled()

        try:
            result = asyncio.run(self._call_tool(query))
        except TimeoutError as exc:
            raise McpEvidenceSearchError(
                kind=McpEvidenceFailureKind.TIMEOUT,
                retryable=True,
            ) from exc
        except (ConnectionError, OSError) as exc:
            raise McpEvidenceSearchError(
                kind=McpEvidenceFailureKind.UNAVAILABLE,
                retryable=True,
            ) from exc
        except McpEvidenceSearchError:
            raise
        except Exception as exc:
            raise McpEvidenceSearchError(
                kind=McpEvidenceFailureKind.EXECUTION_ERROR,
                retryable=False,
            ) from exc

        token.raise_if_cancelled()
        output = self._parse_output(result)
        if output.policy_blocked or not output.evidence_found:
            return []

        generation = query.product_generation or "D"
        model_code = query.model_code or ""

        # The MCP server executes VectorSearchService with the exact sales code.
        # Reconstruct only fields present in the allowlisted MCP response plus
        # the request identity used for that exact-match search.  The outer
        # GuardedEvidenceSearchService still performs the independent product
        # match gate before any chunk can reach generation.
        return [
            RetrievedChunk(
                chunk_id=evidence.chunk_id,
                document_title=evidence.document_title,
                document_version=evidence.document_version,
                page=evidence.page,
                page_refs=evidence.page_refs,
                manual_model=model_code,
                model_code=model_code,
                product_generation=generation,
                content=evidence.summary,
                similarity_score=evidence.similarity_score,
                official_url=evidence.official_url,
                verification_status=evidence.verification_status,
                allowed_use=True,
                runtime_eligible=True,
            )
            for evidence in output.evidence_references
        ]

    async def _call_tool(self, query: RetrievalQuery):
        arguments = {
            "customer_query": query.query_text,
            "model_code": query.model_code,
            "symptom_type": None,
            "previous_answers": [],
        }
        async with self._client_factory() as client:
            return await client.call_tool(
                "search_official_evidence",
                arguments,
            )

    @classmethod
    def _parse_output(cls, result: Any) -> _SearchOfficialEvidenceOutput:
        if bool(
            getattr(result, "isError", False)
            or getattr(result, "is_error", False)
        ):
            raise McpEvidenceSearchError(
                kind=McpEvidenceFailureKind.EXECUTION_ERROR,
                retryable=False,
            )

        payload = getattr(result, "structuredContent", None)
        if payload is None:
            payload = getattr(result, "structured_content", None)

        if payload is None:
            payload = cls._text_payload(result)

        try:
            return _SearchOfficialEvidenceOutput.model_validate(payload)
        except (ValidationError, TypeError, ValueError) as exc:
            raise McpEvidenceSearchError(
                kind=McpEvidenceFailureKind.INVALID_RESPONSE,
                retryable=False,
            ) from exc

    @staticmethod
    def _text_payload(result: Any) -> Any:
        content = getattr(result, "content", None)
        if not isinstance(content, list):
            raise McpEvidenceSearchError(
                kind=McpEvidenceFailureKind.INVALID_RESPONSE,
                retryable=False,
            )

        for item in content:
            text = getattr(item, "text", None)
            if not isinstance(text, str):
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue

        raise McpEvidenceSearchError(
            kind=McpEvidenceFailureKind.INVALID_RESPONSE,
            retryable=False,
        )
