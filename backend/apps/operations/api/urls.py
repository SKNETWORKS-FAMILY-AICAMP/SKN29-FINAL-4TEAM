"""Operations dashboard API routes."""

from django.urls import path

from apps.operations.api.views import ConsultantDashboardView


urlpatterns = [
    path(
        "consultant/dashboard",
        ConsultantDashboardView.as_view(),
        name="consultant-dashboard",
    ),
]
