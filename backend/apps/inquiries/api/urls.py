"""Inquiry API routes."""

from django.urls import path

from apps.inquiries.api.views import (
    CancelInquiryView,
    CreateInquiryView,
)


urlpatterns = [
    path(
        "inquiries",
        CreateInquiryView.as_view(),
        name="inquiry-create",
    ),
    path(
        "inquiries/<uuid:inquiry_id>/cancel",
        CancelInquiryView.as_view(),
        name="inquiry-cancel",
    ),
]
