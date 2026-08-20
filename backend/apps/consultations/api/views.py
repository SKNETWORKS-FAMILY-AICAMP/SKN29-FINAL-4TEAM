"""Consultation workflow controllers."""

from uuid import UUID

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.consultations.api.handoff_serializers import (
    ConsultationHandoffRequestSerializer,
)
from apps.consultations.api.serializers import (
    CompleteConsultationRequestSerializer,
    SaveConsultationRequestSerializer,
    StateTransitionRequestSerializer,
)
from apps.consultations.permissions import HasValidAIHandoffToken, IsConsultant
from apps.consultations.services.consultation_handoff_service import (
    ConsultationHandoffService,
)
from apps.consultations.services.consultation_service import (
    ConsultationService,
)
from common.api.request_headers import require_idempotency_key
from common.api.response import success_response


@extend_schema(exclude=True)
class InternalAIConsultationHandoffView(APIView):
    """Receive one sanitized handoff from the trusted AI service."""

    authentication_classes = []
    permission_classes = [HasValidAIHandoffToken]

    def post(self, request, inquiry_id: UUID):
        serializer = ConsultationHandoffRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["inquiry_id"] != inquiry_id:
            raise ValidationError(
                {"inquiry_id": ["Path와 Payload의 Inquiry가 일치해야 합니다."]}
            )

        idempotency_key = require_idempotency_key(request)
        if idempotency_key != data["ai_request_id"]:
            raise ValidationError(
                {
                    "Idempotency-Key": [
                        "AI Request ID와 동일한 값이어야 합니다."
                    ]
                }
            )

        raw_correlation = request.headers.get("X-Correlation-ID", "")
        try:
            correlation_id = UUID(raw_correlation)
        except (TypeError, ValueError, AttributeError):
            raise ValidationError(
                {"X-Correlation-ID": ["UUID 형식의 필수 헤더입니다."]}
            ) from None
        if correlation_id != data["correlation_id"]:
            raise ValidationError(
                {
                    "X-Correlation-ID": [
                        "Payload의 Correlation ID와 일치해야 합니다."
                    ]
                }
            )

        outcome = ConsultationHandoffService.persist(
            inquiry_public_id=inquiry_id,
            validated_data=data,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        return success_response(outcome.data, status_code=outcome.status_code)


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
