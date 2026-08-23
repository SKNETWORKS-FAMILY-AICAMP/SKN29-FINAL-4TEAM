"""Assigned-consultant inquiry read serializers."""

from rest_framework import serializers

from apps.inquiries.models import Inquiry
from apps.inquiries.api.serializers.inquiry_response import (
    AllowedActionSerializer,
)


PRIORITY_CHOICES = ("LOW", "NORMAL", "HIGH", "URGENT")
SORT_CHOICES = (
    "UPDATED_DESC",
    "UPDATED_ASC",
    "WAITING_DESC",
    "RISK_DESC",
)


class ConsultantInquiryListQuerySerializer(serializers.Serializer):
    """Validate the confirmed server-side list filters."""

    q = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=200,
        trim_whitespace=True,
    )
    status = serializers.ListField(
        child=serializers.ChoiceField(choices=Inquiry.Status.values),
        required=False,
        allow_empty=False,
    )
    risk_level = serializers.ListField(
        child=serializers.ChoiceField(choices=Inquiry.RiskLevel.values),
        required=False,
        allow_empty=False,
    )
    priority = serializers.ListField(
        child=serializers.ChoiceField(choices=PRIORITY_CHOICES),
        required=False,
        allow_empty=False,
    )
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)
    sort = serializers.ChoiceField(
        choices=SORT_CHOICES,
        default="UPDATED_DESC",
    )
    page = serializers.IntegerField(default=1, min_value=1)
    size = serializers.IntegerField(default=20, min_value=1, max_value=100)

    def validate(self, attrs):
        from_date = attrs.get("from_date")
        to_date = attrs.get("to_date")
        if from_date is not None and to_date is not None and from_date > to_date:
            raise serializers.ValidationError(
                {"to": ["to must be on or after from."]}
            )
        return attrs


class ConsultantInquiryListItemSerializer(serializers.Serializer):
    inquiry_id = serializers.UUIDField()
    inquiry_code = serializers.CharField(max_length=48)
    status = serializers.ChoiceField(choices=Inquiry.Status.values)
    state_version = serializers.IntegerField(min_value=1)
    risk_level = serializers.ChoiceField(choices=Inquiry.RiskLevel.values)
    priority = serializers.ChoiceField(choices=PRIORITY_CHOICES)
    symptom_summary = serializers.CharField(max_length=1000)
    customer_display_name_masked = serializers.CharField(max_length=80)
    product_model = serializers.CharField(max_length=120)
    current_assignee_type = serializers.ChoiceField(choices=("CONSULTANT",))
    received_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    waiting_seconds = serializers.IntegerField(min_value=0)
    allowed_actions = AllowedActionSerializer(many=True)


class ConsultantInquiryPageInfoSerializer(serializers.Serializer):
    page = serializers.IntegerField(min_value=1)
    size = serializers.IntegerField(min_value=1, max_value=100)
    total = serializers.IntegerField(min_value=0)


class ConsultantInquiryListDataSerializer(serializers.Serializer):
    items = ConsultantInquiryListItemSerializer(many=True)
    page_info = ConsultantInquiryPageInfoSerializer()
    status_counts = serializers.DictField(
        child=serializers.IntegerField(min_value=0)
    )


class UnassignedConsultationQueueItemSerializer(
    ConsultantInquiryListItemSerializer
):
    """Minimal queue projection; full unassigned detail remains concealed."""

    current_assignee_type = serializers.ChoiceField(choices=("NONE",))


class UnassignedConsultationQueueDataSerializer(serializers.Serializer):
    items = UnassignedConsultationQueueItemSerializer(many=True)
    page_info = ConsultantInquiryPageInfoSerializer()


class ConsultantInquiryHeaderSerializer(serializers.Serializer):
    inquiry_id = serializers.UUIDField()
    inquiry_code = serializers.CharField(max_length=48)
    status = serializers.ChoiceField(choices=Inquiry.Status.values)
    state_version = serializers.IntegerField(min_value=1)
    risk_level = serializers.ChoiceField(choices=Inquiry.RiskLevel.values)
    priority = serializers.ChoiceField(choices=PRIORITY_CHOICES)
    received_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class ConsultantCustomerSerializer(serializers.Serializer):
    is_synthetic = serializers.BooleanField()
    display_name = serializers.CharField(max_length=80)
    phone = serializers.CharField(max_length=32)


class ConsultantProductAndCareSerializer(serializers.Serializer):
    product_model = serializers.CharField(max_length=120)
    subscription_status = serializers.CharField(max_length=40)
    management_type = serializers.CharField(max_length=40)
    recent_care_date = serializers.DateField(allow_null=True)


