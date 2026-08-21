"""Persistent MCP stdio + pgvector latency gate."""

from __future__ import annotations

import os
from time import perf_counter

import pytest

from ai.app.integrations.mcp.session_manager import McpStdioSessionManager


REQUIRED_ENV = (
    "AI_VECTOR_DSN",
    "AI_VECTOR_TABLE_NAME",
    "AI_EMBEDDING_REVISION",
)


@pytest.mark.skipif(
    any(not os.getenv(name) for name in REQUIRED_ENV),
    reason="persistent MCP latency test requires real pgvector Runtime",
)
def test_warmed_persistent_mcp_first_and_second_search_are_under_five_seconds():
    manager = McpStdioSessionManager()

    arguments = {
        "customer_query": "정수기에서 물이 나오지 않을 때 무엇을 확인해야 하나요?",
        "model_code": "WPUJAC104DWH",
        "symptom_type": None,
        "previous_answers": [],
    }

    try:
        warmup_started = perf_counter()
        assert manager.warmup_search_runtime(timeout_seconds=120.0) is True
        warmup_elapsed = perf_counter() - warmup_started

        started = perf_counter()
        first = manager.call_tool(
            "search_official_evidence",
            arguments,
            timeout_seconds=5.0,
        )
        first_elapsed = perf_counter() - started

        started = perf_counter()
        second = manager.call_tool(
            "search_official_evidence",
            arguments,
            timeout_seconds=5.0,
        )
        second_elapsed = perf_counter() - started

        print(
            "persistent MCP latency "
            f"warmup={warmup_elapsed:.3f}s "
            f"first={first_elapsed:.3f}s "
            f"second={second_elapsed:.3f}s"
        )
    finally:
        manager.close()

    assert not getattr(first, "isError", getattr(first, "is_error", False))
    assert not getattr(second, "isError", getattr(second, "is_error", False))
    assert first_elapsed < 5.0
    assert second_elapsed < 5.0