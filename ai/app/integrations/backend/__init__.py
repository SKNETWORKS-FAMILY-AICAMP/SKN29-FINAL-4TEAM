"""Backend read-only integration adapters."""

from .context_client import (
    BackendContextClient,
    BackendContextClientError,
    BackendContextFailureKind,
    BackendInquiryContext,
    BackendInquiryPayload,
    BackendPreviousAnswer,
    BackendProductContext,
    BackendProductFeatures,
)

__all__ = [
    "BackendContextClient",
    "BackendContextClientError",
    "BackendContextFailureKind",
    "BackendInquiryContext",
    "BackendInquiryPayload",
    "BackendPreviousAnswer",
    "BackendProductContext",
    "BackendProductFeatures",
]
