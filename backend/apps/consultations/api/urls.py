"""Consultation workflow API routes."""

from django.urls import path

from apps.consultations.api.views import (
    CompleteConsultationView,
    ConfirmConsultationSummaryView,
    StartConsultationView,
    UpdateConsultationSummaryView,
)


urlpatterns = [
    path(
        "inquiries/<uuid:inquiry_id>/start-consultation",
        StartConsultationView.as_view(),
        name="consultation-start",
    ),
    path(
        "inquiries/<uuid:inquiry_id>/consultation-summary",
        UpdateConsultationSummaryView.as_view(),
        name="consultation-summary-update",
    ),
    path(
        "inquiries/<uuid:inquiry_id>/consultation-summary/confirm",
        ConfirmConsultationSummaryView.as_view(),
        name="consultation-summary-confirm",
    ),
    path(
        "inquiries/<uuid:inquiry_id>/complete-consultation",
        CompleteConsultationView.as_view(),
        name="consultation-complete",
    ),
]
