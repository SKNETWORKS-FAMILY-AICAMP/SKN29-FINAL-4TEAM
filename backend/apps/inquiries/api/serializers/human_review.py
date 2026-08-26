"""Privacy-minimized consultant HumanReview API serializers."""

from rest_framework import serializers

from apps.inquiries.models import HumanReview


class HumanReviewGuidanceItemSerializer(serializers.Serializer):
    step_no = serializers.IntegerField(min_value=1)
    instruction_text = serializers.CharField(max_length=2000)
    caution_text = serializers.CharField(
        max_length=2000,
        allow_blank=True,
        allow_null=True,
    )
    requires_confirmation = serializers.BooleanField()


class HumanReviewGuidanceSerializer(serializers.Serializer):
    guidance_id = serializers.UUIDField()
    guidance_version = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=200)
    summary_text = serializers.CharField(max_length=4000)
    safety_notice = serializers.CharField(
        max_length=4000,
        allow_blank=True,
        allow_null=True,
    )
    requires_consultation = serializers.BooleanField()
    items = HumanReviewGuidanceItemSerializer(many=True)


class HumanReviewDataSerializer(serializers.Serializer):
    review_id = serializers.UUIDField()
    inquiry_id = serializers.UUIDField()
    model_code = serializers.CharField(max_length=100)
    status = serializers.ChoiceField(choices=HumanReview.Status.values)
    decision = serializers.ChoiceField(
        choices=HumanReview.Decision.values,
        allow_null=True,
    )
    review_state_version = serializers.IntegerField(min_value=1)
    source_inquiry_state_version = serializers.IntegerField(min_value=1)
    reason_code = serializers.CharField(max_length=80)
    proposed_guidance = HumanReviewGuidanceSerializer()
    published_guidance = HumanReviewGuidanceSerializer(allow_null=True)
    allowed_actions = serializers.ListField(
        child=serializers.ChoiceField(choices=("DECIDE_HUMAN_REVIEW",))
    )
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    idempotent_replay = serializers.BooleanField(required=False)


class HumanReviewListDataSerializer(serializers.Serializer):
    items = HumanReviewDataSerializer(many=True)


class ModifiedGuidanceItemSerializer(serializers.Serializer):
    instruction_text = serializers.CharField(max_length=2000)
    caution_text = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=2000,
    )
    requires_confirmation = serializers.BooleanField(default=True)


class ModifiedGuidanceSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    summary_text = serializers.CharField(max_length=4000)
    safety_notice = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=4000,
    )
    items = ModifiedGuidanceItemSerializer(
        many=True,
        allow_empty=False,
        max_length=20,
    )


class HumanReviewDecisionRequestSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=HumanReview.Decision.values)
    review_state_version = serializers.IntegerField(min_value=1)
    reason_code = serializers.RegexField(
        regex=r"^[A-Z][A-Z0-9_]{2,79}$",
        required=False,
    )
    modified_guidance = ModifiedGuidanceSerializer(required=False)

    def validate(self, attrs):
        decision = attrs["decision"]
        modified = attrs.get("modified_guidance")
        reason = attrs.get("reason_code")
        if decision == HumanReview.Decision.MODIFY and modified is None:
            raise serializers.ValidationError(
                {"modified_guidance": ["MODIFY 결정에는 수정본이 필요합니다."]}
            )
        if decision != HumanReview.Decision.MODIFY and modified is not None:
            raise serializers.ValidationError(
                {"modified_guidance": ["MODIFY 결정에서만 사용할 수 있습니다."]}
            )
        if decision in {
            HumanReview.Decision.MODIFY,
            HumanReview.Decision.REJECT,
        } and reason is None:
            raise serializers.ValidationError(
                {"reason_code": ["MODIFY 또는 REJECT 결정에는 사유 코드가 필요합니다."]}
            )
        return attrs
