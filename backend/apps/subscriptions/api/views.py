"""T-018 owner-only list and detail controllers."""

from __future__ import annotations

from uuid import UUID

from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.subscriptions.api.serializers import (
    SubscriptionDetailSerializer,
    SubscriptionListDataSerializer,
    SubscriptionListQuerySerializer,
)
from apps.subscriptions.permissions import IsCustomer
from apps.subscriptions.services.subscription_service import (
    SubscriptionService,
)
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


class MySubscriptionListView(APIView):
    """List active supported subscriptions owned by the CUSTOMER."""

    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        reject_unknown_query_parameters(request, {"page", "size"})
        query = SubscriptionListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = SubscriptionService.list_for_customer(
            actor=request.user,
            **query.validated_data,
        )
        return success_response(SubscriptionListDataSerializer(data).data)


class MySubscriptionDetailView(APIView):
    """Return one active supported subscription without existence leaks."""

    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request, subscription_id: UUID):
        reject_unknown_query_parameters(request, set())
        data = SubscriptionService.detail_for_customer(
            actor=request.user,
            subscription_public_id=subscription_id,
        )
        return success_response(SubscriptionDetailSerializer(data).data)
