"""Backend Context MCP Tool adapters."""

from __future__ import annotations

from uuid import uuid4

from ai.app.integrations.backend import (
    BackendContextClientError,
    BackendContextFailureKind,
    BackendInquiryContext,
)
from ai.app.integrations.mcp.tools.get_inquiry_context import (
    GetInquiryContextAdapter,
    GetInquiryContextInput,
)
from ai.app.integrations.mcp.tools.lookup_product_context import (
    LookupProductContextAdapter,
    LookupProductContextInput,
)


def _context(inquiry_id, correlation_id):
    return BackendInquiryContext.model_validate(
        {
            "inquiry_id": inquiry_id,
            "inquiry_code": "INQ-TEST",
            "status_code": "QUESTIONNAIRE_IN_PROGRESS",
            "state_version": 2,
            "correlation_id": correlation_id,
            "product_context": {
                "subscription_id": uuid4(),
                "subscription_status_code": "ACTIVE",
                "management_type_code": "SELF_MANAGED",
                "product_model_id": uuid4(),
                "model_code": "WPUIAC606SNW",
                "model_name": "IAC606",
                "product_family": "ICE_WATER_PURIFIER",
                "generation_code": "ICE",
                "manufacturer": "SK매직",
                "features": {
                    "model_family": "WPU-IAC606",
                    "water_modes": ["COLD"],
                    "supported_functions": ["ICE"],
                },
            },
            "inquiry_context": {
                "customer_query": "얼음이 나오지 않아요.",
                "symptom_type": "NO_ICE",
                "selected_symptoms": ["NO_ICE"],
                "previous_answers": [],
            },
        }
    )


class _FakeClient:
    def __init__(self, context=None, error=None):
        self.context = context
        self.error = error
        self.closed = False

    def get_context(self, *, inquiry_id, correlation_id):
        if self.error is not None:
            raise self.error
        assert self.context.inquiry_id == inquiry_id
        assert self.context.correlation_id == correlation_id
        return self.context

    def close(self):
        self.closed = True


def test_product_and_inquiry_tools_project_the_same_backend_context():
    inquiry_id = uuid4()
    correlation_id = uuid4()
    context = _context(inquiry_id, correlation_id)
    clients = []

    def factory():
        client = _FakeClient(context=context)
        clients.append(client)
        return client

    product = LookupProductContextAdapter(factory).execute(
        LookupProductContextInput(
            inquiry_id=inquiry_id,
            correlation_id=correlation_id,
        )
    )
    inquiry = GetInquiryContextAdapter(factory).execute(
        GetInquiryContextInput(
            inquiry_id=inquiry_id,
            correlation_id=correlation_id,
        )
    )

    assert product.success is True
    assert product.product_context.model_code == "WPUIAC606SNW"
    assert inquiry.success is True
    assert inquiry.inquiry_context.customer_query == "얼음이 나오지 않아요."
    assert inquiry.state_version == 2
    assert all(client.closed for client in clients)


def test_context_tool_failure_returns_only_sanitized_metadata():
    error = BackendContextClientError(
        kind=BackendContextFailureKind.UNAVAILABLE,
        retryable=False,
    )
    output = LookupProductContextAdapter(
        lambda: _FakeClient(error=error)
    ).execute(
        LookupProductContextInput(
            inquiry_id=uuid4(),
            correlation_id=uuid4(),
        )
    )

    assert output.success is False
    assert output.product_context is None
    assert output.failure_kind == BackendContextFailureKind.UNAVAILABLE
    assert output.retryable is False
    assert set(output.model_dump()) == {
        "success",
        "inquiry_id",
        "correlation_id",
        "product_context",
        "failure_kind",
        "retryable",
    }
