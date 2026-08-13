"""T-019 care history public routes."""

from django.urls import path

from apps.care.api.views import (
    MyCareRecordDetailView,
    MyCareRecordListCreateView,
)


urlpatterns = [
    path(
        "me/subscriptions/<uuid:subscription_id>/care-records",
        MyCareRecordListCreateView.as_view(),
        name="my-care-record-list-create",
    ),
    path(
        "me/subscriptions/<uuid:subscription_id>/care-records/"
        "<uuid:care_record_id>",
        MyCareRecordDetailView.as_view(),
        name="my-care-record-detail",
    ),
]
