"""Persistent Backend business ledger for AI guidance human review."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.common_codes.db_expressions import IsJSONObject
from common.models.base import TimestampedModel


class HumanReview(TimestampedModel):
    """Keep review state separate from the PM-owned Inquiry state machine."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        MODIFIED = "MODIFIED", "Modified"
        REJECTED = "REJECTED", "Rejected"
        RESUME_FAILED = "RESUME_FAILED", "Resume failed"

    class Decision(models.TextChoices):
        APPROVE = "APPROVE", "Approve"
        MODIFY = "MODIFY", "Modify"
        REJECT = "REJECT", "Reject"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.PROTECT,
        related_name="human_reviews",
        db_column="inquiry_id",
        db_index=False,
    )
    guidance = models.OneToOneField(
        "inquiries.Guidance",
        on_delete=models.PROTECT,
        related_name="human_review",
        db_column="guidance_id",
    )
    published_guidance = models.ForeignKey(
        "inquiries.Guidance",
        on_delete=models.PROTECT,
        related_name="published_by_human_reviews",
        db_column="published_guidance_id",
        null=True,
        blank=True,
    )
    checkpoint_thread_id = models.CharField(max_length=100, unique=True)
    source_ai_request_id = models.CharField(max_length=100)
    source_inquiry_state_version = models.PositiveIntegerField()
    status_code = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.PENDING,
    )
    decision_code = models.CharField(
        max_length=40,
        choices=Decision.choices,
        null=True,
        blank=True,
    )
    review_state_version = models.PositiveIntegerField(default=1)
    initial_reason_code = models.CharField(max_length=80)
    decision_reason_code = models.CharField(max_length=80, null=True, blank=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="human_review_decisions",
        db_column="reviewer_id",
        null=True,
        blank=True,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_idempotency_key = models.CharField(
        max_length=128,
        null=True,
        blank=True,
    )
    decision_correlation_id = models.UUIDField(null=True, blank=True)
    modified_guidance_payload = models.JSONField(default=dict, blank=True)
    resume_failure_code = models.CharField(max_length=80, null=True, blank=True)

    class Meta:
        db_table = "support_human_review"
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    status_code__in=[
                        "PENDING",
                        "APPROVED",
                        "MODIFIED",
                        "REJECTED",
                        "RESUME_FAILED",
                    ]
                ),
                name="ck_hreview_status",
            ),
            models.CheckConstraint(
                condition=(
                    Q(decision_code__isnull=True)
                    | Q(decision_code__in=["APPROVE", "MODIFY", "REJECT"])
                ),
                name="ck_hreview_decision",
            ),
            models.CheckConstraint(
                condition=Q(review_state_version__gt=0)
                & Q(source_inquiry_state_version__gt=0),
                name="ck_hreview_versions",
            ),
            models.CheckConstraint(
                condition=(
                    Q(reviewer__isnull=True, decided_at__isnull=True)
                    | Q(reviewer__isnull=False, decided_at__isnull=False)
                ),
                name="ck_hreview_actor_time",
            ),
            models.CheckConstraint(
                condition=IsJSONObject("modified_guidance_payload"),
                name="ck_hreview_modified_object",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status_code="PENDING",
                        decision_code__isnull=True,
                        decision_reason_code__isnull=True,
                        reviewer__isnull=True,
                        decided_at__isnull=True,
                        decision_idempotency_key__isnull=True,
                        decision_correlation_id__isnull=True,
                    )
                    | Q(
                        status_code__in=[
                            "APPROVED",
                            "MODIFIED",
                            "REJECTED",
                            "RESUME_FAILED",
                        ],
                        decision_code__isnull=False,
                        decision_reason_code__isnull=False,
                        reviewer__isnull=False,
                        decided_at__isnull=False,
                        decision_idempotency_key__isnull=False,
                        decision_correlation_id__isnull=False,
                    )
                ),
                name="ck_hreview_decision_audit",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status_code="PENDING",
                        published_guidance__isnull=True,
                        resume_failure_code__isnull=True,
                        modified_guidance_payload={},
                    )
                    | Q(
                        status_code="APPROVED",
                        decision_code="APPROVE",
                        published_guidance__isnull=False,
                        resume_failure_code__isnull=True,
                        modified_guidance_payload={},
                    )
                    | Q(
                        status_code="MODIFIED",
                        decision_code="MODIFY",
                        published_guidance__isnull=False,
                        resume_failure_code__isnull=True,
                    )
                    & ~Q(modified_guidance_payload={})
                    | Q(
                        status_code="REJECTED",
                        decision_code="REJECT",
                        published_guidance__isnull=True,
                        resume_failure_code__isnull=True,
                        modified_guidance_payload={},
                    )
                    | (
                        Q(
                            status_code="RESUME_FAILED",
                            resume_failure_code__isnull=False,
                        )
                        & (
                            Q(
                                decision_code="APPROVE",
                                published_guidance__isnull=False,
                                modified_guidance_payload={},
                            )
                            | Q(
                                decision_code="MODIFY",
                                published_guidance__isnull=False,
                            )
                            & ~Q(modified_guidance_payload={})
                            | Q(
                                decision_code="REJECT",
                                published_guidance__isnull=True,
                                modified_guidance_payload={},
                            )
                        )
                    )
                ),
                name="ck_hreview_state_fields",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status_code", "created_at"],
                condition=Q(status_code="PENDING"),
                name="ix_hreview_pending_created",
            ),
            models.Index(
                fields=["inquiry", "-created_at"],
                name="ix_hreview_inquiry_created",
            ),
        ]

    def clean(self) -> None:
        """Validate cross-row and state-dependent review invariants."""

        super().clean()
        errors: dict[str, str] = {}
        if self.guidance_id and self.inquiry_id:
            if self.guidance.inquiry_id != self.inquiry_id:
                errors["guidance"] = "Guidance와 HumanReview의 문의가 같아야 합니다."
        if self.published_guidance_id and self.inquiry_id:
            if self.published_guidance.inquiry_id != self.inquiry_id:
                errors["published_guidance"] = (
                    "공개 Guidance와 HumanReview의 문의가 같아야 합니다."
                )

        pending = self.status_code == self.Status.PENDING
        decision_fields_present = any(
            value is not None
            for value in (
                self.decision_code,
                self.reviewer_id,
                self.decided_at,
                self.decision_idempotency_key,
                self.decision_correlation_id,
            )
        )
        if pending and decision_fields_present:
            errors["status_code"] = "대기 상태에는 결정 정보가 없어야 합니다."
        if not pending and not all(
            value is not None
            for value in (
                self.decision_code,
                self.reviewer_id,
                self.decided_at,
                self.decision_idempotency_key,
                self.decision_correlation_id,
            )
        ):
            errors["decision_code"] = "완료 상태에는 결정 감사 정보가 필요합니다."

        expected_status = {
            self.Decision.APPROVE: self.Status.APPROVED,
            self.Decision.MODIFY: self.Status.MODIFIED,
            self.Decision.REJECT: self.Status.REJECTED,
        }.get(self.decision_code)
        if self.status_code not in {self.Status.PENDING, self.Status.RESUME_FAILED}:
            if expected_status != self.status_code:
                errors["status_code"] = "결정과 검토 상태가 일치해야 합니다."
        if self.decision_code == self.Decision.MODIFY:
            if not self.modified_guidance_payload or not self.published_guidance_id:
                errors["modified_guidance_payload"] = (
                    "수정 결정에는 수정본과 공개 Guidance가 필요합니다."
                )
        elif self.modified_guidance_payload:
            errors["modified_guidance_payload"] = (
                "수정 결정이 아니면 수정 Payload를 저장할 수 없습니다."
            )
        if self.decision_code == self.Decision.APPROVE and not self.published_guidance_id:
            errors["published_guidance"] = "승인 결정에는 공개 Guidance가 필요합니다."
        if self.decision_code == self.Decision.REJECT and self.published_guidance_id:
            errors["published_guidance"] = "거절 결정은 Guidance를 공개하지 않습니다."
        if self.status_code == self.Status.RESUME_FAILED:
            if not self.resume_failure_code:
                errors["resume_failure_code"] = "Resume 실패 코드를 기록해야 합니다."
        elif self.resume_failure_code:
            errors["resume_failure_code"] = "Resume 실패 상태에서만 코드를 기록합니다."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.public_id} ({self.status_code})"
