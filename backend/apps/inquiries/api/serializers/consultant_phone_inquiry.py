"""Public DTOs for consultant phone inquiry registration."""

from __future__ import annotations

from collections.abc import Mapping
import re

from rest_framework import serializers

from apps.inquiries.api.serializers.inquiry_response import (
    AllowedActionSerializer,
)
from apps.inquiries.models import Inquiry
from apps.subscriptions.models import CustomerSubscription


SYMPTOM_CODE_CHOICES = (
    "NO_WATER",
    "LOW_FLOW",
    "LEAK",
    "ODOR",
    "TASTE",
    "TEMPERATURE_ABNORMAL",
    "NOISE",
    "DISPLAY_ERROR",
    "OTHER",
)
PHONE_LIKE_PATTERN = re.compile(r"^[0-9\s()+-]+$")


class RejectUnknownFieldsMixin:
    """Reject request keys that DRF would otherwise ignore."""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = sorted(set(data) - set(self.fields))
            if unknown:
                raise serializers.ValidationError(
                    {
                        field: ["지원하지 않는 필드입니다."]
                        for field in unknown
                    }
                )
        return super().to_internal_value(data)


class ConsultantCustomerSubscriptionSearchSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    query = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        min_length=2,
        max_length=100,
    )
    limit = serializers.IntegerField(
        required=False,
        default=10,
        min_value=1,
        max_value=20,
    )

    def validate_query(self, value: str) -> str:
        normalized = value.strip()
        if PHONE_LIKE_PATTERN.fullmatch(normalized):
            digits = "".join(
                character
                for character in normalized
                if character.isdigit()
            )
            if len(digits) < 4:
                raise serializers.ValidationError(
                    "연락처 검색은 숫자 4자리 이상이어야 합니다."
                )
        return normalized


class ConsultantCustomerSubscriptionItemSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField()
    customer_display_name = serializers.CharField(max_length=80)
    phone_masked = serializers.CharField(max_length=30, allow_blank=True)
    subscription_id = serializers.UUIDField()
    subscription_status = serializers.ChoiceField(
        choices=[CustomerSubscription.Status.ACTIVE]
    )
    management_type_code = serializers.ChoiceField(
        choices=CustomerSubscription.ManagementType.values
    )
    product_id = serializers.UUIDField()
    product_model_code = serializers.CharField(max_length=60)
    product_name = serializers.CharField(max_length=150)


class ConsultantCustomerSubscriptionSearchResultSerializer(
    serializers.Serializer
):
    items = ConsultantCustomerSubscriptionItemSerializer(many=True)
    returned_count = serializers.IntegerField(min_value=0, max_value=20)


class RegisterConsultantPhoneInquirySerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    subscription_id = serializers.UUIDField()
    raw_text = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        max_length=5000,
    )
    representative_symptom_code = serializers.ChoiceField(
        choices=SYMPTOM_CODE_CHOICES
    )
    priority_code = serializers.ChoiceField(
        choices=Inquiry.Priority.values
    )


class RegisterConsultantPhoneInquiryResultSerializer(serializers.Serializer):
    inquiry_id = serializers.UUIDField()
    inquiry_code = serializers.CharField(max_length=50)
    status_code = serializers.ChoiceField(
        choices=[Inquiry.Status.CONSULTATION_REQUIRED]
    )
    state_version = serializers.IntegerField(min_value=1, max_value=1)
    idempotent_replay = serializers.BooleanField()
    allowed_actions = AllowedActionSerializer(many=True)
