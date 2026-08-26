"""Customer inquiry creation and workflow-action controllers."""

from uuid import UUID

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.inquiries.api.serializers import (
    ActionResultRequestSerializer,
    ActionResultResponseSerializer,
    CancelInquiryResponseSerializer,
    CancelInquirySerializer,
    ConsultantInquiryDetailDataSerializer,
    ConsultantInquiryListDataSerializer,
    ConsultantInquiryListQuerySerializer,
    UnassignedConsultationQueueDataSerializer,
    ConsultantCustomerSubscriptionSearchResultSerializer,
    ConsultantCustomerSubscriptionSearchSerializer,
    CreateInquirySerializer,
    CustomerActiveInquirySerializer,
    CustomerInquiryGuidanceSerializer,
    CustomerInquiryQuestionsSerializer,
    CustomerInquirySnapshotSerializer,
    InquiryResponseSerializer,
    InternalAIInquiryContextDataSerializer,
    HumanReviewDataSerializer,
    HumanReviewDecisionRequestSerializer,
    HumanReviewListDataSerializer,
    FinalizeInquiryRequestSerializer,
    RegisterConsultantPhoneInquiryResultSerializer,
    RegisterConsultantPhoneInquirySerializer,
    ReportUnresolvedRequestSerializer,
    RequestConsultationResponseSerializer,
    RequestConsultationSerializer,
    ResolutionFeedbackRequestSerializer,
    ResolutionTransitionResponseSerializer,
    StateVersionRequestSerializer,
    SubmitFollowUpAnswersResponseSerializer,
    SubmitFollowUpAnswersSerializer,
    SubmitSymptomResponseSerializer,
    SymptomSubmissionSerializer,
)
from apps.inquiries.permissions import (
    CanAttemptInquiryCancel,
    IsCompletionStaff,
    IsConsultant,
    IsCustomer,
)
from apps.inquiries.services.consultant_inquiry_service import (
    ConsultantInquiryService,
)
from apps.inquiries.services.consultation_claim_service import (
    ConsultationClaimService,
)
from apps.inquiries.services.action_result_service import ActionResultService
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
from apps.inquiries.services.internal_ai_context_service import (
    InternalAIContextService,
)
from apps.inquiries.services.human_review_service import HumanReviewService
from apps.inquiries.services.resolution_service import ResolutionService
from common.api.response import success_response
from common.permissions import HasValidAIInternalToken


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


@extend_schema(exclude=True)
class InternalAIInquiryContextView(APIView):
    """Return one privacy-minimized Context to the trusted AI service."""

    authentication_classes = []
    permission_classes = [HasValidAIInternalToken]

    def get(self, request, inquiry_id: UUID):
        reject_unknown_query_parameters(request, set())
        correlation_id = require_correlation_id(request)
        data = InternalAIContextService.retrieve(
            inquiry_public_id=inquiry_id,
            correlation_id=correlation_id,
        )
        return success_response(
            InternalAIInquiryContextDataSerializer(data).data
        )


@extend_schema(exclude=True)
class HumanReviewListView(APIView):
    """Return privacy-minimized pending reviews visible to a consultant."""

    permission_classes = [IsAuthenticated, IsConsultant]

    def get(self, request):
        reject_unknown_query_parameters(request, set())
        data = HumanReviewService.list_pending(actor=request.user)
        return success_response(HumanReviewListDataSerializer(data).data)


@extend_schema(exclude=True)
class HumanReviewDetailView(APIView):
    """Return one visible review without customer raw text or internal errors."""

    permission_classes = [IsAuthenticated, IsConsultant]

    def get(self, request, review_id: UUID):
        reject_unknown_query_parameters(request, set())
        data = HumanReviewService.retrieve(
            actor=request.user,
            review_public_id=review_id,
        )
        return success_response(HumanReviewDataSerializer(data).data)


