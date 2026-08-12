"""T-019 owner-only care history controllers."""

from uuid import UUID

from django.db import transaction
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.care.api.serializers import (
    CareHistoryCreateSerializer,
    CareHistoryItemSerializer,
    CareHistoryListDataSerializer,
    CareHistoryListQuerySerializer,
    CareHistoryMutationResultSerializer,
)
from apps.care.services.care_history_service import CareHistoryService
from apps.subscriptions.permissions import IsCustomer
from common.api.response import success_response


def reject_unknown_query_parameters(request, allowed: set[str]) -> None:
    unknown = sorted(set(request.query_params) - allowed)
    if unknown:
        raise ValidationError(
            {
                name: ["This query parameter is not allowed."]
                for name in unknown
            }
        )


def require_idempotency_key(request) -> str:
    raw_value = request.headers.get("Idempotency-Key")
    value = raw_value.strip() if isinstance(raw_value, str) else ""
    if not value:
        raise ValidationError(
            {"Idempotency-Key": ["이 헤더는 필수입니다."]}
        )
    if len(value) > 128:
        raise ValidationError(
            {"Idempotency-Key": ["128자 이하여야 합니다."]}
        )
    return value


class MyCareRecordListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request, subscription_id: UUID):
        reject_unknown_query_parameters(request, {"page", "size"})
        query = CareHistoryListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = CareHistoryService.list_for_customer(
            actor=request.user,
            subscription_public_id=subscription_id,
            **query.validated_data,
        )
        return success_response(CareHistoryListDataSerializer(data).data)

    def post(self, request, subscription_id: UUID):
        serializer = CareHistoryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            outcome = CareHistoryService.create_for_customer(
                actor=request.user,
                subscription_public_id=subscription_id,
                validated_data=serializer.validated_data,
                idempotency_key=require_idempotency_key(request),
            )
            data = CareHistoryMutationResultSerializer(outcome.data).data
            return success_response(data, status_code=outcome.status_code)


class MyCareRecordDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(
        self,
        request,
        subscription_id: UUID,
        care_record_id: UUID,
    ):
        reject_unknown_query_parameters(request, set())
        data = CareHistoryService.detail_for_customer(
            actor=request.user,
            subscription_public_id=subscription_id,
            care_record_public_id=care_record_id,
        )
        return success_response(CareHistoryItemSerializer(data).data)
