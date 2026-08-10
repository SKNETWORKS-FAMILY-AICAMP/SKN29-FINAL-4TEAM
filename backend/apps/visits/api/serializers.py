"""Visit workflow request serializers."""

from rest_framework import serializers

from apps.consultations.api.serializers import RejectUnknownFieldsMixin
from apps.inquiries.models import Inquiry


VISIT_REVIEW_REASONS = (
    "REMOTE_RESOLUTION_LIMITED",
    "SAFETY_CHECK_REQUIRED",
    "REPEATED_SYMPTOM",
    "PHYSICAL_INSPECTION_REQUIRED",
)
VISIT_NOT_NEEDED_REASONS = (
    "RESOLVED_BY_CONSULTATION",
    "MONITORING_AGREED",
    "CUSTOMER_DECLINED_VISIT",
    "DUPLICATE_VISIT_AVOIDED",
)


class StateTransitionRequestSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    state_version = serializers.IntegerField(min_value=1)


class VisitReasonRequestSerializer(StateTransitionRequestSerializer):
    reason_code = serializers.ChoiceField(choices=())
    reason_detail = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=1000,
        trim_whitespace=True,
    )


class VisitReviewRequestSerializer(VisitReasonRequestSerializer):
    reason_code = serializers.ChoiceField(choices=VISIT_REVIEW_REASONS)


class VisitNotNeededRequestSerializer(VisitReasonRequestSerializer):
    reason_code = serializers.ChoiceField(
        choices=VISIT_NOT_NEEDED_REASONS
    )


class VisitHandoffSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    product_summary = serializers.CharField(max_length=2000)
    symptom_summary = serializers.CharField(max_length=4000)
    action_summary = serializers.CharField(max_length=4000)
    risk_summary = serializers.CharField(max_length=2000)
    priority_check_items = serializers.ListField(
        child=serializers.CharField(max_length=500),
        min_length=1,
        max_length=50,
    )
    consultant_final = serializers.CharField(max_length=4000)


class CreateVisitRequestSerializer(
    StateTransitionRequestSerializer,
):
    visit_reason = serializers.CharField(max_length=1000)
    preferred_date = serializers.DateField(
        required=False,
        allow_null=True,
    )
    usage_guidance_status = serializers.ChoiceField(
        choices=Inquiry.UsageGuidanceStatus.values,
    )
    handoff = VisitHandoffSerializer()


class UpdateVisitScheduleRequestSerializer(
    StateTransitionRequestSerializer,
):
    synthetic_technician_id = serializers.UUIDField()
    preferred_date = serializers.DateField(allow_null=True)
    confirmed_date = serializers.DateField(allow_null=True)

    def validate(self, attrs):
        preferred_date = attrs.get("preferred_date")
        confirmed_date = attrs.get("confirmed_date")
        if (
            preferred_date is not None
            and confirmed_date is not None
            and preferred_date > confirmed_date
        ):
            raise serializers.ValidationError(
                {
                    "confirmed_date": [
                        "확정일은 희망일보다 빠를 수 없습니다."
                    ]
                }
            )
        return attrs


class ConfirmVisitRequestSerializer(StateTransitionRequestSerializer):
    pass
