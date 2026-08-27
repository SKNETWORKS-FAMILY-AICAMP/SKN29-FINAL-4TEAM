"""Minimal CUSTOMER-owned inquiry read serializers."""

from rest_framework import serializers

from apps.consultations.models import Consultation
from apps.inquiries.api.serializers.inquiry_response import (
    AllowedActionSerializer,
)
from apps.inquiries.models import Inquiry


class CustomerInquiryProductSerializer(serializers.Serializer):
    model_code = serializers.CharField(max_length=60)


class CustomerInquirySnapshotSerializer(serializers.Serializer):
    inquiry_id = serializers.UUIDField()
    status_code = serializers.ChoiceField(choices=Inquiry.Status.values)
    state_version = serializers.IntegerField(min_value=1)
    subscription_id = serializers.UUIDField()
    product = CustomerInquiryProductSerializer()
    allowed_actions = AllowedActionSerializer(many=True)
    updated_at = serializers.DateTimeField()
    system_notice = serializers.CharField(
        max_length=200,
        allow_null=True,
        required=False,
    )


class CustomerActiveInquirySerializer(serializers.Serializer):
    active_inquiry = CustomerInquirySnapshotSerializer(allow_null=True)


class CustomerInquiryGuidanceSerializer(serializers.Serializer):
    """Public CUSTOMER projection of the latest trusted AI guidance."""

    inquiry_id = serializers.UUIDField()
    inquiry_code = serializers.CharField(max_length=50)
    status_code = serializers.ChoiceField(choices=Inquiry.Status.values)
    state_version = serializers.IntegerField(min_value=1)
    symptom_summary = serializers.CharField(max_length=2000)
    risk_level = serializers.ChoiceField(choices=Inquiry.RiskLevel.values)
    usage_guidance_status = serializers.ChoiceField(
        choices=Inquiry.UsageGuidanceStatus.values
    )
    usage_guidance_message = serializers.CharField(max_length=3000)
    restricted_functions = serializers.ListField(
        child=serializers.CharField(max_length=1000),
        max_length=20,
    )
    safe_actions = serializers.ListField(
        child=serializers.CharField(max_length=1000),
        max_length=20,
    )
    escalation_conditions = serializers.ListField(
        child=serializers.CharField(max_length=1000),
        max_length=20,
    )
    prohibited_actions = serializers.ListField(
        child=serializers.CharField(max_length=1000),
        max_length=20,
    )
    next_action = serializers.CharField(max_length=1000)
    requires_consultation = serializers.BooleanField()
    evidence = serializers.ListField(
        child=serializers.DictField(),
        max_length=0,
    )
    allowed_actions = AllowedActionSerializer(many=True)


class CustomerInquiryConsultationResultSerializer(serializers.Serializer):
    """Customer-safe projection of a completed consultation result."""

    inquiry_id = serializers.UUIDField()
    status_code = serializers.ChoiceField(choices=Inquiry.Status.values)
    state_version = serializers.IntegerField(min_value=1)
    result_code = serializers.ChoiceField(
        choices=(
            Consultation.Outcome.COMPLETED_NO_VISIT,
            Consultation.Outcome.VISIT_REQUIRED,
            Consultation.Outcome.REOPENED_FOLLOWUP,
        )
    )
    result_display_label = serializers.CharField(max_length=100)
    customer_guidance = serializers.CharField(max_length=2000)
    usage_guidance_status = serializers.ChoiceField(
        choices=Inquiry.UsageGuidanceStatus.values
    )
    usage_guidance_display_label = serializers.CharField(max_length=100)
    completed_at = serializers.DateTimeField()
    allowed_actions = AllowedActionSerializer(many=True)


class CustomerInquiryQuestionOptionSerializer(serializers.Serializer):
    value = serializers.CharField(max_length=200)
    label = serializers.CharField(max_length=200)


class CustomerInquiryQuestionSerializer(serializers.Serializer):
    question_id = serializers.UUIDField()
    question_type = serializers.ChoiceField(
        choices=("FREE_TEXT", "SINGLE_CHOICE")
    )
    prompt = serializers.CharField(max_length=500, allow_blank=True)
    required = serializers.BooleanField()
    options = CustomerInquiryQuestionOptionSerializer(many=True)


class CustomerInquiryQuestionsSerializer(serializers.Serializer):
    inquiry_id = serializers.UUIDField()
    state_version = serializers.IntegerField(min_value=1)
    questions = CustomerInquiryQuestionSerializer(many=True)
