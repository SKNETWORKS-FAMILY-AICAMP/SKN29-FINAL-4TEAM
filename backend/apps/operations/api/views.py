"""Read-only consultant operations dashboard controller."""

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.inquiries.permissions import IsConsultant
from apps.operations.api.serializers import (
    ConsultantDashboardDataSerializer,
    DashboardNoticeSerializer,
)
from apps.operations.services import ConsultantDashboardService
from common.api.response import success_response


class ConsultantDashboardView(APIView):
    """Return only assigned synthetic inquiries and synthetic reference data."""

    permission_classes = [IsAuthenticated, IsConsultant]

    @extend_schema(
        responses=ConsultantDashboardDataSerializer,
        operation_id="consultant_dashboard_read",
    )
    def get(self, request):
        if request.query_params:
            raise ValidationError(
                {
                    name: ["This query parameter is not allowed."]
                    for name in sorted(request.query_params)
                }
            )
        data = ConsultantDashboardService.snapshot(actor=request.user)
        return success_response(ConsultantDashboardDataSerializer(data).data)


class ConsultantDashboardNoticeDetailView(APIView):
    """Return one published synthetic Dashboard notice."""

    permission_classes = [IsAuthenticated, IsConsultant]

    @extend_schema(
        responses=DashboardNoticeSerializer,
        operation_id="consultant_dashboard_notice_read",
    )
    def get(self, request, notice_id):
        if request.query_params:
            raise ValidationError(
                {
                    name: ["This query parameter is not allowed."]
                    for name in sorted(request.query_params)
                }
            )
        data = ConsultantDashboardService.notice_detail(
            notice_public_id=notice_id
        )
        return success_response(DashboardNoticeSerializer(data).data)
