"""Customer inquiry creation and workflow-action controllers."""

from uuid import UUID

from django.db import transaction
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.inquiries.api.serializers import (
    CancelInquiryResponseSerializer,
    CancelInquirySerializer,
    CreateInquirySerializer,
    InquiryResponseSerializer,
    SubmitSymptomResponseSerializer,
    SymptomSubmissionSerializer,
)
from apps.inquiries.permissions import IsCustomer
from apps.inquiries.services.inquiry_service import InquiryService
from apps.inquiries.services.inquiry_transition_service import (
    InquiryTransitionService,
)
from common.api.response import success_response


def require_idempotency_key(request) -> str:
    raw_value = request.headers.get("Idempotency-Key")
    value = raw_value.strip() if isinstance(raw_value, str) else ""
    if not value:
        raise ValidationError(
            {
                "Idempotency-Key": [
                    "이 헤더는 필수입니다.",
                ]
            }
        )
    if len(value) > 128:
        raise ValidationError(
            {
                "Idempotency-Key": [
                    "128자 이하여야 합니다.",
                ]
            }
        )
    return value


class CreateInquiryView(APIView):
    """Execute START_INQUIRY for the authenticated subscription owner."""

    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request):
        idempotency_key = require_idempotency_key(request)
        serializer = CreateInquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        outcome = InquiryService.create(
            actor=request.user,
            validated_data=serializer.validated_data,
            idempotency_key=idempotency_key,
            correlation_id=UUID(request.correlation_id),
        )
        response_data = InquiryResponseSerializer(outcome.data).data
        return success_response(
            response_data,
            status_code=outcome.status_code,
        )


class CancelInquiryView(APIView):
    """Execute CANCEL_INQUIRY for the authenticated inquiry owner."""

    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, inquiry_id: UUID):
        idempotency_key = require_idempotency_key(request)
        serializer = CancelInquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        outcome = InquiryService.cancel(
            actor=request.user,
            inquiry_public_id=inquiry_id,
            validated_data=serializer.validated_data,
            idempotency_key=idempotency_key,
            correlation_id=UUID(request.correlation_id),
        )
        response_data = CancelInquiryResponseSerializer(
            outcome.data
        ).data
        return success_response(
            response_data,
            status_code=outcome.status_code,
        )


class SubmitSymptomView(APIView):
    """Execute SUBMIT_SYMPTOM for the authenticated inquiry owner."""

    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, inquiry_id: UUID):
        idempotency_key = require_idempotency_key(request)
        serializer = SymptomSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Keep response contract materialization inside the outer transaction.
        # If serialization fails, all transition writes roll back together.
        with transaction.atomic():
            outcome = InquiryTransitionService.submit_symptom(
                actor=request.user,
                inquiry_public_id=inquiry_id,
                validated_data=serializer.validated_data,
                idempotency_key=idempotency_key,
                correlation_id=UUID(request.correlation_id),
            )
            response_data = SubmitSymptomResponseSerializer(
                outcome.data
            ).data
        return success_response(
            response_data,
            status_code=outcome.status_code,
        )
