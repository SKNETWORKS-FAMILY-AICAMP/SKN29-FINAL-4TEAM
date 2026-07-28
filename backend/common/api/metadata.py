"""공통 응답의 요청 추적 Metadata."""

from common.middleware.request_context import get_correlation_id as get_context_id


def get_correlation_id(request=None) -> str | None:
    if request is not None:
        return getattr(request, "correlation_id", None)
    return get_context_id()


def build_response_metadata(
    correlation_id: str | None = None,
) -> dict[str, str] | None:
    resolved_id = correlation_id or get_correlation_id()
    if not resolved_id:
        return None
    return {"correlation_id": resolved_id}
