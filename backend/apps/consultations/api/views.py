"""Consultation workflow controllers."""

from uuid import UUID

from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.consultations.api.serializers import (
    CompleteConsultationRequestSerializer,
    SaveConsultationRequestSerializer,
    StateTransitionRequestSerializer,
)
from apps.consultations.permissions import IsConsultant
from apps.consultations.services.consultation_service import (
    ConsultationService,
)
from common.api.request_headers import require_idempotency_key
from common.api.response import success_response


class ConsultationActionView(APIView):
    """Base view that keeps service writes and response materialization atomic."""

    permission_classes = [IsAuthenticated, IsConsultant]
    serializer_class = StateTransitionRequestSerializer
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


class StartConsultationView(ConsultationActionView):
    service_method = ConsultationService.start

    def post(self, request, inquiry_id: UUID):
        return self.execute(request, inquiry_id)


class UpdateConsultationSummaryView(ConsultationActionView):
    serializer_class = SaveConsultationRequestSerializer
    service_method = ConsultationService.save_summary

    def patch(self, request, inquiry_id: UUID):
        return self.execute(request, inquiry_id)


class ConfirmConsultationSummaryView(ConsultationActionView):
    service_method = ConsultationService.confirm_summary

    def post(self, request, inquiry_id: UUID):
        return self.execute(request, inquiry_id)


class CompleteConsultationView(ConsultationActionView):
    serializer_class = CompleteConsultationRequestSerializer
    service_method = ConsultationService.complete

    def post(self, request, inquiry_id: UUID):
        return self.execute(request, inquiry_id)
