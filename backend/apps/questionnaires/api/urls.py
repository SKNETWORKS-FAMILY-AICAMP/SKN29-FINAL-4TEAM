"""CARE_PRECHECK customer routes."""

from django.urls import path

from apps.questionnaires.api.views import (
    CarePrecheckCollectionView,
    CarePrecheckDetailView,
    CarePrecheckSubmitView,
)


urlpatterns = [
    path(
        "me/questionnaire-sessions",
        CarePrecheckCollectionView.as_view(),
        name="care-precheck-start",
    ),
    path(
        "me/questionnaire-sessions/<uuid:questionnaire_session_id>",
        CarePrecheckDetailView.as_view(),
        name="care-precheck-detail",
    ),
    path(
        "me/questionnaire-sessions/"
        "<uuid:questionnaire_session_id>/submit",
        CarePrecheckSubmitView.as_view(),
        name="care-precheck-submit",
    ),
]
