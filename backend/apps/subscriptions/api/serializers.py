"""T-018 read/write request and public response serializers."""

from collections.abc import Mapping

from rest_framework import serializers
from django.utils import timezone

from apps.subscriptions.models import CustomerSubscription


class RejectUnknownFieldsMixin:
    """Reject request keys that DRF would otherwise silently ignore."""

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


class SubscriptionListQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(default=1, min_value=1)
    size = serializers.IntegerField(default=20, min_value=1, max_value=100)


class SubscriptionCreateSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    model_code = serializers.CharField(max_length=60)
    started_on = serializers.DateField()
    management_type_code = serializers.ChoiceField(
        choices=CustomerSubscription.ManagementType.values
    )
    last_care_on = serializers.DateField(
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        today = timezone.localdate()
        if attrs["started_on"] > today:
            raise serializers.ValidationError(
                {"started_on": ["미래 날짜는 사용할 수 없습니다."]}
            )
        last_care_on = attrs.get("last_care_on")
        if last_care_on is not None:
            if last_care_on > today:
                raise serializers.ValidationError(
                    {"last_care_on": ["미래 날짜는 사용할 수 없습니다."]}
                )
            if last_care_on < attrs["started_on"]:
                raise serializers.ValidationError(
                    {
                        "last_care_on": [
                            "사용 시작일보다 빠를 수 없습니다."
                        ]
                    }
                )
        return attrs


class SubscriptionUpdateSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    started_on = serializers.DateField(required=False)
    management_type_code = serializers.ChoiceField(
        required=False,
        choices=CustomerSubscription.ManagementType.values,
    )
    last_care_on = serializers.DateField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                {"non_field_errors": ["수정할 필드가 필요합니다."]}
            )
        today = timezone.localdate()
        for field in ("started_on", "last_care_on"):
            value = attrs.get(field)
            if value is not None and value > today:
                raise serializers.ValidationError(
                    {field: ["미래 날짜는 사용할 수 없습니다."]}
                )
        if (
            "started_on" in attrs
            and "last_care_on" in attrs
            and attrs["last_care_on"] < attrs["started_on"]
        ):
            raise serializers.ValidationError(
                {
                    "last_care_on": [
                        "사용 시작일보다 빠를 수 없습니다."
                    ]
                }
            )
        return attrs


class ProductSummarySerializer(serializers.Serializer):
    product_model_id = serializers.UUIDField()
    model_code = serializers.CharField()
    model_name = serializers.CharField()
    generation_code = serializers.CharField(allow_null=True)
    manufacturer = serializers.CharField()


class SubscriptionSummarySerializer(serializers.Serializer):
    subscription_id = serializers.UUIDField()
    status_code = serializers.ChoiceField(choices=("ACTIVE",))
    management_type_code = serializers.ChoiceField(
        choices=("SELF_MANAGED", "VISIT_CARE")
    )
    started_on = serializers.DateField()
    last_care_on = serializers.DateField(allow_null=True)
    next_care_on = serializers.DateField(allow_null=True)
    product = ProductSummarySerializer()


class SubscriptionDetailSerializer(SubscriptionSummarySerializer):
    ended_on = serializers.DateField(allow_null=True)


class SubscriptionMutationResultSerializer(SubscriptionDetailSerializer):
    idempotent_replay = serializers.BooleanField()


class SubscriptionListDataSerializer(serializers.Serializer):
    items = SubscriptionSummarySerializer(many=True)
    page = serializers.IntegerField(min_value=1)
    size = serializers.IntegerField(min_value=1, max_value=100)
    total = serializers.IntegerField(min_value=0)
