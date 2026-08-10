"""Inquiry API routes."""

from django.urls import path

from apps.inquiries.api.views import (
    CancelInquiryView,
    ConsultantInquiryDetailView,
    CreateInquiryView,
    CustomerInquiryQuestionsView,
    CustomerInquirySnapshotView,
    SubmitSymptomView,
    SubmitFollowUpAnswersView,
)


urlpatterns = [
    path(
        "me/inquiries/<uuid:inquiry_id>",
        CustomerInquirySnapshotView.as_view(),
        name="customer-inquiry-snapshot",
    ),
    path(
        "me/inquiries/<uuid:inquiry_id>/questions",
        CustomerInquiryQuestionsView.as_view(),
        name="customer-inquiry-questions",
    ),
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
    path(
        "inquiries/<uuid:inquiry_id>/answers",
        SubmitFollowUpAnswersView.as_view(),
        name="inquiry-submit-followup-answers",
    ),
]
