"""ORM reads for synthetic inquiries assigned to one consultant."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db.models import (
    Case,
    CharField,
    Count,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce

from apps.audit.models import AIRun
from apps.care.models import CareRecord
from apps.consultations.models import Consultation
from apps.inquiries.models import (
    Guidance,
    Inquiry,
    InquiryQA,
    SymptomAssessment,
)
from apps.workflow.models import TransitionHistory
from apps.visits.models import Visit


BUSINESS_TIMEZONE = ZoneInfo("Asia/Seoul")


class ConsultantInquiryRepository:
    """Apply assignment and synthetic-data scope before all other filters."""

    @classmethod
    def visible_for_consultant(cls, actor: Any) -> QuerySet[Inquiry]:
        return cls._with_list_projection(
            Inquiry.objects.filter(
                assigned_user=actor,
                assigned_role_code=Inquiry.AssignedRole.CONSULTANT,
                subscription__customer__deleted_at__isnull=True,
                subscription__customer__is_synthetic=True,
                subscription__customer__user__is_synthetic=True,
            )
        )

    @classmethod
    def unassigned_consultation_queue(cls) -> QuerySet[Inquiry]:
        """Return only privacy-safe, currently claimable waiting work."""

        latest_consultation = Consultation.objects.filter(
            inquiry_id=OuterRef("pk")
        ).order_by("-sequence", "-id")
        return cls._with_list_projection(
            Inquiry.objects.filter(
                status_code=Inquiry.Status.CONSULTATION_REQUIRED,
                assigned_user__isnull=True,
                assigned_role_code=Inquiry.AssignedRole.NONE,
                subscription__customer__deleted_at__isnull=True,
                subscription__customer__is_synthetic=True,
                subscription__customer__user__is_synthetic=True,
            )
            .annotate(
                latest_consultation_status=Subquery(
                    latest_consultation.values("status")[:1],
                    output_field=CharField(),
                ),
                latest_consultation_consultant_id=Subquery(
                    latest_consultation.values("consultant_id")[:1],
                ),
            )
            .filter(
                latest_consultation_status=Consultation.Status.WAITING,
                latest_consultation_consultant_id__isnull=True,
            )
        )

    @staticmethod
    def lock_claimable(inquiry_public_id: UUID) -> Inquiry | None:
        """Lock one synthetic inquiry before checking Claim eligibility."""

        return (
            Inquiry.objects.select_for_update(of=("self",))
            .select_related(
                "subscription",
                "subscription__customer",
                "subscription__customer__user",
                "subscription__product_model",
                "assigned_user",
            )
            .filter(
                public_id=inquiry_public_id,
                subscription__customer__deleted_at__isnull=True,
                subscription__customer__is_synthetic=True,
                subscription__customer__user__is_synthetic=True,
            )
            .first()
        )

    @staticmethod
    def _with_list_projection(
        queryset: QuerySet[Inquiry],
    ) -> QuerySet[Inquiry]:
        latest_assessment = SymptomAssessment.objects.filter(
            inquiry_id=OuterRef("pk")
        ).order_by("-assessment_version", "-created_at", "-pk")

        queryset = (
            queryset.select_related(
                "subscription",
                "subscription__customer",
                "subscription__product_model",
            )
            .prefetch_related(
                Prefetch(
                    "consultations",
                    queryset=Consultation.objects.order_by("-sequence", "-id"),
                    to_attr="allowed_action_consultations",
                ),
                Prefetch(
                    "visits",
                    queryset=Visit.objects.select_related("technician").order_by(
                        "-created_at", "-id"
                    ),
                    to_attr="allowed_action_visits",
                ),
            )
            .annotate(
                latest_assessment_risk=Subquery(
                    latest_assessment.values("risk_level_code")[:1],
                    output_field=CharField(),
                ),
                latest_assessment_priority=Subquery(
                    latest_assessment.values("priority_code")[:1],
                    output_field=CharField(),
                ),
                latest_assessment_usage_guidance=Subquery(
                    latest_assessment.values("usage_guidance_status")[:1],
                    output_field=CharField(),
                ),
            )
            .annotate(
                effective_risk_level=Coalesce(
                    "risk_level_code",
                    "latest_assessment_risk",
                    Value(Inquiry.RiskLevel.GENERAL),
                )
            )
            .annotate(
                effective_priority=Case(
                    When(
                        effective_risk_level=Inquiry.RiskLevel.DANGER,
                        then=Value("URGENT"),
                    ),
                    When(
                        priority_code=Inquiry.Priority.URGENT,
                        then=Value("URGENT"),
                    ),
                    When(
                        latest_assessment_priority__in=(
                            "URGENT",
                            "priority_consultation",
                        ),
                        then=Value("URGENT"),
                    ),
                    When(
                        effective_risk_level=Inquiry.RiskLevel.CAUTION,
                        then=Value("HIGH"),
                    ),
                    When(
                        priority_code=Inquiry.Priority.HIGH,
                        then=Value("HIGH"),
                    ),
                    When(
                        latest_assessment_priority__in=(
                            "HIGH",
                            "consultation_recommended",
                        ),
                        then=Value("HIGH"),
                    ),
                    When(
                        priority_code=Inquiry.Priority.NORMAL,
                        then=Value("NORMAL"),
                    ),
                    When(
                        latest_assessment_priority="LOW",
                        then=Value("LOW"),
                    ),
                    When(
                        priority_code=Inquiry.Priority.LOW,
                        then=Value("LOW"),
                    ),
                    When(
                        latest_assessment_priority__in=(
                            "NORMAL",
                            "general_guidance",
                        ),
                        then=Value("NORMAL"),
                    ),
                    default=Value("NORMAL"),
                    output_field=CharField(),
                ),
                effective_usage_guidance_status=Coalesce(
                    "usage_guidance_status",
                    "latest_assessment_usage_guidance",
                    output_field=CharField(),
                ),
            )
        )
        return queryset

    @classmethod
    def list_unassigned_page(
        cls,
        *,
        q: str | None,
        risk_levels: list[str],
        priorities: list[str],
        from_date: date | None,
        to_date: date | None,
        sort: str,
        offset: int,
        limit: int,
    ) -> tuple[list[Inquiry], int]:
        queryset = cls._apply_non_status_filters(
            cls.unassigned_consultation_queue(),
            q=q,
            risk_levels=risk_levels,
            priorities=priorities,
            from_date=from_date,
            to_date=to_date,
        )
        queryset = cls._apply_sort(queryset, sort=sort)
        total = queryset.count()
        return list(queryset[offset : offset + limit]), total

    @classmethod
    def list_page(
        cls,
        *,
        actor: Any,
        q: str | None,
        statuses: list[str],
        risk_levels: list[str],
        priorities: list[str],
        from_date: date | None,
        to_date: date | None,
        sort: str,
        offset: int,
        limit: int,
    ) -> tuple[list[Inquiry], int, dict[str, int]]:
        queryset = cls.visible_for_consultant(actor)
        queryset = cls._apply_non_status_filters(
            queryset,
            q=q,
            risk_levels=risk_levels,
            priorities=priorities,
            from_date=from_date,
            to_date=to_date,
        )
        status_counts = {
            row["status_code"]: row["total"]
            for row in queryset.values("status_code")
            .annotate(total=Count("id"))
            .order_by("status_code")
        }
        if statuses:
            queryset = queryset.filter(status_code__in=statuses)

        queryset = cls._apply_sort(queryset, sort=sort)
        total = queryset.count()
        return list(queryset[offset : offset + limit]), total, status_counts

    @staticmethod
    def _apply_non_status_filters(
        queryset: QuerySet[Inquiry],
        *,
        q: str | None,
        risk_levels: list[str],
        priorities: list[str],
        from_date: date | None,
        to_date: date | None,
    ) -> QuerySet[Inquiry]:
        if q:
            queryset = queryset.filter(
                Q(inquiry_code__icontains=q)
                | Q(raw_text__icontains=q)
                | Q(subscription__customer__customer_name__icontains=q)
                | Q(subscription__product_model__model_code__icontains=q)
                | Q(subscription__product_model__model_name__icontains=q)
            )
        if risk_levels:
            queryset = queryset.filter(
                effective_risk_level__in=risk_levels
            )
        if priorities:
            queryset = queryset.filter(effective_priority__in=priorities)
        if from_date is not None and from_date != date.min:
            queryset = queryset.filter(
                created_at__gte=datetime.combine(
                    from_date,
                    time.min,
                    tzinfo=BUSINESS_TIMEZONE,
                )
            )
        if to_date is not None and to_date != date.max:
            next_day = to_date + timedelta(days=1)
            queryset = queryset.filter(
                created_at__lt=datetime.combine(
                    next_day,
                    time.min,
                    tzinfo=BUSINESS_TIMEZONE,
                )
            )
        return queryset

    @staticmethod
    def _apply_sort(
        queryset: QuerySet[Inquiry],
        *,
        sort: str,
    ) -> QuerySet[Inquiry]:
        if sort == "UPDATED_ASC":
            return queryset.order_by("updated_at", "public_id")
        if sort == "WAITING_DESC":
            return queryset.order_by("created_at", "public_id")
        if sort == "RISK_DESC":
            return queryset.annotate(
                consultant_risk_rank=Case(
                    When(
                        effective_risk_level=Inquiry.RiskLevel.DANGER,
                        then=Value(3),
                    ),
                    When(
                        effective_risk_level=Inquiry.RiskLevel.CAUTION,
                        then=Value(2),
                    ),
                    When(
                        effective_risk_level=Inquiry.RiskLevel.GENERAL,
                        then=Value(1),
                    ),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ).order_by("-consultant_risk_rank", "created_at", "public_id")
        return queryset.order_by("-updated_at", "public_id")

    @classmethod
    def find_detail(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
    ) -> Inquiry | None:
        completed_care = (
            CareRecord.objects.filter(status_code=CareRecord.Status.COMPLETED)
            .only("subscription_id", "performed_on", "completed_at")
            .order_by()
        )
        answered_qa = InquiryQA.objects.filter(
            customer_answer__isnull=False,
        ).select_related("customer_answer").order_by(
            "sequence_no",
            "public_id",
        )
        guidance_versions = (
            Guidance.objects.filter(
                Q(review_status_code__in=("APPROVED", "CONFIRMED"))
                | Q(
                    generated_by_ai_run__status_code__in=(
                        AIRun.Status.SUCCEEDED,
                        AIRun.Status.NO_EVIDENCE,
                    ),
                    generated_by_ai_run__schema_validation_status_code=(
                        AIRun.SchemaValidationStatus.PASSED
                    ),
                    generated_by_ai_run__validated_output_payload__isnull=False,
                )
            )
            .select_related("generated_by_ai_run")
            .order_by("-guidance_version", "-created_at", "-public_id")
        )
        state_history = (
            TransitionHistory.objects.filter(
                target_type_code=TransitionHistory.TargetType.INQUIRY,
            )
            .select_related("actor")
            .order_by("state_version", "changed_at", "public_id")
        )
        visits = (
            Visit.objects.filter(
                data_classification=Visit.DataClassification.SYNTHETIC,
            )
            .filter(
                Q(technician__isnull=True)
                | Q(technician__is_synthetic=True)
            )
            .select_related("technician")
            .order_by("-requested_at", "-public_id")
        )
        return (
            cls.visible_for_consultant(actor)
            .prefetch_related(
                Prefetch(
                    "subscription__care_records",
                    queryset=completed_care,
                    to_attr="consultant_completed_care_records",
                ),
                Prefetch(
                    "qa_entries",
                    queryset=answered_qa,
                    to_attr="consultant_answered_qa_entries",
                ),
                Prefetch(
                    "guidance_versions",
                    queryset=guidance_versions,
                    to_attr="consultant_guidance_versions",
                ),
                Prefetch(
                    "transition_history",
                    queryset=state_history,
                    to_attr="consultant_state_history",
                ),
                Prefetch(
                    "visits",
                    queryset=visits,
                    to_attr="consultant_visits",
                ),
            )
            .filter(public_id=inquiry_public_id)
            .first()
        )
