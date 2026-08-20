"""Shared fail-closed helpers for Backend Context MCP Tools."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from ....integrations.backend import (
    BackendContextClient,
    BackendContextClientError,
    BackendContextFailureKind,
    BackendInquiryContext,
)


BackendContextClientFactory = Callable[[], BackendContextClient]


def fetch_backend_context(
    *,
    inquiry_id: UUID,
    correlation_id: UUID,
    client_factory: BackendContextClientFactory,
) -> tuple[BackendInquiryContext | None, BackendContextFailureKind | None, bool]:
    """Return only a validated Context or sanitized failure metadata."""

    client = None
    try:
        client = client_factory()
        context = client.get_context(
            inquiry_id=inquiry_id,
            correlation_id=correlation_id,
        )
        return context, None, False
    except BackendContextClientError as exc:
        return None, exc.kind, exc.retryable
    except Exception:
        return None, BackendContextFailureKind.EXECUTION_ERROR, False
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
