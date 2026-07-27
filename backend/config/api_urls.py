"""/api/v1 하위 도메인 API 통합 URL."""

from django.urls import include, path


urlpatterns = [
    path("", include("apps.accounts.api.urls")),
]
