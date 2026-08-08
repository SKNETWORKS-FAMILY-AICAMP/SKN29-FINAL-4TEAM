"""T-018 owner-only subscription read routes."""

from django.urls import path

from apps.subscriptions.api.views import (
    MySubscriptionDetailView,
    MySubscriptionListView,
)


urlpatterns = [
    path(
        "me/subscriptions",
        MySubscriptionListView.as_view(),
        name="my-subscription-list",
    ),
    path(
        "me/subscriptions/<uuid:subscription_id>",
        MySubscriptionDetailView.as_view(),
        name="my-subscription-detail",
    ),
]
