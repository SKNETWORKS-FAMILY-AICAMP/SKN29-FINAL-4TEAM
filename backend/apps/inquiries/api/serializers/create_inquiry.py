"""Validated body contract for START_INQUIRY."""

from rest_framework import serializers

from apps.inquiries.models import Inquiry


class CreateInquirySerializer(serializers.Serializer):
    """Accept public identifiers only and normalize user-provided text."""

    subscription_id = serializers.UUIDField()
    channel_code = serializers.ChoiceField(
        choices=Inquiry.Channel.values,
    )
    raw_text = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        max_length=5000,
    )
    representative_symptom_code = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=False,
        trim_whitespace=True,
        max_length=40,
    )
    questionnaire_session_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
