"""T-018 list query and public response serializers."""

from rest_framework import serializers


class SubscriptionListQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(default=1, min_value=1)
    size = serializers.IntegerField(default=20, min_value=1, max_value=100)


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


class SubscriptionListDataSerializer(serializers.Serializer):
    items = SubscriptionSummarySerializer(many=True)
    page = serializers.IntegerField(min_value=1)
    size = serializers.IntegerField(min_value=1, max_value=100)
    total = serializers.IntegerField(min_value=0)
