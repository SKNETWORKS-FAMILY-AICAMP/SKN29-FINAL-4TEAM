"""민감한 요청 본문을 제외한 구조화 요청 로그."""

import logging
from time import perf_counter


logger = logging.getLogger("watercare.request")


def _request_route(request) -> str:
    resolver_match = getattr(request, "resolver_match", None)
    route = getattr(resolver_match, "route", None)
    if route:
        return f"/{route.lstrip('/')}"
    return "<unresolved>"


class RequestLoggingMiddleware:
    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request):
        started_at = perf_counter()

        try:
            response = self.get_response(request)
        except Exception:
            logger.exception(
                "request_failed",
                extra={
                    "http_method": request.method,
                    "request_route": _request_route(request),
                    "duration_ms": round(
                        (perf_counter() - started_at) * 1000,
                        2,
                    ),
                },
            )
            raise

        log_method = logger.info
        if response.status_code >= 500:
            log_method = logger.error
        elif response.status_code >= 400:
            log_method = logger.warning

        log_method(
            "request_completed",
            extra={
                "http_method": request.method,
                "request_route": _request_route(request),
                "status_code": response.status_code,
                "duration_ms": round(
                    (perf_counter() - started_at) * 1000,
                    2,
                ),
            },
        )
        return response
