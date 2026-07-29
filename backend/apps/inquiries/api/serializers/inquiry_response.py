"""Public START_INQUIRY result serializers."""

from rest_framework import serializers

from apps.inquiries.models import Inquiry


class AllowedActionSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()
    operation_id = serializers.CharField()
    style = serializers.CharField()
    requires_confirmation = serializers.BooleanField()
    confirmation_message = serializers.CharField(
        allow_null=True,
        required=False,
    )


class InquiryResponseSerializer(serializers.Serializer):
    """Expose UUID and business code, never the internal database key."""

    inquiry_id = serializers.UUIDField()
    inquiry_code = serializers.CharField()
    status_code = serializers.ChoiceField(
        choices=Inquiry.Status.values,
    )
    state_version = serializers.IntegerField(min_value=1)
    idempotent_replay = serializers.BooleanField()
    allowed_actions = AllowedActionSerializer(many=True)
