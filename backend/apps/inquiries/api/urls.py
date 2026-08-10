"""Inquiry API routes."""

from django.urls import path

from apps.inquiries.api.views import (
    CancelInquiryView,
    ConsultantInquiryDetailView,
    CreateInquiryView,
    SubmitSymptomView,
)


urlpatterns = [
    path(
        "inquiries",
        CreateInquiryView.as_view(),
        name="inquiry-create",
    ),
    path(
        "inquiries/<uuid:inquiry_id>",
        ConsultantInquiryDetailView.as_view(),
        name="consultant-inquiry-detail",
    ),
    path(
        "inquiries/<uuid:inquiry_id>/cancel",
        CancelInquiryView.as_view(),
        name="inquiry-cancel",
    ),
    path(
        "inquiries/<uuid:inquiry_id>/submit",
        SubmitSymptomView.as_view(),
        name="inquiry-submit",
    ),
]
