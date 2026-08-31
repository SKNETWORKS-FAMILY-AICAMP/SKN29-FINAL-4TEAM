"""Persistent Backend business ledger for AI guidance human review."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

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

    class ConsultationOrigin(models.TextChoices):
        NOT_REQUIRED = "NOT_REQUIRED", "Not required"
        SAFETY_LOCKED = "SAFETY_LOCKED", "Safety locked"
        FAIL_CLOSED_LOCKED = (
            "FAIL_CLOSED_LOCKED",
            "Fail-closed locked",
        )
        NON_SAFETY_RESOLVABLE = (
            "NON_SAFETY_RESOLVABLE",
            "Non-safety resolvable",
        )
        UNKNOWN_LOCKED = "UNKNOWN_LOCKED", "Unknown locked"

    class ConsultationDisposition(models.TextChoices):
        PRESERVE = "PRESERVE", "Preserve"
        REQUIRE = "REQUIRE", "Require"
        RESOLVE_NON_SAFETY = (
            "RESOLVE_NON_SAFETY",
            "Resolve non-safety",
        )

    class ConsultationOriginReason(models.TextChoices):
        NOT_REQUIRED = "NOT_REQUIRED", "Not required"
        DANGER_ASSESSMENT = "DANGER_ASSESSMENT", "Danger assessment"
        EXPLICIT_SAFETY_RULE = (
            "EXPLICIT_SAFETY_RULE",
            "Explicit safety rule",
        )
        FAIL_CLOSED_AI_RESULT = (
            "FAIL_CLOSED_AI_RESULT",
            "Fail-closed AI result",
        )
        HARNESS_UNSUPPORTED_FUNCTION = (
            "HARNESS_UNSUPPORTED_FUNCTION",
            "Harness unsupported function",
        )
        HARNESS_SCOPE_EXCEEDED = (
            "HARNESS_SCOPE_EXCEEDED",
            "Harness scope exceeded",
        )
        UNCLASSIFIED_AI_SIGNAL = (
            "UNCLASSIFIED_AI_SIGNAL",
            "Unclassified AI signal",
        )
        LEGACY_UNCLASSIFIED = (
            "LEGACY_UNCLASSIFIED",
            "Legacy unclassified",
        )

    class ConsultationChangeReason(models.TextChoices):
        CONSULTANT_SAFETY_ESCALATION = (
            "CONSULTANT_SAFETY_ESCALATION",
            "Consultant safety escalation",
        )
        PRODUCT_FUNCTION_UNCERTAIN = (
            "PRODUCT_FUNCTION_UNCERTAIN",
            "Product function uncertain",
        )
        CUSTOMER_CONTEXT_INCOMPLETE = (
            "CUSTOMER_CONTEXT_INCOMPLETE",
            "Customer context incomplete",
        )
        PRODUCT_CAPABILITY_VERIFIED = (
            "PRODUCT_CAPABILITY_VERIFIED",
            "Product capability verified",
        )
        HARNESS_SCOPE_VERIFIED = (
            "HARNESS_SCOPE_VERIFIED",
            "Harness scope verified",
        )
        HUMAN_REVIEW_REJECTED = (
            "HUMAN_REVIEW_REJECTED",
            "Human review rejected",
        )

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
    original_requires_consultation = models.BooleanField()
    effective_requires_consultation = models.BooleanField()
    consultation_origin_code = models.CharField(
        max_length=40,
        choices=ConsultationOrigin.choices,
    )
    consultation_origin_reason_code = models.CharField(
        max_length=80,
        choices=ConsultationOriginReason.choices,
    )
    consultation_disposition_code = models.CharField(
        max_length=40,
        choices=ConsultationDisposition.choices,
        null=True,
        blank=True,
    )
    consultation_reason_code = models.CharField(
        max_length=80,
        choices=ConsultationChangeReason.choices,
        null=True,
        blank=True,
    )
    consultation_evidence_snapshot = models.JSONField(
        default=list,
        blank=True,
    )

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
                condition=Q(
                    consultation_origin_code__in=[
                        "NOT_REQUIRED",
                        "SAFETY_LOCKED",
                        "FAIL_CLOSED_LOCKED",
                        "NON_SAFETY_RESOLVABLE",
                        "UNKNOWN_LOCKED",
                    ]
                ),
                name="ck_hreview_consult_origin",
            ),
            models.CheckConstraint(
                condition=(
                    Q(consultation_disposition_code__isnull=True)
                    | Q(
                        consultation_disposition_code__in=[
                            "PRESERVE",
                            "REQUIRE",
                            "RESOLVE_NON_SAFETY",
                        ]
                    )
                ),
                name="ck_hreview_consult_disposition",
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
                        consultation_disposition_code__isnull=True,
                        consultation_reason_code__isnull=True,
                        consultation_evidence_snapshot=[],
                        effective_requires_consultation=F(
                            "original_requires_consultation"
                        ),
                    )
                    | Q(
                        status_code__in=[
                            "APPROVED",
                            "MODIFIED",
                            "REJECTED",
                            "RESUME_FAILED",
                        ],
                        consultation_disposition_code__isnull=False,
                    )
                ),
                name="ck_hreview_consult_audit",
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

        evidence_snapshot = self.consultation_evidence_snapshot
        if not isinstance(evidence_snapshot, list) or any(
            not isinstance(item, dict) for item in evidence_snapshot
        ):
            errors["consultation_evidence_snapshot"] = (
                "상담 해소 Evidence 스냅샷은 객체 배열이어야 합니다."
            )

        if self.original_requires_consultation:
            if self.consultation_origin_code == self.ConsultationOrigin.NOT_REQUIRED:
                errors["consultation_origin_code"] = (
                    "상담 필요 원본에는 NOT_REQUIRED를 사용할 수 없습니다."
                )
        elif self.consultation_origin_code != self.ConsultationOrigin.NOT_REQUIRED:
            errors["consultation_origin_code"] = (
                "상담 불필요 원본은 NOT_REQUIRED로 분류해야 합니다."
            )

        allowed_origin_reasons = {
            self.ConsultationOrigin.NOT_REQUIRED: {
                self.ConsultationOriginReason.NOT_REQUIRED,
            },
            self.ConsultationOrigin.SAFETY_LOCKED: {
                self.ConsultationOriginReason.DANGER_ASSESSMENT,
                self.ConsultationOriginReason.EXPLICIT_SAFETY_RULE,
            },
            self.ConsultationOrigin.FAIL_CLOSED_LOCKED: {
                self.ConsultationOriginReason.FAIL_CLOSED_AI_RESULT,
            },
            self.ConsultationOrigin.NON_SAFETY_RESOLVABLE: {
                self.ConsultationOriginReason.HARNESS_UNSUPPORTED_FUNCTION,
                self.ConsultationOriginReason.HARNESS_SCOPE_EXCEEDED,
            },
            self.ConsultationOrigin.UNKNOWN_LOCKED: {
                self.ConsultationOriginReason.UNCLASSIFIED_AI_SIGNAL,
                self.ConsultationOriginReason.LEGACY_UNCLASSIFIED,
            },
        }
        if self.consultation_origin_reason_code not in allowed_origin_reasons.get(
            self.consultation_origin_code,
            set(),
        ):
            errors["consultation_origin_reason_code"] = (
                "상담 원인과 원인 사유 코드가 일치해야 합니다."
            )

        if pending:
            if self.consultation_disposition_code is not None:
                errors["consultation_disposition_code"] = (
                    "대기 상태에는 상담 변경 결정을 기록할 수 없습니다."
                )
            if self.consultation_reason_code is not None or evidence_snapshot:
                errors["consultation_reason_code"] = (
                    "대기 상태에는 상담 변경 감사 자료가 없어야 합니다."
                )
            if (
                self.effective_requires_consultation
                is not self.original_requires_consultation
            ):
                errors["effective_requires_consultation"] = (
                    "대기 상태의 최종 상담 여부는 원본과 같아야 합니다."
                )
        elif self.consultation_disposition_code is None:
            errors["consultation_disposition_code"] = (
                "완료 상태에는 상담 처리 결정을 기록해야 합니다."
            )
        elif (
            self.consultation_disposition_code
            == self.ConsultationDisposition.PRESERVE
        ):
            if (
                self.effective_requires_consultation
                is not self.original_requires_consultation
            ):
                errors["effective_requires_consultation"] = (
                    "PRESERVE 결정은 원본 상담 여부를 바꿀 수 없습니다."
                )
            if self.consultation_reason_code is not None or evidence_snapshot:
                errors["consultation_reason_code"] = (
                    "PRESERVE 결정에는 변경 사유나 Evidence가 없어야 합니다."
                )
        elif (
            self.consultation_disposition_code
            == self.ConsultationDisposition.REQUIRE
        ):
            if self.effective_requires_consultation is not True:
                errors["effective_requires_consultation"] = (
                    "REQUIRE 결정의 최종 상담 여부는 true여야 합니다."
                )
            if not self.consultation_reason_code:
                errors["consultation_reason_code"] = (
                    "상담 필요 결정에는 사유 코드가 필요합니다."
                )
            elif self.consultation_reason_code not in {
                self.ConsultationChangeReason.CONSULTANT_SAFETY_ESCALATION,
                self.ConsultationChangeReason.PRODUCT_FUNCTION_UNCERTAIN,
                self.ConsultationChangeReason.CUSTOMER_CONTEXT_INCOMPLETE,
                self.ConsultationChangeReason.HUMAN_REVIEW_REJECTED,
            }:
                errors["consultation_reason_code"] = (
                    "상담 필요 결정에 허용되지 않은 사유 코드입니다."
                )
            if evidence_snapshot:
                errors["consultation_evidence_snapshot"] = (
                    "상담 필요 상향에는 해소 Evidence를 저장하지 않습니다."
                )
        elif (
            self.consultation_disposition_code
            == self.ConsultationDisposition.RESOLVE_NON_SAFETY
        ):
            if not self.original_requires_consultation:
                errors["original_requires_consultation"] = (
                    "원본이 true일 때만 상담 필요를 해소할 수 있습니다."
                )
            if self.effective_requires_consultation is not False:
                errors["effective_requires_consultation"] = (
                    "해소 결정의 최종 상담 여부는 false여야 합니다."
                )
            if (
                self.consultation_origin_code
                != self.ConsultationOrigin.NON_SAFETY_RESOLVABLE
            ):
                errors["consultation_origin_code"] = (
                    "비-Safety 원인으로 분류된 경우만 해소할 수 있습니다."
                )
            if not self.consultation_reason_code or not evidence_snapshot:
                errors["consultation_reason_code"] = (
                    "해소 결정에는 사유와 검증 Evidence가 모두 필요합니다."
                )
            elif self.consultation_reason_code not in {
                self.ConsultationChangeReason.PRODUCT_CAPABILITY_VERIFIED,
                self.ConsultationChangeReason.HARNESS_SCOPE_VERIFIED,
            }:
                errors["consultation_reason_code"] = (
                    "비-Safety 해소에 허용되지 않은 사유 코드입니다."
                )

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
