"""/api/v1 하위 도메인 API 통합 URL."""

from django.urls import include, path


urlpatterns = [
    path("", include("apps.accounts.api.urls")),
    path("", include("apps.subscriptions.api.urls")),
    path("", include("apps.care.api.urls")),
    path("", include("apps.inquiries.api.urls")),
    path("", include("apps.consultations.api.urls")),
    path("", include("apps.visits.api.urls")),
    path("", include("apps.operations.api.urls")),
]