class ConsultantQuestionAnswerSerializer(serializers.Serializer):
    question_code = serializers.CharField(max_length=80)
    answer = serializers.CharField(max_length=2000)


class ConsultantSymptomQuestionnaireSerializer(serializers.Serializer):
    symptom_summary = serializers.CharField(max_length=2000)
    answers = ConsultantQuestionAnswerSerializer(many=True)


class ConsultantGuidanceActionsSerializer(serializers.Serializer):
    usage_guidance_status = serializers.ChoiceField(
        choices=Inquiry.UsageGuidanceStatus.values,
        allow_null=True,
    )
    usage_guidance_message = serializers.CharField(
        max_length=2000,
        allow_null=True,
    )
    restricted_functions = serializers.ListField(
        child=serializers.CharField(max_length=120)
    )


class ConsultantStateHistorySerializer(serializers.Serializer):
    from_status = serializers.CharField(max_length=64, allow_null=True)
    to_status = serializers.CharField(max_length=64)
    changed_at = serializers.DateTimeField()
    actor_role = serializers.ChoiceField(
        choices=(
            "CUSTOMER",
            "CONSULTANT",
            "TECHNICIAN",
            "OPERATOR",
            "SYSTEM",
        )
    )


class ConsultantWorkflowSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Inquiry.Status.values)
    state_version = serializers.IntegerField(min_value=1)
    allowed_actions = AllowedActionSerializer(many=True)


class ConsultantSectionErrorSerializer(serializers.Serializer):
    section = serializers.ChoiceField(
        choices=("product_and_care", "consultation", "visit")
    )
    code = serializers.CharField(max_length=80)
    message = serializers.CharField(max_length=300)


class ConsultantConsultationSummarySerializer(serializers.Serializer):
    ai_draft_summary = serializers.CharField(
        max_length=4000,
        allow_null=True,
    )
    edited_summary = serializers.CharField(
        max_length=4000,
        allow_null=True,
    )
    confirmed_summary = serializers.CharField(
        max_length=4000,
        allow_null=True,
    )
    confirmed_at = serializers.DateTimeField(allow_null=True)


class ConsultantConsultationRecordSerializer(serializers.Serializer):
    consultation_id = serializers.UUIDField()
    result_code = serializers.ChoiceField(
        choices=(
            "PENDING",
            "COMPLETED_NO_VISIT",
            "VISIT_REQUIRED",
            "REOPENED_FOLLOWUP",
        )
    )
    summary = ConsultantConsultationSummarySerializer()
    consultation_note = serializers.CharField(
        max_length=8000,
        allow_null=True,
    )
    additional_check = serializers.CharField(
        max_length=4000,
        allow_null=True,
    )
    customer_guidance = serializers.CharField(
        max_length=2000,
        allow_null=True,
    )
    usage_guidance_status = serializers.ChoiceField(
        choices=Inquiry.UsageGuidanceStatus.values,
        allow_null=True,
    )


class ConsultantVisitScheduleSerializer(serializers.Serializer):
    preferred_date = serializers.DateField(allow_null=True)
    confirmed_date = serializers.DateField(allow_null=True)
    schedule_status = serializers.ChoiceField(
        choices=(
            "ASSIGNING",
            "SCHEDULING",
            "CONFIRMED",
            "IN_PROGRESS",
            "COMPLETED",
            "FOLLOW_UP_REQUIRED",
            "CANCELLED",
        )
    )
    synthetic_technician_id = serializers.UUIDField(allow_null=True)


class ConsultantSyntheticTechnicianSerializer(serializers.Serializer):
    is_synthetic = serializers.BooleanField()
    technician_id = serializers.UUIDField()
    display_name = serializers.CharField(max_length=80)
    phone = serializers.CharField(max_length=32)


class ConsultantVisitDetailSerializer(serializers.Serializer):
    visit_id = serializers.UUIDField()
    inquiry_id = serializers.UUIDField()
    schedule = ConsultantVisitScheduleSerializer()
    technician = ConsultantSyntheticTechnicianSerializer(allow_null=True)


class ConsultantInquiryDetailDataSerializer(serializers.Serializer):
    inquiry = ConsultantInquiryHeaderSerializer()
    customer = ConsultantCustomerSerializer()
    product_and_care = ConsultantProductAndCareSerializer(allow_null=True)
    symptom_and_questionnaire = ConsultantSymptomQuestionnaireSerializer()
    guidance_and_actions = ConsultantGuidanceActionsSerializer()
    consultation = ConsultantConsultationRecordSerializer(allow_null=True)
    visit = ConsultantVisitDetailSerializer(allow_null=True)
    state_history = ConsultantStateHistorySerializer(many=True)
    workflow = ConsultantWorkflowSerializer()
    section_errors = ConsultantSectionErrorSerializer(many=True)
