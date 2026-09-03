"""Privacy-minimized consultant HumanReview API serializers."""

from rest_framework import serializers

from apps.inquiries.models import HumanReview, Inquiry


CUSTOMER_GUIDANCE_MESSAGE_MAX_LENGTH = 3000
CUSTOMER_GUIDANCE_ACTION_MAX_LENGTH = 1000


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
    inquiry_status = serializers.ChoiceField(choices=Inquiry.Status.values)
    inquiry_state_version = serializers.IntegerField(min_value=1)
    model_code = serializers.CharField(max_length=100)
    status = serializers.ChoiceField(choices=HumanReview.Status.values)
    decision = serializers.ChoiceField(
        choices=HumanReview.Decision.values,
        allow_null=True,
    )
    review_state_version = serializers.IntegerField(min_value=1)
    source_inquiry_state_version = serializers.IntegerField(min_value=1)
    reason_code = serializers.CharField(max_length=80)
    decision_reason_code = serializers.CharField(
        max_length=80,
        allow_null=True,
    )
    consultation_origin = serializers.ChoiceField(
        choices=HumanReview.ConsultationOrigin.values
    )
    consultation_origin_reason = serializers.ChoiceField(
        choices=HumanReview.ConsultationOriginReason.values
    )
    original_requires_consultation = serializers.BooleanField()
    effective_requires_consultation = serializers.BooleanField()
    consultation_disposition = serializers.ChoiceField(
        choices=HumanReview.ConsultationDisposition.values,
        allow_null=True,
    )
    consultation_reason_code = serializers.ChoiceField(
        choices=HumanReview.ConsultationChangeReason.values,
        allow_null=True,
    )
    can_resolve_consultation = serializers.BooleanField()
    verified_evidence_ids = serializers.ListField(
        child=serializers.UUIDField(),
    )
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
    # A MODIFY decision is published through CustomerInquiryGuidance.
    # Reject text that the customer projection cannot represent instead of
    # accepting the decision and returning AI_GUIDANCE_NOT_READY on GET.
    instruction_text = serializers.CharField(
        max_length=CUSTOMER_GUIDANCE_ACTION_MAX_LENGTH
    )
    caution_text = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=2000,
    )
    requires_confirmation = serializers.BooleanField(default=True)


class ModifiedGuidanceSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    summary_text = serializers.CharField(
        max_length=CUSTOMER_GUIDANCE_MESSAGE_MAX_LENGTH
    )
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
    consultation_disposition = serializers.ChoiceField(
        choices=HumanReview.ConsultationDisposition.values,
        default=HumanReview.ConsultationDisposition.PRESERVE,
    )
    consultation_reason_code = serializers.ChoiceField(
        choices=HumanReview.ConsultationChangeReason.values,
        required=False,
    )
    consultation_evidence_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=False,
        max_length=20,
    )

    def validate(self, attrs):
        decision = attrs["decision"]
        modified = attrs.get("modified_guidance")
        reason = attrs.get("reason_code")
        consultation_disposition = attrs["consultation_disposition"]
        consultation_reason = attrs.get("consultation_reason_code")
        evidence_ids = attrs.get("consultation_evidence_ids", [])
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
        if len(set(evidence_ids)) != len(evidence_ids):
            raise serializers.ValidationError(
                {"consultation_evidence_ids": ["Evidence ID는 중복될 수 없습니다."]}
            )
        if decision == HumanReview.Decision.REJECT:
            if (
                consultation_disposition
                != HumanReview.ConsultationDisposition.PRESERVE
                or consultation_reason is not None
                or evidence_ids
            ):
                raise serializers.ValidationError(
                    {
                        "consultation_disposition": [
                            "REJECT의 상담 전환은 Backend 정책으로 처리됩니다."
                        ]
                    }
                )
            return attrs
        if (
            consultation_disposition
            == HumanReview.ConsultationDisposition.PRESERVE
        ):
            if consultation_reason is not None or evidence_ids:
                raise serializers.ValidationError(
                    {
                        "consultation_disposition": [
                            "PRESERVE에는 상담 변경 사유나 Evidence가 없습니다."
                        ]
                    }
                )
        elif (
            consultation_disposition
            == HumanReview.ConsultationDisposition.REQUIRE
        ):
            if consultation_reason not in {
                HumanReview.ConsultationChangeReason.CONSULTANT_SAFETY_ESCALATION,
                HumanReview.ConsultationChangeReason.PRODUCT_FUNCTION_UNCERTAIN,
                HumanReview.ConsultationChangeReason.CUSTOMER_CONTEXT_INCOMPLETE,
            }:
                raise serializers.ValidationError(
                    {
                        "consultation_reason_code": [
                            "상담 필요 상향에 허용된 사유 코드가 필요합니다."
                        ]
                    }
                )
            if evidence_ids:
                raise serializers.ValidationError(
                    {
                        "consultation_evidence_ids": [
                            "상담 필요 상향에는 해소 Evidence를 제출하지 않습니다."
                        ]
                    }
                )
        else:
            if consultation_reason not in {
                HumanReview.ConsultationChangeReason.PRODUCT_CAPABILITY_VERIFIED,
                HumanReview.ConsultationChangeReason.HARNESS_SCOPE_VERIFIED,
            }:
                raise serializers.ValidationError(
                    {
                        "consultation_reason_code": [
                            "비-Safety 해소에 허용된 사유 코드가 필요합니다."
                        ]
                    }
                )
            if not evidence_ids:
                raise serializers.ValidationError(
                    {
                        "consultation_evidence_ids": [
                            "상담 해소에는 검증 Evidence가 필요합니다."
                        ]
                    }
                )
        return attrs
