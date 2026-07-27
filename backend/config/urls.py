"""Health와 API 최상위 URL 연결."""

from django.urls import include, path

from common.api.health import health
from common.api.not_found import api_not_found


urlpatterns = [
    path("health", health, name="health"),
    path("api/v1/", include("config.api_urls")),
    path("api/v1/", api_not_found, name="api-root-not-found"),
    path(
        "api/v1/<path:unmatched_path>",
        api_not_found,
        name="api-not-found",
    ),
]
