"""Validated request and public result contracts for CANCEL_INQUIRY."""

from rest_framework import serializers

from apps.inquiries.models import Inquiry


class CancelInquirySerializer(serializers.Serializer):
    state_version = serializers.IntegerField(min_value=1)
    reason_code = serializers.ChoiceField(
        choices=Inquiry.CancellationReason.values,
    )
    reason_detail = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        trim_whitespace=True,
        max_length=500,
    )


class CancelInquiryResponseSerializer(serializers.Serializer):
    inquiry_id = serializers.UUIDField()
    state = serializers.ChoiceField(
        choices=[Inquiry.Status.CANCELLED],
    )
    state_version = serializers.IntegerField(min_value=2)
    idempotent_replay = serializers.BooleanField()
