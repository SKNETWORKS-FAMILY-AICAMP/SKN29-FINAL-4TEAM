"""Customer CARE_PRECHECK controllers."""

from uuid import UUID

from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.inquiries.permissions import IsCustomer
from apps.questionnaires.api.serializers import (
    CarePrecheckSessionSerializer,
    SaveCarePrecheckRequestSerializer,
    StartCarePrecheckRequestSerializer,
    SubmitCarePrecheckRequestSerializer,
)
from apps.questionnaires.services.questionnaire_service import (
    QuestionnaireService,
)
from common.api.request_headers import require_idempotency_key
from common.api.response import success_response


def reject_query_parameters(request) -> None:
    if request.query_params:
        raise ValidationError(
            {
                name: ["This query parameter is not allowed."]
                for name in sorted(request.query_params)
            }
        )


class CarePrecheckCollectionView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request):
        reject_query_parameters(request)
        idempotency_key = require_idempotency_key(request)
        serializer = StartCarePrecheckRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = QuestionnaireService.start(
            actor=request.user,
            subscription_public_id=serializer.validated_data[
                "subscription_id"
            ],
            idempotency_key=idempotency_key,
            correlation_id=UUID(request.correlation_id),
        )
        data = CarePrecheckSessionSerializer(outcome.data).data
        return success_response(data, status_code=outcome.status_code)


class CarePrecheckDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request, questionnaire_session_id: UUID):
        reject_query_parameters(request)
        data = QuestionnaireService.get(
            actor=request.user,
            session_public_id=questionnaire_session_id,
        )
        return success_response(CarePrecheckSessionSerializer(data).data)

    def patch(self, request, questionnaire_session_id: UUID):
        reject_query_parameters(request)
        idempotency_key = require_idempotency_key(request)
        serializer = SaveCarePrecheckRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = QuestionnaireService.save(
            actor=request.user,
            session_public_id=questionnaire_session_id,
            state_version=serializer.validated_data["state_version"],
            answers=serializer.validated_data["answers"],
            idempotency_key=idempotency_key,
            correlation_id=UUID(request.correlation_id),
        )
        data = CarePrecheckSessionSerializer(outcome.data).data
        return success_response(data, status_code=outcome.status_code)


class CarePrecheckSubmitView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, questionnaire_session_id: UUID):
        reject_query_parameters(request)
        idempotency_key = require_idempotency_key(request)
        serializer = SubmitCarePrecheckRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = QuestionnaireService.submit(
            actor=request.user,
            session_public_id=questionnaire_session_id,
            state_version=serializer.validated_data["state_version"],
            answers=serializer.validated_data["answers"],
            idempotency_key=idempotency_key,
            correlation_id=UUID(request.correlation_id),
        )
        data = CarePrecheckSessionSerializer(outcome.data).data
        return success_response(data, status_code=outcome.status_code)
