"""Visit review, creation and date-only schedule API routes."""

from django.urls import path

from apps.visits.api.views import (
    ConfirmVisitView,
    CreateVisitRequestView,
    MarkVisitNotNeededView,
    RequestVisitReviewView,
    UpdateVisitScheduleView,
)


urlpatterns = [
    path(
        "inquiries/<uuid:inquiry_id>/visit-review",
        RequestVisitReviewView.as_view(),
        name="visit-review",
    ),
    path(
        "inquiries/<uuid:inquiry_id>/visits",
        CreateVisitRequestView.as_view(),
        name="visit-create",
    ),
    path(
        "inquiries/<uuid:inquiry_id>/visit-not-needed",
        MarkVisitNotNeededView.as_view(),
        name="visit-not-needed",
    ),
    path(
        "visits/<uuid:visit_id>/schedule",
        UpdateVisitScheduleView.as_view(),
        name="visit-schedule-update",
    ),
    path(
        "visits/<uuid:visit_id>/confirm",
        ConfirmVisitView.as_view(),
        name="visit-confirm",
    ),
]
