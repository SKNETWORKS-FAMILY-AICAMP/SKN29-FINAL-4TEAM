"""WaterBridge MCP stdio subprocess integration tests.

These tests intentionally use the real WaterBridgeMCPClient. No fake MCP
client is allowed here: the purpose is to verify the actual stdio subprocess,
MCP handshake, Tool registration, and (when configured) pgvector search path.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest


AI_ROOT = Path(__file__).resolve().parents[2]
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from app.integrations.mcp.client import WaterBridgeMCPClient  # noqa: E402


REQUIRED_PGVECTOR_ENV = (
    "AI_VECTOR_DSN",
    "AI_VECTOR_TABLE_NAME",
    "AI_EMBEDDING_REVISION",
)

JAC104_MODEL_CODE = "WPUJAC104DWH"
IAC425_MODEL_CODE = "WPUIAC425SNW"


def _run(coro):
    return asyncio.run(coro)


def _is_error(result: Any) -> bool:
    return bool(
        getattr(
            result,
            "is_error",
            getattr(result, "isError", False),
        )
    )


def _structured_payload(result: Any) -> dict[str, Any]:
    if _is_error(result):
        pytest.fail("MCP Tool returned is_error=True")

    payload = getattr(result, "structured_content", None)
    if payload is None:
        payload = getattr(result, "structuredContent", None)

    if payload is None:
        content = getattr(result, "content", None)
        if isinstance(content, list):
            for item in content:
                text = getattr(item, "text", None)
                if not isinstance(text, str):
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue
                break

    assert isinstance(payload, dict), "MCP Tool structured payload must be a dict"
    return payload


async def _list_tools_and_health() -> tuple[set[str], dict[str, Any]]:
    async with WaterBridgeMCPClient() as client:
        listed = await client.list_tools()
        names = {tool.name for tool in listed.tools}
        health_result = await client.call_tool("health_check", {})
        health = _structured_payload(health_result)
        return names, health


def test_stdio_server_starts_lists_tools_and_runs_health_check():
    names, health = _run(_list_tools_and_health())

    assert "health_check" in names
    assert "search_official_evidence" in names
    assert health["status"] == "ok"
    assert health["service"] == "waterbridge-mcp"


async def _call_search_official_evidence(
    *,
    customer_query: str,
    model_code: str,
) -> dict[str, Any]:
    async with WaterBridgeMCPClient() as client:
        result = await client.call_tool(
            "search_official_evidence",
            {
                "customer_query": customer_query,
                "model_code": model_code,
                "symptom_type": None,
                "previous_answers": [],
            },
        )
        return _structured_payload(result)


def test_stdio_policy_block_for_prepared_but_inactive_iac425_without_pgvector():
    payload = _run(
        _call_search_official_evidence(
            customer_query="온수가 나오지 않아요.",
            model_code=IAC425_MODEL_CODE,
        )
    )

    assert payload["policy_blocked"] is True
    assert payload["vector_search_executed"] is False
    assert payload["search_result_found"] is False
    assert payload["evidence_found"] is False
    assert payload["evidence_references"] == []

    execution_path = payload.get("policy_execution_path")
    assert isinstance(execution_path, str)
    assert execution_path.startswith("POLICY_BLOCK_")


@pytest.mark.skipif(
    any(not os.getenv(name) for name in REQUIRED_PGVECTOR_ENV),
    reason=(
        "real pgvector MCP search requires "
        "AI_VECTOR_DSN, AI_VECTOR_TABLE_NAME, AI_EMBEDDING_REVISION"
    ),
)
def test_stdio_jac104_search_reaches_real_pgvector_and_returns_verified_evidence():
    payload = _run(
        _call_search_official_evidence(
            customer_query="정수기에서 물이 나오지 않을 때 무엇을 확인해야 하나요?",
            model_code=JAC104_MODEL_CODE,
        )
    )

    assert payload["policy_blocked"] is False
    assert payload["vector_search_executed"] is True
    assert payload["search_result_found"] is True
    assert payload["evidence_found"] is True

    evidence = payload["evidence_references"]
    assert evidence
    assert evidence[0]["chunk_id"] == "RAG-WPUJAC104DWH-NO-WATER-001"
    assert all(
        item["verification_status"] == "official_verified"
        for item in evidence
    )
    assert all(item["page_refs"] for item in evidence)