@extend_schema(exclude=True)
class HumanReviewDecisionView(APIView):
    """Apply one versioned and idempotent consultant review decision."""

    permission_classes = [IsAuthenticated, IsConsultant]

    def post(self, request, review_id: UUID):
        reject_unknown_query_parameters(request, set())
        idempotency_key = require_idempotency_key(request)
        correlation_id = require_correlation_id(request)
        serializer = HumanReviewDecisionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = HumanReviewService.decide(
            actor=request.user,
            review_public_id=review_id,
            validated_data=serializer.validated_data,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        return success_response(
            HumanReviewDataSerializer(outcome.data).data,
            status_code=outcome.status_code,
        )


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


class UnassignedConsultationQueueView(APIView):
    """Return only synthetic, unassigned, waiting consultation work."""

    permission_classes = [IsAuthenticated, IsConsultant]

    def get(self, request):
        reject_unknown_query_parameters(
            request,
            {
                "q",
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
        for name in ("risk_level", "priority"):
            if name in request.query_params:
                raw_query[name] = request.query_params.getlist(name)
        if "from" in request.query_params:
            raw_query["from_date"] = request.query_params.get("from")
        if "to" in request.query_params:
            raw_query["to_date"] = request.query_params.get("to")

        query = ConsultantInquiryListQuerySerializer(data=raw_query)
        query.is_valid(raise_exception=True)
        values = query.validated_data
        data = ConsultantInquiryService.list_unassigned_consultations(
            actor=request.user,
            q=values.get("q") or None,
            risk_levels=values.get("risk_level", []),
            priorities=values.get("priority", []),
            from_date=values.get("from_date"),
            to_date=values.get("to_date"),
            sort=values["sort"],
            page=values["page"],
            size=values["size"],
        )
        return success_response(
            UnassignedConsultationQueueDataSerializer(data).data
        )


class ClaimConsultationView(APIView):
    """Assign one unassigned queue item without starting consultation."""

    permission_classes = [IsAuthenticated, IsConsultant]

    def post(self, request, inquiry_id: UUID):
        reject_unknown_query_parameters(request, set())
        idempotency_key = require_idempotency_key(request)
        correlation_id = require_correlation_id(request)
        serializer = StateVersionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            outcome = ConsultationClaimService.claim(
                actor=request.user,
                inquiry_public_id=inquiry_id,
                validated_data=serializer.validated_data,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
            response_data = ResolutionTransitionResponseSerializer(
                outcome.data
            ).data
        return success_response(
            response_data,
            status_code=outcome.status_code,
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


class CustomerActiveInquiryView(APIView):
    """Return the CUSTOMER's latest non-terminal inquiry, if one exists."""

    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        reject_unknown_query_parameters(request, set())
        data = CustomerInquiryService.latest_active_for_customer(
            actor=request.user,
        )
        return success_response(CustomerActiveInquirySerializer(data).data)


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


class CreateActionResultView(APIView):
    """Append a CUSTOMER-owned guidance action result."""

    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, inquiry_id: UUID):
        reject_unknown_query_parameters(request, set())
        idempotency_key = require_idempotency_key(request)
        serializer = ActionResultRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            outcome = ActionResultService.create(
                actor=request.user,
                inquiry_public_id=inquiry_id,
                validated_data=serializer.validated_data,
                idempotency_key=idempotency_key,
            )
            response_data = ActionResultResponseSerializer(
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


class ResolutionActionView(APIView):
    """Shared strict HTTP boundary for confirmed T-023 actions."""

    request_serializer_class = StateVersionRequestSerializer
    service_method = ""

    def post(self, request, inquiry_id: UUID):
        reject_unknown_query_parameters(request, set())
        idempotency_key = require_idempotency_key(request)
        correlation_id = require_correlation_id(request)
        serializer = self.request_serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            outcome = getattr(
                ResolutionService,
                self.service_method,
            )(
                actor=request.user,
                inquiry_public_id=inquiry_id,
                validated_data=serializer.validated_data,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
            response_data = ResolutionTransitionResponseSerializer(
                outcome.data
            ).data
        return success_response(
            response_data,
            status_code=outcome.status_code,
        )


class SubmitResolutionFeedbackView(ResolutionActionView):
    permission_classes = [IsAuthenticated, IsCustomer]
    request_serializer_class = ResolutionFeedbackRequestSerializer
    service_method = "submit_feedback"


class ReportUnresolvedView(ResolutionActionView):
    permission_classes = [IsAuthenticated, IsCustomer]
    request_serializer_class = ReportUnresolvedRequestSerializer
    service_method = "report_unresolved"


class ResumeConsultationView(ResolutionActionView):
    permission_classes = [IsAuthenticated, IsConsultant]
    service_method = "resume_consultation"


class FinalizeInquiryView(ResolutionActionView):
    permission_classes = [IsAuthenticated, IsCompletionStaff]
    request_serializer_class = FinalizeInquiryRequestSerializer
    service_method = "finalize"
