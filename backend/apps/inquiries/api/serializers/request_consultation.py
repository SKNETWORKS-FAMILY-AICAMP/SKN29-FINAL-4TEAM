"""Validated public contract for CUSTOMER REQUEST_CONSULTATION."""

from collections.abc import Mapping

from rest_framework import serializers

from apps.inquiries.api.serializers.inquiry_response import (
    AllowedActionSerializer,
)
from apps.inquiries.models import Inquiry


class RequestConsultationSerializer(serializers.Serializer):
    """Accept only the optimistic-lock version declared by OpenAPI."""

    state_version = serializers.IntegerField(min_value=1)

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unexpected = sorted(set(data) - set(self.fields))
            if unexpected:
                raise serializers.ValidationError(
                    {
                        field: ["This field is not allowed."]
                        for field in unexpected
                    }
                )
        return super().to_internal_value(data)


class RequestConsultationResponseSerializer(serializers.Serializer):
    """Materialize the confirmed StateTransitionResult projection."""

    message = serializers.CharField(min_length=1, max_length=300)
    inquiry_id = serializers.UUIDField()
    status = serializers.ChoiceField(
        choices=[Inquiry.Status.CONSULTATION_REQUIRED]
    )
    state_version = serializers.IntegerField(min_value=1)
    allowed_actions = AllowedActionSerializer(many=True)
    idempotent_replay = serializers.BooleanField()
    resource = serializers.JSONField(allow_null=True)

    def validate_resource(self, value):
        if value is not None:
            raise serializers.ValidationError(
                "REQUEST_CONSULTATION does not expose an internal resource."
            )
        return value
