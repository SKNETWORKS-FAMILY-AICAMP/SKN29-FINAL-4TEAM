"""요청·응답·로그를 연결하는 ``correlation_id`` 전파."""

import uuid

from common.middleware.request_context import (
    reset_correlation_id,
    set_correlation_id,
)


CORRELATION_ID_HEADER = "X-Correlation-ID"


def resolve_correlation_id(request) -> str:
    """유효한 외부 UUID는 이어 쓰고, 그 외에는 새 UUID를 발급한다."""

    candidate = request.headers.get(CORRELATION_ID_HEADER)
    if candidate:
        try:
            return str(uuid.UUID(candidate))
        except (ValueError, AttributeError, TypeError):
            pass
    return str(uuid.uuid4())


class CorrelationIdMiddleware:
    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request):
        correlation_id = resolve_correlation_id(request)
        request.correlation_id = correlation_id
        token = set_correlation_id(correlation_id)

        try:
            response = self.get_response(request)
            response[CORRELATION_ID_HEADER] = correlation_id
            return response
        finally:
            reset_correlation_id(token)
