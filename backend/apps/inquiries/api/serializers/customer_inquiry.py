"""Minimal CUSTOMER-owned inquiry read serializers."""

from rest_framework import serializers

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
