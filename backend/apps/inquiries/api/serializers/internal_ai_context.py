"""Private Backend-to-AI inquiry Context response contract."""

from rest_framework import serializers


class InternalAIPreviousAnswerSerializer(serializers.Serializer):
    question_id = serializers.CharField(max_length=100)
    answer_text = serializers.CharField(max_length=1000)


class InternalAIProductFeaturesSerializer(serializers.Serializer):
    model_family = serializers.CharField(
        max_length=100,
        allow_null=True,
    )
    water_modes = serializers.ListField(
        child=serializers.CharField(max_length=100),
        max_length=20,
    )
    supported_functions = serializers.ListField(
        child=serializers.CharField(max_length=100),
        max_length=40,
    )


class InternalAIProductContextSerializer(serializers.Serializer):
    subscription_id = serializers.UUIDField()
    subscription_status_code = serializers.CharField(max_length=40)
    management_type_code = serializers.CharField(max_length=40)
    product_model_id = serializers.UUIDField()
    model_code = serializers.CharField(max_length=60)
    model_name = serializers.CharField(max_length=150)
    product_family = serializers.ChoiceField(
        choices=(
            "DIRECT_WATER_PURIFIER",
            "ICE_WATER_PURIFIER",
            "UNKNOWN",
        )
    )
    generation_code = serializers.CharField(
        max_length=40,
        allow_null=True,
    )
    manufacturer = serializers.CharField(max_length=100)
    features = InternalAIProductFeaturesSerializer()


class InternalAIInquiryPayloadSerializer(serializers.Serializer):
    customer_query = serializers.CharField(max_length=4000)
    symptom_type = serializers.CharField(
        max_length=200,
        allow_null=True,
    )
    selected_symptoms = serializers.ListField(
        child=serializers.CharField(max_length=200),
        max_length=30,
    )
    previous_answers = InternalAIPreviousAnswerSerializer(many=True)


class InternalAIInquiryContextDataSerializer(serializers.Serializer):
    inquiry_id = serializers.UUIDField()
    inquiry_code = serializers.CharField(max_length=50)
    status_code = serializers.CharField(max_length=40)
    state_version = serializers.IntegerField(min_value=1)
    correlation_id = serializers.UUIDField()
    product_context = InternalAIProductContextSerializer()
    inquiry_context = InternalAIInquiryPayloadSerializer()
