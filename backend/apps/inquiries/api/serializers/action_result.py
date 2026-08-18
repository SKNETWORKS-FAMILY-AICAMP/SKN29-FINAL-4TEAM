"""T-022 customer action-result request and response serializers."""

from rest_framework import serializers


class ActionResultRequestSerializer(serializers.Serializer):
    guidance_item_id = serializers.UUIDField()
    result_code = serializers.CharField(max_length=40)
    result_text = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        trim_whitespace=False,
    )
    customer_comment = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        trim_whitespace=False,
    )
    performed_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )
    state_version = serializers.IntegerField(min_value=1)

    def to_internal_value(self, data):
        if hasattr(data, "keys"):
            unknown = sorted(set(data) - set(self.fields))
            if unknown:
                raise serializers.ValidationError(
                    {
                        field: ["This field is not allowed."]
                        for field in unknown
                    }
                )
        return super().to_internal_value(data)

    def validate_result_code(self, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("This field may not be blank.")
        return normalized


class ActionResultResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    inquiry_id = serializers.UUIDField()
    guidance_item_id = serializers.UUIDField()
    attempt_no = serializers.IntegerField(min_value=1)
    result_code = serializers.CharField(max_length=40)
    result_text = serializers.CharField(allow_null=True, allow_blank=True)
    performed_at = serializers.DateTimeField(allow_null=True)
    customer_comment = serializers.CharField(
        allow_null=True,
        allow_blank=True,
    )
    submitted_by = serializers.UUIDField()
    state_version = serializers.IntegerField(min_value=1)
    idempotent_replay = serializers.BooleanField()
    created_at = serializers.DateTimeField()
