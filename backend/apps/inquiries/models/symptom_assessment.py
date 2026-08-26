"""Versioned symptom risk assessments for one support inquiry."""

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.common_codes.db_expressions import IsJSONObject
from apps.inquiries.services.safety_rule_registry import (
    danger_assessment_is_valid,
)
from common.models.base import TimestampedModel


class SymptomAssessment(TimestampedModel):
    """Persist one ruleset or AI-assisted safety assessment version."""

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

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.PROTECT,
        related_name="symptom_assessments",
        db_column="inquiry_id",
        db_index=False,
    )
    assessment_version = models.PositiveIntegerField(default=1)
    ruleset_version = models.CharField(max_length=40)
    risk_level_code = models.CharField(
        max_length=40,
        choices=RiskLevel.choices,
    )
    priority_code = models.CharField(max_length=40)
    usage_guidance_status = models.CharField(
        max_length=32,
        choices=UsageGuidanceStatus.choices,
        null=True,
        blank=True,
    )
    requires_consultation = models.BooleanField(default=False)
    reason = models.TextField()
    rule_result = models.JSONField(default=dict)
    assessed_by_type_code = models.CharField(
        max_length=40,
        default="RULE",
    )
    ai_run = models.ForeignKey(
        "audit.AIRun",
        on_delete=models.PROTECT,
        related_name="symptom_assessments",
        db_column="ai_run_id",
        db_index=False,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "support_symptom_assessment"
        constraints = [
            models.UniqueConstraint(
                fields=["inquiry", "assessment_version"],
                name="ux_assessment_version",
            ),
            models.CheckConstraint(
                condition=Q(assessment_version__gt=0),
                name="ck_assessment_version_positive",
            ),
            models.CheckConstraint(
                condition=IsJSONObject(F("rule_result")),
                name="ck_assessment_rule_result_object",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(assessed_by_type_code="AI")
                    | Q(ai_run__isnull=False)
                ),
                name="ck_assessment_ai_origin",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(risk_level_code="danger")
                    | (
                        Q(
                            usage_guidance_status__isnull=False,
                            usage_guidance_status="TOTAL_STOP",
                            requires_consultation=True,
                        )
                        | Q(
                            usage_guidance_status__isnull=False,
                            usage_guidance_status="PARTIAL_STOP",
                            requires_consultation=True,
                            rule_result__matched_safety_rule_ids=[
                                "SAFETY-HOT-WATER-HEATER-001"
                            ],
                        )
                    )
                ),
                name="ck_assessment_danger_safety",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(risk_level_code="caution")
                    | Q(
                        usage_guidance_status__isnull=False,
                        usage_guidance_status__in=[
                            "PARTIAL_STOP",
                            "TOTAL_STOP",
                            "PENDING_CONSULTATION",
                        ],
                    )
                ),
                name="ck_assessment_caution_safety",
            ),
            models.CheckConstraint(
                condition=(
                    Q(usage_guidance_status__isnull=True)
                    | ~Q(
                        usage_guidance_status=(
                            "PENDING_CONSULTATION"
                        )
                    )
                    | Q(requires_consultation=True)
                ),
                name="ck_assessment_pending_consultation",
            ),
            models.CheckConstraint(
                condition=Q(
                    risk_level_code__in=[
                        "general",
                        "caution",
                        "danger",
                    ]
                ),
                name=(
                    "ck_support_symptom_assessment_"
                    "risk_level_code_allowed"
                ),
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
                name=(
                    "ck_support_symptom_assessment_"
                    "usage_guidance_status_allowed"
                ),
            ),
        ]
        indexes = [
            models.Index(
                fields=["risk_level_code", "created_at"],
                name="ix_assessment_risk",
            ),
            models.Index(
                fields=["ai_run", "inquiry"],
                name="ix_assessment_ai_run",
            ),
        ]

    def clean(self) -> None:
        """Validate cross-row AI policy and portable safety rules."""

        super().clean()
        errors: dict[str, str] = {}

        if not isinstance(self.rule_result, dict):
            errors["rule_result"] = "rule_result must be a JSON object."

        if self.risk_level_code == self.RiskLevel.DANGER:
            is_total_stop = (
                self.usage_guidance_status
                == self.UsageGuidanceStatus.TOTAL_STOP
                and self.requires_consultation
            )
            partial_payload = {
                "safety_assessment": {
                    **self.rule_result,
                    "risk_level": self.RiskLevel.DANGER,
                    "requires_consultation": self.requires_consultation,
                },
                "usage_guidance": {
                    "guidance_status": self.usage_guidance_status,
                },
            }
            is_approved_partial_stop = (
                self.usage_guidance_status
                == self.UsageGuidanceStatus.PARTIAL_STOP
                and danger_assessment_is_valid(
                    partial_payload,
                    require_guidance_details=False,
                )
            )
            if not is_total_stop and not is_approved_partial_stop:
                errors["risk_level_code"] = (
                    "A danger assessment requires consultation and either "
                    "TOTAL_STOP or an approved Rule-specific PARTIAL_STOP."
                )
        elif self.risk_level_code == self.RiskLevel.CAUTION:
            if self.usage_guidance_status not in {
                self.UsageGuidanceStatus.PARTIAL_STOP,
                self.UsageGuidanceStatus.TOTAL_STOP,
                self.UsageGuidanceStatus.PENDING_CONSULTATION,
            }:
                errors["usage_guidance_status"] = (
                    "A caution assessment requires restricted-use or "
                    "pending-consultation guidance."
                )

        if (
            self.usage_guidance_status
            == self.UsageGuidanceStatus.PENDING_CONSULTATION
            and not self.requires_consultation
        ):
            errors["requires_consultation"] = (
                "PENDING_CONSULTATION requires consultation."
            )

        if self.assessed_by_type_code == "AI" and self.ai_run_id is None:
            errors["ai_run"] = "An AI assessment requires an AI run."

        if self.ai_run_id is not None:
            ai_run = self.ai_run
            if (
                self.inquiry_id is not None
                and ai_run.inquiry_id != self.inquiry_id
            ):
                errors["ai_run"] = (
                    "The assessment and AI run must belong to the same "
                    "inquiry."
                )
            elif (
                ai_run.task_type_code
                not in {"ASSESS_RISK", "ANALYZE_SYMPTOM"}
                or ai_run.schema_validation_status_code != "PASSED"
            ):
                errors["ai_run"] = (
                    "A risk assessment can use only a schema-validated "
                    "ASSESS_RISK AI run."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return (
            f"{self.public_id} v{self.assessment_version} "
            f"({self.risk_level_code})"
        )
