"""Immutable, synthetic reference scenarios for later AI evaluation/matching."""

from __future__ import annotations

import uuid

from django.db import models
from django.db.models import Q

from common.models.base import TimestampedModel


class ReferenceScenario(TimestampedModel):
    """A versioned decision oracle that is not read by the runtime yet.

    The table deliberately does not point to ``Inquiry``.  An inquiry is a
    customer-owned runtime aggregate, whereas this row is synthetic reference
    data.  Runtime and prompt use remain disabled until a separately reviewed
    matcher is introduced.
    """

    class RiskLevel(models.TextChoices):
        GENERAL = "general", "General"
        CAUTION = "caution", "Caution"
        DANGER = "danger", "Danger"

    class ExpectedRoute(models.TextChoices):
        AI_GUIDANCE = "AI_GUIDANCE", "AI guidance"
        HUMAN_REVIEW = "HUMAN_REVIEW", "Human review"
        EMERGENCY_ESCALATION = (
            "EMERGENCY_ESCALATION",
            "Emergency escalation",
        )

    class PublicationGate(models.TextChoices):
        AUTO_GUIDANCE_ELIGIBLE = (
            "AUTO_GUIDANCE_ELIGIBLE",
            "Auto guidance eligible",
        )
        HUMAN_APPROVAL_REQUIRED = (
            "HUMAN_APPROVAL_REQUIRED",
            "Human approval required",
        )
        SAFETY_ESCALATION_ONLY = (
            "SAFETY_ESCALATION_ONLY",
            "Safety escalation only",
        )

    class UsageGuidanceStatus(models.TextChoices):
        NORMAL = "NORMAL", "Normal"
        PARTIAL_STOP = "PARTIAL_STOP", "Partial stop"
        TOTAL_STOP = "TOTAL_STOP", "Total stop"

    class EvidenceReadiness(models.TextChoices):
        SCENARIO_GROUP_VERIFIED = (
            "SCENARIO_GROUP_VERIFIED",
            "Scenario evidence group verified",
        )
        TOPIC_GROUP_SELECTION_PENDING = (
            "TOPIC_GROUP_SELECTION_PENDING",
            "Topic group needs scenario selection",
        )
        SOURCE_PAGE_ONLY = "SOURCE_PAGE_ONLY", "Verified source page only"

    class RuntimeUse(models.TextChoices):
        REFERENCE_ONLY = "REFERENCE_ONLY", "Reference only"

    class TrainingUse(models.TextChoices):
        PROHIBITED = "PROHIBITED", "Prohibited"

    class CurationStatus(models.TextChoices):
        CANDIDATE = "CANDIDATE", "Candidate"

    class SourcePolicy(models.TextChoices):
        MVP_SOURCE_REFERENCE = (
            "MVP_SOURCE_REFERENCE",
            "MVP source reference",
        )
        EXPANSION_REFERENCE_ONLY = (
            "EXPANSION_REFERENCE_ONLY",
            "Expansion reference only",
        )

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    scenario_id = models.CharField(max_length=64)
    catalog_version = models.CharField(max_length=40)
    exact_model_code = models.CharField(max_length=40)
    model_family = models.CharField(max_length=40)
    risk_level = models.CharField(max_length=20, choices=RiskLevel.choices)
    title = models.CharField(max_length=180)
    customer_utterance = models.TextField()
    topic_code = models.CharField(max_length=80)
    context_facts = models.JSONField(default=list)

    source_document_id = models.CharField(max_length=100)
    source_policy = models.CharField(max_length=30, choices=SourcePolicy.choices)
    manual_page_refs = models.JSONField(default=list)
    evidence_group_ids = models.JSONField(default=list, blank=True)
    evidence_readiness = models.CharField(
        max_length=30,
        choices=EvidenceReadiness.choices,
    )

    expected_route = models.CharField(
        max_length=30,
        choices=ExpectedRoute.choices,
    )
    expected_requires_consultation = models.BooleanField()
    expected_publication_gate = models.CharField(
        max_length=30,
        choices=PublicationGate.choices,
    )
    expected_usage_guidance_status = models.CharField(
        max_length=30,
        choices=UsageGuidanceStatus.choices,
    )
    expected_reason = models.TextField()
    response_outline = models.JSONField(default=list)

    runtime_use = models.CharField(
        max_length=20,
        choices=RuntimeUse.choices,
        default=RuntimeUse.REFERENCE_ONLY,
    )
    training_use = models.CharField(
        max_length=20,
        choices=TrainingUse.choices,
        default=TrainingUse.PROHIBITED,
    )
    curation_status = models.CharField(
        max_length=20,
        choices=CurationStatus.choices,
        default=CurationStatus.CANDIDATE,
    )
    is_runtime_enabled = models.BooleanField(default=False)
    data_classification = models.CharField(max_length=20, default="synthetic")
    source_record_sha256 = models.CharField(max_length=64)
    source_catalog_sha256 = models.CharField(max_length=64)

    class Meta:
        db_table = "ai_reference_scenario"
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    exact_model_code__in=[
                        "WPUJAC104DWH",
                        "WPUIAC425SNW",
                        "WPUIAC606SNW",
                    ]
                ),
                name="ck_ref_scenario_model_code",
            ),
            models.CheckConstraint(
                condition=Q(risk_level__in=["general", "caution", "danger"]),
                name="ck_ref_scenario_risk",
            ),
            models.CheckConstraint(
                condition=Q(
                    runtime_use="REFERENCE_ONLY",
                    training_use="PROHIBITED",
                    curation_status="CANDIDATE",
                    is_runtime_enabled=False,
                    data_classification="synthetic",
                ),
                name="ck_ref_scenario_nonruntime",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        risk_level="general",
                        expected_route="AI_GUIDANCE",
                        expected_requires_consultation=False,
                        expected_publication_gate="AUTO_GUIDANCE_ELIGIBLE",
                        expected_usage_guidance_status="NORMAL",
                    )
                    | Q(
                        risk_level="caution",
                        expected_route="HUMAN_REVIEW",
                        expected_publication_gate="HUMAN_APPROVAL_REQUIRED",
                        expected_usage_guidance_status="PARTIAL_STOP",
                    )
                    | Q(
                        risk_level="danger",
                        expected_route="EMERGENCY_ESCALATION",
                        expected_requires_consultation=True,
                        expected_publication_gate="SAFETY_ESCALATION_ONLY",
                        expected_usage_guidance_status="TOTAL_STOP",
                    )
                ),
                name="ck_ref_scenario_release_oracle",
            ),
            models.UniqueConstraint(
                fields=["catalog_version", "scenario_id"],
                name="uq_ref_scenario_version_id",
            ),
        ]
        indexes = [
            models.Index(
                fields=["catalog_version", "exact_model_code", "risk_level"],
                name="ix_ref_scenario_matrix",
            ),
            models.Index(
                fields=["runtime_use", "is_runtime_enabled"],
                name="ix_ref_scenario_runtime",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.scenario_id} ({self.risk_level})"
