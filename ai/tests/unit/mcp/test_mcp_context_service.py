"""MCP Product+Inquiry Context resolver integrity checks."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from ai.app.integrations.backend import BackendContextFailureKind
from ai.app.integrations.mcp.context_service import (
    McpBackendContextError,
    McpBackendContextService,
    McpBackendContextToolName,
)


class _Result:
    def __init__(self, payload):
        self.structuredContent = payload
        self.isError = False


class _Client:
    def __init__(self, responses, *, delay=0.0):
        self.responses = responses
        self.delay = delay
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def call_tool(self, tool_name, arguments):
        self.calls.append((tool_name, dict(arguments)))
        if self.delay:
            await asyncio.sleep(self.delay)
        return _Result(self.responses[tool_name])


def _responses(inquiry_id, correlation_id, *, model_code="WPUIAC425SNW"):
    product = {
        "success": True,
        "inquiry_id": str(inquiry_id),
        "correlation_id": str(correlation_id),
        "product_context": {
            "subscription_id": str(uuid4()),
            "subscription_status_code": "ACTIVE",
            "management_type_code": "SELF_MANAGED",
            "product_model_id": str(uuid4()),
            "model_code": model_code,
            "model_name": "IAC425",
            "product_family": "ICE_WATER_PURIFIER",
            "generation_code": "ICE",
            "manufacturer": "SK매직",
            "features": {
                "model_family": "WPU-IAC425",
                "water_modes": ["COLD", "HOT"],
                "supported_functions": ["HOT_WATER"],
            },
        },
        "failure_kind": None,
        "retryable": False,
    }
    inquiry = {
        "success": True,
        "inquiry_id": str(inquiry_id),
        "correlation_id": str(correlation_id),
        "inquiry_code": "INQ-TEST",
        "status_code": "QUESTIONNAIRE_IN_PROGRESS",
        "state_version": 4,
        "inquiry_context": {
            "customer_query": "온수가 나오지 않아요.",
            "symptom_type": "HOT_WATER_STOPPED",
            "selected_symptoms": ["HOT_WATER_STOPPED"],
            "previous_answers": [],
        },
        "failure_kind": None,
        "retryable": False,
    }
    return {
        "lookup_product_context": product,
        "get_inquiry_context": inquiry,
    }


def test_context_service_calls_both_tools_and_preserves_exact_model_code():
    inquiry_id = uuid4()
    correlation_id = uuid4()
    client = _Client(_responses(inquiry_id, correlation_id))
    service = McpBackendContextService(
        client_factory=lambda: client,
        timeout_seconds=1.0,
    )

    resolved = service.resolve(
        inquiry_id=inquiry_id,
        correlation_id=correlation_id,
        expected_state_version=4,
        expected_model_code="WPUIAC425SNW",
    )

    assert resolved.product_context.model_code == "WPUIAC425SNW"
    assert resolved.inquiry_context.customer_query == "온수가 나오지 않아요."
    assert [name for name, _args in client.calls] == [
        "lookup_product_context",
        "get_inquiry_context",
    ]
    assert all(
        args["correlation_id"] == str(correlation_id)
        for _name, args in client.calls
    )


def test_context_service_fails_closed_on_request_product_mismatch():
    inquiry_id = uuid4()
    correlation_id = uuid4()
    service = McpBackendContextService(
        client_factory=lambda: _Client(
            _responses(inquiry_id, correlation_id, model_code="WPUIAC606SNW")
        ),
        timeout_seconds=1.0,
    )

    with pytest.raises(McpBackendContextError) as exc_info:
        service.resolve(
            inquiry_id=inquiry_id,
            correlation_id=correlation_id,
            expected_state_version=4,
            expected_model_code="WPUIAC425SNW",
        )

    assert exc_info.value.kind == BackendContextFailureKind.INVALID_RESPONSE
    assert exc_info.value.retryable is False


def test_context_service_timeout_is_fail_closed():
    inquiry_id = uuid4()
    correlation_id = uuid4()
    service = McpBackendContextService(
        client_factory=lambda: _Client(
            _responses(inquiry_id, correlation_id),
            delay=0.2,
        ),
        timeout_seconds=0.1,
    )

    with pytest.raises(McpBackendContextError) as exc_info:
        service.resolve(
            inquiry_id=inquiry_id,
            correlation_id=correlation_id,
            expected_state_version=4,
            expected_model_code="WPUIAC425SNW",
        )

    assert exc_info.value.tool_name == (
        McpBackendContextToolName.LOOKUP_PRODUCT_CONTEXT
    )
    assert exc_info.value.kind == BackendContextFailureKind.TIMEOUT
    assert exc_info.value.retryable is True
