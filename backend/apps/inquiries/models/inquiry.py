"""Customer inquiry aggregate root."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.subscriptions.models import CustomerSubscription
from common.models.base import TimestampedModel


def generate_inquiry_code() -> str:
    """Create a non-sensitive business identifier independent of the DB key."""

    return f"INQ-{uuid.uuid4().hex.upper()}"


class Inquiry(TimestampedModel):
    """A customer-owned support inquiry governed by the PM state contract."""

    class Channel(models.TextChoices):
        WEB = "WEB", "Web"
        MOBILE = "MOBILE", "Mobile"
        PHONE = "PHONE", "Phone"
        OPERATOR = "OPERATOR", "Operator"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        QUESTIONNAIRE_IN_PROGRESS = (
            "QUESTIONNAIRE_IN_PROGRESS",
            "Questionnaire in progress",
        )
        AI_GUIDANCE = "AI_GUIDANCE", "AI guidance"
        CONSULTATION_REQUIRED = (
            "CONSULTATION_REQUIRED",
            "Consultation required",
        )
        CONSULTATION_IN_PROGRESS = (
            "CONSULTATION_IN_PROGRESS",
            "Consultation in progress",
        )
        VISIT_REVIEW_PENDING = (
            "VISIT_REVIEW_PENDING",
            "Visit review pending",
        )
        VISIT_SCHEDULING = "VISIT_SCHEDULING", "Visit scheduling"
        VISIT_SCHEDULED = "VISIT_SCHEDULED", "Visit scheduled"
        COMPLETION_PENDING = "COMPLETION_PENDING", "Completion pending"
        REVISIT_REQUIRED = "REVISIT_REQUIRED", "Revisit required"
        REOPENED = "REOPENED", "Reopened"
        RESOLVED = "RESOLVED", "Resolved"
        CANCELLED = "CANCELLED", "Cancelled"

    class CancellationReason(models.TextChoices):
        CUSTOMER_REQUEST = "CUSTOMER_REQUEST", "Customer request"
        DUPLICATE_INQUIRY = "DUPLICATE_INQUIRY", "Duplicate inquiry"
        ISSUE_RESOLVED = "ISSUE_RESOLVED", "Issue resolved"
        OTHER = "OTHER", "Other"

    class AssignedRole(models.TextChoices):
        NONE = "NONE", "No assignee"
        CONSULTANT = "CONSULTANT", "Consultant"
        TECHNICIAN = "TECHNICIAN", "Technician"

    class RiskLevel(models.TextChoices):
        GENERAL = "general", "General"
        CAUTION = "caution", "Caution"
        DANGER = "danger", "Danger"

    class UsageGuidanceStatus(models.TextChoices):
        NORMAL = "NORMAL", "Normal use"
        PARTIAL_STOP = "PARTIAL_STOP", "Partial stop"
        TOTAL_STOP = "TOTAL_STOP", "Total stop"
        PENDING_CONSULTATION = (
            "PENDING_CONSULTATION",
            "Pending consultation",
        )

    class EvidenceMode(models.TextChoices):
        EXACT_MODEL = "EXACT_MODEL", "Exact model evidence"
        NO_EVIDENCE = "NO_EVIDENCE", "No evidence"
        PARTIAL_EVIDENCE = "PARTIAL_EVIDENCE", "Partial evidence"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    inquiry_code = models.CharField(
        max_length=50,
        unique=True,
        default=generate_inquiry_code,
        editable=False,
    )
    scenario_code = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        unique=True,
        help_text="합성 시나리오 추적용 업무 식별자",
    )
    subscription = models.ForeignKey(
        CustomerSubscription,
        on_delete=models.PROTECT,
        related_name="inquiries",
        db_column="subscription_id",
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="initiated_inquiries",
        db_column="initiated_by_id",
    )
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_inquiries",
        db_column="assigned_user_id",
        null=True,
        blank=True,
    )
    assigned_role_code = models.CharField(
        max_length=40,
        choices=AssignedRole.choices,
        default=AssignedRole.NONE,
    )
    channel_code = models.CharField(
        max_length=40,
        choices=Channel.choices,
        null=True,
        blank=True,
        help_text="원본에 접수 채널이 없으면 NULL로 보존",
    )
    raw_text = models.TextField()
    risk_level_code = models.CharField(
        max_length=40,
        choices=RiskLevel.choices,
        null=True,
        blank=True,
    )
    usage_guidance_status = models.CharField(
        max_length=40,
        choices=UsageGuidanceStatus.choices,
        null=True,
        blank=True,
    )
    evidence_ids = models.JSONField(default=list, blank=True)
    evidence_mode = models.CharField(
        max_length=40,
        choices=EvidenceMode.choices,
        null=True,
        blank=True,
    )
    requires_fallback = models.BooleanField(default=False)
    source_idempotency_key = models.CharField(
        max_length=128,
        null=True,
        blank=True,
    )
    source_correlation_id = models.UUIDField(null=True, blank=True)
    questionnaire_session_public_id = models.UUIDField(
        null=True,
        blank=True,
    )
    status_code = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    state_version = models.PositiveIntegerField(default=1)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason_code = models.CharField(
        max_length=40,
        choices=CancellationReason.choices,
        null=True,
        blank=True,
    )
    cancellation_reason_detail = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "support_inquiry"
        constraints = [
            models.UniqueConstraint(
                fields=["id", "subscription"],
                name="ux_inquiry_id_subscription",
            ),
            models.CheckConstraint(
                condition=Q(
                    channel_code__in=[
                        "WEB",
                        "MOBILE",
                        "PHONE",
                        "OPERATOR",
                    ]
                ),
                name="ck_inquiry_channel_code",
            ),
            models.CheckConstraint(
                condition=Q(
                    assigned_role_code__in=[
                        "NONE",
                        "CONSULTANT",
                        "TECHNICIAN",
                    ]
                ),
                name="ck_inquiry_assigned_role",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        assigned_role_code="NONE",
                        assigned_user__isnull=True,
                    )
                    | Q(
                        assigned_role_code__in=[
                            "CONSULTANT",
                            "TECHNICIAN",
                        ],
                        assigned_user__isnull=False,
                    )
                ),
                name="ck_inquiry_assignment_pair",
            ),
            models.CheckConstraint(
                condition=(
                    Q(risk_level_code__isnull=True)
                    | Q(
                        risk_level_code__in=[
                            "general",
                            "caution",
                            "danger",
                        ]
                    )
                ),
                name="ck_inquiry_risk_level",
            ),
            models.CheckConstraint(
                condition=(
                    Q(usage_guidance_status__isnull=True)
                    | Q(
                        usage_guidance_status__in=[
                            "NORMAL",
                            "PARTIAL_STOP",
                            "TOTAL_STOP",
                            "PENDING_CONSULTATION",
                        ]
                    )
                ),
                name="ck_inquiry_usage_status",
            ),
            models.CheckConstraint(
                condition=(
                    Q(evidence_mode__isnull=True)
                    | Q(
                        evidence_mode__in=[
                            "EXACT_MODEL",
                            "NO_EVIDENCE",
                            "PARTIAL_EVIDENCE",
                        ]
                    )
                ),
                name="ck_inquiry_evidence_mode",
            ),
            models.CheckConstraint(
                condition=Q(
                    status_code__in=[
                        "DRAFT",
                        "QUESTIONNAIRE_IN_PROGRESS",
                        "AI_GUIDANCE",
                        "CONSULTATION_REQUIRED",
                        "CONSULTATION_IN_PROGRESS",
                        "VISIT_REVIEW_PENDING",
                        "VISIT_SCHEDULING",
                        "VISIT_SCHEDULED",
                        "COMPLETION_PENDING",
                        "REVISIT_REQUIRED",
                        "REOPENED",
                        "RESOLVED",
                        "CANCELLED",
                    ]
                ),
                name="ck_inquiry_status_code",
            ),
            models.CheckConstraint(
                condition=Q(state_version__gt=0),
                name="ck_inquiry_state_version_positive",
            ),
            models.CheckConstraint(
                condition=~Q(raw_text=""),
                name="ck_inquiry_raw_text_nonempty",
            ),
            models.CheckConstraint(
                condition=(
                    Q(cancellation_reason_code__isnull=True)
                    | Q(
                        cancellation_reason_code__in=[
                            "CUSTOMER_REQUEST",
                            "DUPLICATE_INQUIRY",
                            "ISSUE_RESOLVED",
                            "OTHER",
                        ]
                    )
                ),
                name="ck_inquiry_cancel_reason_code",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status_code="CANCELLED",
                        cancelled_at__isnull=False,
                        cancellation_reason_code__isnull=False,
                    )
                    | (
                        ~Q(status_code="CANCELLED")
                        & Q(cancelled_at__isnull=True)
                        & Q(cancellation_reason_code__isnull=True)
                        & Q(cancellation_reason_detail__isnull=True)
                    )
                ),
                name="ck_inquiry_cancellation_fields",
            ),
        ]
        indexes = [
            models.Index(
                fields=["subscription", "status_code"],
                name="ix_inquiry_subscription_status",
            ),
            models.Index(
                fields=["initiated_by", "status_code"],
                name="ix_inquiry_actor_status",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.inquiry_code} ({self.status_code})"

    def clean(self) -> None:
        super().clean()
        if not self.assigned_user_id:
            return
        user_role = getattr(self.assigned_user, "role_code", None)
        if user_role != self.assigned_role_code:
            raise ValidationError(
                {
                    "assigned_user": (
                        "assigned_user 역할과 assigned_role_code가 일치해야 합니다."
                    )
                }
            )
