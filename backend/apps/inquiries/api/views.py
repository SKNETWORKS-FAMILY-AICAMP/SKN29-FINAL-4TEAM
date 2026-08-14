"""Customer inquiry creation and workflow-action controllers."""

from uuid import UUID

from django.db import transaction
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.inquiries.api.serializers import (
    CancelInquiryResponseSerializer,
    CancelInquirySerializer,
    ConsultantInquiryDetailDataSerializer,
    ConsultantInquiryListDataSerializer,
    ConsultantInquiryListQuerySerializer,
    ConsultantCustomerSubscriptionSearchResultSerializer,
    ConsultantCustomerSubscriptionSearchSerializer,
    CreateInquirySerializer,
    CustomerInquiryGuidanceSerializer,
    CustomerInquiryQuestionsSerializer,
    CustomerInquirySnapshotSerializer,
    InquiryResponseSerializer,
    RegisterConsultantPhoneInquiryResultSerializer,
    RegisterConsultantPhoneInquirySerializer,
    RequestConsultationResponseSerializer,
    RequestConsultationSerializer,
    SubmitFollowUpAnswersResponseSerializer,
    SubmitFollowUpAnswersSerializer,
    SubmitSymptomResponseSerializer,
    SymptomSubmissionSerializer,
)
from apps.inquiries.permissions import (
    CanAttemptInquiryCancel,
    IsConsultant,
    IsCustomer,
)
from apps.inquiries.services.consultant_inquiry_service import (
    ConsultantInquiryService,
)
from apps.inquiries.services.consultant_phone_inquiry_service import (
    ConsultantPhoneInquiryService,
)
from apps.inquiries.services.customer_inquiry_service import (
    CustomerInquiryService,
)
from apps.inquiries.services.consultation_request_service import (
    ConsultationRequestService,
)
from apps.inquiries.services.inquiry_service import InquiryService
from apps.inquiries.services.followup_answer_service import (
    FollowUpAnswerService,
)
from apps.inquiries.services.inquiry_transition_service import (
    InquiryTransitionService,
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


def require_correlation_id(request) -> UUID:
    """Require the caller-provided trace UUID for external write actions."""

    raw_value = request.headers.get("X-Correlation-ID")
    value = raw_value.strip() if isinstance(raw_value, str) else ""
    if not isinstance(raw_value, str) or raw_value != value:
        raise ValidationError(
            {
                "X-Correlation-ID": [
                    "공백 없는 UUID 형식의 필수 헤더입니다."
                ]
            }
        )
    try:
        return UUID(value)
    except (TypeError, ValueError, AttributeError):
        raise ValidationError(
            {
                "X-Correlation-ID": [
                    "유효한 UUID 형식의 필수 헤더입니다."
                ]
            }
        ) from None


class CreateInquiryView(APIView):
    """List assigned work or execute customer START_INQUIRY."""

    def get_permissions(self):
        permission_classes = (
            [IsAuthenticated, IsConsultant]
            if self.request.method in {"GET", "HEAD"}
            else [IsAuthenticated, IsCustomer]
        )
        return [permission() for permission in permission_classes]

    def get(self, request):
        reject_unknown_query_parameters(
            request,
            {
                "q",
                "status",
                "risk_level",
                "priority",
                "from",
                "to",
                "sort",
                "page",
                "size",
            },
        )
        raw_query = {}
        for name in ("q", "sort", "page", "size"):
            if name in request.query_params:
                raw_query[name] = request.query_params.get(name)
        for name in ("status", "risk_level", "priority"):
            if name in request.query_params:
                raw_query[name] = request.query_params.getlist(name)
        if "from" in request.query_params:
            raw_query["from_date"] = request.query_params.get("from")
        if "to" in request.query_params:
            raw_query["to_date"] = request.query_params.get("to")

        query = ConsultantInquiryListQuerySerializer(data=raw_query)
        query.is_valid(raise_exception=True)
        values = query.validated_data
        data = ConsultantInquiryService.list_for_consultant(
            actor=request.user,
            q=values.get("q") or None,
            statuses=values.get("status", []),
            risk_levels=values.get("risk_level", []),
            priorities=values.get("priority", []),
            from_date=values.get("from_date"),
            to_date=values.get("to_date"),
            sort=values["sort"],
            page=values["page"],
            size=values["size"],
        )
        return success_response(ConsultantInquiryListDataSerializer(data).data)

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


class ConsultantInquiryDetailView(APIView):
    """Return one assigned synthetic inquiry without existence leaks."""

    permission_classes = [IsAuthenticated, IsConsultant]

    def get(self, request, inquiry_id: UUID):
        data = ConsultantInquiryService.detail_for_consultant(
            actor=request.user,
            inquiry_public_id=inquiry_id,
        )
        return success_response(
            ConsultantInquiryDetailDataSerializer(data).data
        )


class ConsultantCustomerSubscriptionSearchView(APIView):
    """Search masked synthetic-customer active subscription candidates."""

    permission_classes = [IsAuthenticated, IsConsultant]

    def post(self, request):
        reject_unknown_query_parameters(request, set())
        require_correlation_id(request)
        serializer = ConsultantCustomerSubscriptionSearchSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        data = ConsultantPhoneInquiryService.search(
            query=serializer.validated_data["query"],
            limit=serializer.validated_data["limit"],
        )
        return success_response(
            ConsultantCustomerSubscriptionSearchResultSerializer(data).data
        )


class RegisterConsultantPhoneInquiryView(APIView):
    """Create one consultant-owned PHONE inquiry from an approved candidate."""

    permission_classes = [IsAuthenticated, IsConsultant]

    def post(self, request):
        reject_unknown_query_parameters(request, set())
        idempotency_key = require_idempotency_key(request)
        correlation_id = require_correlation_id(request)
        serializer = RegisterConsultantPhoneInquirySerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            outcome = ConsultantPhoneInquiryService.register(
                actor=request.user,
                validated_data=serializer.validated_data,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
            response_data = RegisterConsultantPhoneInquiryResultSerializer(
                outcome.data
            ).data
        return success_response(
            response_data,
            status_code=outcome.status_code,
        )


class CustomerInquirySnapshotView(APIView):
    """Return the authenticated CUSTOMER's minimal inquiry Snapshot."""

    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request, inquiry_id: UUID):
        reject_unknown_query_parameters(request, set())
        data = CustomerInquiryService.snapshot_for_customer(
            actor=request.user,
            inquiry_public_id=inquiry_id,
        )
        return success_response(CustomerInquirySnapshotSerializer(data).data)


class CustomerInquiryQuestionsView(APIView):
    """Return question metadata for one CUSTOMER-owned inquiry."""

    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request, inquiry_id: UUID):
        reject_unknown_query_parameters(request, set())
        data = CustomerInquiryService.questions_for_customer(
            actor=request.user,
            inquiry_public_id=inquiry_id,
        )
        return success_response(CustomerInquiryQuestionsSerializer(data).data)


