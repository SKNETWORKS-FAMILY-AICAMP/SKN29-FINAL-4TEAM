"""Consultant operations dashboard response serializers."""

from rest_framework import serializers

from apps.inquiries.models import Inquiry
from apps.operations.models import DashboardNotice


class DashboardSummarySerializer(serializers.Serializer):
    total = serializers.IntegerField(min_value=0)
    new = serializers.IntegerField(min_value=0)
    in_progress = serializers.IntegerField(min_value=0)
    completed = serializers.IntegerField(min_value=0)


class DashboardNoticeSerializer(serializers.Serializer):
    notice_id = serializers.UUIDField()
    notice_code = serializers.CharField(max_length=50)
    category_code = serializers.ChoiceField(
        choices=DashboardNotice.Category.values
    )
    category = serializers.CharField(max_length=20)
    title = serializers.CharField(max_length=160)
    content = serializers.CharField()
    department = serializers.CharField(max_length=100)
    published_on = serializers.DateField()


class DashboardConsultantSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    name = serializers.CharField(max_length=100)
    department = serializers.CharField(max_length=100)
    position = serializers.CharField(max_length=80)
    extension = serializers.CharField(max_length=30)
    email = serializers.EmailField()


class DashboardTechnicianSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    name = serializers.CharField(max_length=100)
    branch = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=30)
    email = serializers.EmailField()


class DashboardInquirySerializer(serializers.Serializer):
    inquiry_id = serializers.UUIDField()
    inquiry_code = serializers.CharField(max_length=50)
    bucket = serializers.ChoiceField(
        choices=("NEW", "IN_PROGRESS", "COMPLETED")
    )
    status = serializers.ChoiceField(choices=Inquiry.Status.values)
    risk_level = serializers.ChoiceField(choices=Inquiry.RiskLevel.values)
    priority = serializers.ChoiceField(choices=Inquiry.Priority.values)
    title = serializers.CharField(max_length=160)
    detail = serializers.CharField(max_length=4000)
    contact = serializers.CharField(max_length=30)
    address = serializers.CharField(max_length=520)
    customer_name = serializers.CharField(max_length=100)
    customer_code = serializers.CharField(max_length=40)
    product_name = serializers.CharField(max_length=150)
    product_code = serializers.CharField(max_length=60)
    warranty_status = serializers.ChoiceField(
        choices=("IN_WARRANTY", "EXPIRED", "NOT_REGISTERED")
    )
    warranty_ends_on = serializers.DateField(allow_null=True)
    warranty_label = serializers.CharField(max_length=80)
    previous_visit_count = serializers.IntegerField(min_value=0)
    received_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class ConsultantDashboardDataSerializer(serializers.Serializer):
    data_classification = serializers.ChoiceField(choices=("synthetic",))
    generated_at = serializers.DateTimeField()
    summary = DashboardSummarySerializer()
    notices = DashboardNoticeSerializer(many=True)
    consultants = DashboardConsultantSerializer(many=True)
    technicians = DashboardTechnicianSerializer(many=True)
    inquiries = DashboardInquirySerializer(many=True)
