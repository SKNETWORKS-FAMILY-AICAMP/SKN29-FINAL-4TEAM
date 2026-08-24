"""Operations dashboard API routes."""

from django.urls import path

from apps.operations.api.views import (
    ConsultantDashboardNoticeDetailView,
    ConsultantDashboardView,
)


urlpatterns = [
    path(
        "consultant/dashboard",
        ConsultantDashboardView.as_view(),
        name="consultant-dashboard",
    ),
    path(
        "consultant/notices/<uuid:notice_id>",
        ConsultantDashboardNoticeDetailView.as_view(),
        name="consultant-dashboard-notice-detail",
    ),
]