class CustomerInquiryGuidanceView(APIView):
    """Return the authenticated CUSTOMER's latest trusted AI Guidance."""

    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request, inquiry_id: UUID):
        reject_unknown_query_parameters(request, set())
        data = CustomerInquiryService.guidance_for_customer(
            actor=request.user,
            inquiry_public_id=inquiry_id,
        )
        return success_response(CustomerInquiryGuidanceSerializer(data).data)


class CancelInquiryView(APIView):
    """Execute CANCEL_INQUIRY within the approved actor object scope."""

    permission_classes = [IsAuthenticated, CanAttemptInquiryCancel]

    def post(self, request, inquiry_id: UUID):
        idempotency_key = require_idempotency_key(request)
        serializer = CancelInquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
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


class SubmitFollowUpAnswersView(APIView):
    """Execute SUBMIT_ANSWERS for the authenticated inquiry owner."""

    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, inquiry_id: UUID):
        idempotency_key = require_idempotency_key(request)
        correlation_id = require_correlation_id(request)
        serializer = SubmitFollowUpAnswersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            outcome = FollowUpAnswerService.submit(
                actor=request.user,
                inquiry_public_id=inquiry_id,
                validated_data=serializer.validated_data,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
            response_data = SubmitFollowUpAnswersResponseSerializer(
                outcome.data
            ).data
        return success_response(
            response_data,
            status_code=outcome.status_code,
        )


class RequestConsultationView(APIView):
    """Execute REQUEST_CONSULTATION for the authenticated owner."""

    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, inquiry_id: UUID):
        reject_unknown_query_parameters(request, set())
        idempotency_key = require_idempotency_key(request)
        correlation_id = require_correlation_id(request)
        serializer = RequestConsultationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            outcome = ConsultationRequestService.request(
                actor=request.user,
                inquiry_public_id=inquiry_id,
                validated_data=serializer.validated_data,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
            response_data = RequestConsultationResponseSerializer(
                outcome.data
            ).data
        return success_response(
            response_data,
            status_code=outcome.status_code,
        )
