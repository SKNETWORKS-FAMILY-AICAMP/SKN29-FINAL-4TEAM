"""Visit workflow controllers."""

from uuid import UUID

from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.visits.api.serializers import (
    ConfirmVisitRequestSerializer,
    CreateVisitRequestSerializer,
    UpdateVisitScheduleRequestSerializer,
    VisitNotNeededRequestSerializer,
    VisitReviewRequestSerializer,
)
from apps.visits.permissions import IsConsultant
from apps.visits.services.visit_service import VisitService
from common.api.request_headers import require_idempotency_key
from common.api.response import success_response


class InquiryVisitActionView(APIView):
    permission_classes = [IsAuthenticated, IsConsultant]
    serializer_class = VisitReviewRequestSerializer
    service_method = None

    def execute(self, request, inquiry_id: UUID):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = require_idempotency_key(request)
        with transaction.atomic():
            outcome = self.service_method(
                actor=request.user,
                inquiry_public_id=inquiry_id,
                validated_data=serializer.validated_data,
                idempotency_key=idempotency_key,
                correlation_id=UUID(request.correlation_id),
            )
            response_data = dict(outcome.data)
        return success_response(
            response_data,
            status_code=outcome.status_code,
        )


class RequestVisitReviewView(InquiryVisitActionView):
    service_method = VisitService.request_review

    def post(self, request, inquiry_id: UUID):
        return self.execute(request, inquiry_id)


class CreateVisitRequestView(InquiryVisitActionView):
    serializer_class = CreateVisitRequestSerializer
    service_method = VisitService.create_request

    def post(self, request, inquiry_id: UUID):
        return self.execute(request, inquiry_id)


class MarkVisitNotNeededView(InquiryVisitActionView):
    serializer_class = VisitNotNeededRequestSerializer
    service_method = VisitService.mark_not_needed

    def post(self, request, inquiry_id: UUID):
        return self.execute(request, inquiry_id)


class VisitActionView(APIView):
    permission_classes = [IsAuthenticated, IsConsultant]
    serializer_class = ConfirmVisitRequestSerializer
    service_method = None

    def execute(self, request, visit_id: UUID):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = require_idempotency_key(request)
        with transaction.atomic():
            outcome = self.service_method(
                actor=request.user,
                visit_public_id=visit_id,
                validated_data=serializer.validated_data,
                idempotency_key=idempotency_key,
                correlation_id=UUID(request.correlation_id),
            )
            response_data = dict(outcome.data)
        return success_response(
            response_data,
            status_code=outcome.status_code,
        )


class UpdateVisitScheduleView(VisitActionView):
    serializer_class = UpdateVisitScheduleRequestSerializer
    service_method = VisitService.update_schedule

    def patch(self, request, visit_id: UUID):
        return self.execute(request, visit_id)


class ConfirmVisitView(VisitActionView):
    service_method = VisitService.confirm

    def post(self, request, visit_id: UUID):
        return self.execute(request, visit_id)
