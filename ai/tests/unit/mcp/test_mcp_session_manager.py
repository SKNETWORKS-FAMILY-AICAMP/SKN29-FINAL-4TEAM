"""Persistent MCP stdio session lifecycle tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai.app.integrations.mcp.session_manager import McpStdioSessionManager


class _FakePersistentClient:
    instances = 0
    connects = 0
    closes = 0
    calls = 0

    def __init__(self):
        type(self).instances += 1

    async def connect(self):
        type(self).connects += 1

    async def close(self):
        type(self).closes += 1

    async def call_tool(self, tool_name, arguments):
        type(self).calls += 1
        return SimpleNamespace(
            isError=False,
            structuredContent={
                "ready": True,
                "status": "ready",
                "tool_name": tool_name,
                "arguments": dict(arguments),
            },
        )


class _FailOnceClient(_FakePersistentClient):
    remaining_failures = 1

    async def call_tool(self, tool_name, arguments):
        type(self).calls += 1
        if type(self).remaining_failures:
            type(self).remaining_failures -= 1
            raise ConnectionError("sanitized-test-transport-failure")
        return SimpleNamespace(
            isError=False,
            structuredContent={
                "ready": True,
                "status": "ready",
                "tool_name": tool_name,
                "arguments": dict(arguments),
            },
        )


def _reset_counts(client_type=_FakePersistentClient):
    client_type.instances = 0
    client_type.connects = 0
    client_type.closes = 0
    client_type.calls = 0
    if hasattr(client_type, "remaining_failures"):
        client_type.remaining_failures = 1


def test_persistent_manager_reuses_one_client_for_consecutive_calls():
    _reset_counts()
    manager = McpStdioSessionManager(client_factory=_FakePersistentClient)

    try:
        first = manager.call_tool("health_check", {})
        second = manager.call_tool("health_check", {})
    finally:
        manager.close()

    assert first.structuredContent["tool_name"] == "health_check"
    assert second.structuredContent["tool_name"] == "health_check"
    assert _FakePersistentClient.instances == 1
    assert _FakePersistentClient.connects == 1
    assert _FakePersistentClient.calls == 2
    assert _FakePersistentClient.closes == 1


def test_persistent_manager_warmup_uses_same_session():
    _reset_counts()
    manager = McpStdioSessionManager(client_factory=_FakePersistentClient)

    try:
        assert manager.warmup_search_runtime(timeout_seconds=1.0) is True
        manager.call_tool(
            "search_official_evidence",
            {"model_code": "WPUJAC104DWH"},
        )
    finally:
        manager.close()

    assert _FakePersistentClient.instances == 1
    assert _FakePersistentClient.connects == 1
    assert _FakePersistentClient.calls == 2
    assert _FakePersistentClient.closes == 1


def test_transport_failure_is_invalidated_and_next_call_reconnects():
    _reset_counts(_FailOnceClient)
    manager = McpStdioSessionManager(client_factory=_FailOnceClient)

    try:
        with pytest.raises(ConnectionError):
            manager.call_tool("health_check", {})

        result = manager.call_tool("health_check", {})
    finally:
        manager.close()

    assert result.structuredContent["status"] == "ready"
    assert _FailOnceClient.instances == 2
    assert _FailOnceClient.connects == 2
    assert _FailOnceClient.closes == 2
    assert _FailOnceClient.calls == 2