"""승인된 개발·배포 Origin만 허용하는 최소 CORS Middleware."""

from django.conf import settings
from django.http import HttpResponse
from django.utils.cache import patch_vary_headers


ALLOWED_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
ALLOWED_HEADERS = (
    "Authorization, Content-Type, X-Correlation-ID, Idempotency-Key"
)
EXPOSED_HEADERS = "X-Correlation-ID"


class CorsAllowlistMiddleware:
    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin")
        allowed_origins = set(
            getattr(settings, "CORS_ALLOWED_ORIGINS", ())
        )
        is_allowed = bool(origin and origin in allowed_origins)
        is_preflight = bool(
            request.method == "OPTIONS"
            and request.headers.get("Access-Control-Request-Method")
        )

        if is_preflight and is_allowed:
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        if is_allowed:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Methods"] = ALLOWED_METHODS
            response["Access-Control-Allow-Headers"] = ALLOWED_HEADERS
            response["Access-Control-Expose-Headers"] = EXPOSED_HEADERS
            patch_vary_headers(response, ("Origin",))
        return response
