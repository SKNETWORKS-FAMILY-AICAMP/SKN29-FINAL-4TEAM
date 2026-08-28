"""Health와 API 최상위 URL 연결."""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny

from common.api.health import health
from common.api.not_found import api_not_found
from apps.accounts.admin_site import waterbridge_admin_site


urlpatterns = [
    path("health", health, name="health"),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=[AllowAny]),
        name="api-schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(
            url_name="api-schema",
            permission_classes=[AllowAny],
        ),
        name="api-docs",
    ),
    path("admin/", waterbridge_admin_site.urls),
    path("api/v1/", include("config.api_urls")),
    path("api/v1/", api_not_found, name="api-root-not-found"),
    path(
        "api/v1/<path:unmatched_path>",
        api_not_found,
        name="api-not-found",
    ),
]
