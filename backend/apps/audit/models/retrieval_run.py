"""RAG retrieval execution persistence for the active T-005 contract."""

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.common_codes.db_expressions import IsJSONObject
from common.models.base import TimestampedModel


class AIRetrievalRun(TimestampedModel):
    """Persist one reproducible retrieval execution for an AI run."""

    class DistanceMetric(models.TextChoices):
        COSINE = "COSINE", "Cosine"
        L2 = "L2", "L2"
        INNER_PRODUCT = "INNER_PRODUCT", "Inner product"

    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        RUNNING = "RUNNING", "Running"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        NO_EVIDENCE = "NO_EVIDENCE", "No evidence"
        FAILED = "FAILED", "Failed"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    ai_run = models.ForeignKey(
        "audit.AIRun",
        on_delete=models.PROTECT,
        related_name="retrieval_runs",
        db_column="ai_run_id",
        db_index=False,
    )
    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.PROTECT,
        related_name="retrieval_runs",
        db_column="inquiry_id",
        db_index=False,
    )
    query_text = models.TextField()
    query_sha256 = models.CharField(max_length=64)
    filter_payload = models.JSONField(default=dict, blank=True)
    retrieval_config_version = models.CharField(max_length=50)
    retrieval_config = models.JSONField(default=dict, blank=True)
    embedding_model = models.CharField(
        max_length=120,
        null=True,
        blank=True,
    )
    embedding_model_version = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )
    distance_metric_code = models.CharField(
        max_length=30,
        choices=DistanceMetric.choices,
        null=True,
        blank=True,
    )
    top_k = models.SmallIntegerField(default=5)
    reranker_name = models.CharField(
        max_length=120,
        null=True,
        blank=True,
    )
    status_code = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    no_evidence_reason = models.TextField(null=True, blank=True)
    error_code = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )
    error_message = models.TextField(null=True, blank=True)
    correlation_id = models.UUIDField()

    class Meta:
        db_table = "aiops_retrieval_run"
        constraints = [
            models.UniqueConstraint(
                fields=["id", "ai_run", "inquiry"],
                name="ux_retrieval_id_ai_inquiry",
            ),
            models.CheckConstraint(
                condition=Q(top_k__gte=1, top_k__lte=100),
                name="ck_retrieval_top_k",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status_code="NO_EVIDENCE")
                    | Q(no_evidence_reason__isnull=False)
                ),
                name="ck_retrieval_no_evidence",
            ),
            models.CheckConstraint(
                condition=(
                    Q(completed_at__isnull=True)
                    | Q(
                        started_at__isnull=False,
                        completed_at__gte=F("started_at"),
                    )
                ),
                name="ck_retrieval_time_order",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status_code="QUEUED",
                        started_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status_code="RUNNING",
                        started_at__isnull=False,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status_code__in=[
                            "SUCCEEDED",
                            "NO_EVIDENCE",
                            "FAILED",
                        ],
                        started_at__isnull=False,
                        completed_at__isnull=False,
                    )
                ),
                name="ck_retrieval_terminal",
            ),
            models.CheckConstraint(
                condition=Q(
                    query_sha256__regex=r"^[0-9a-f]{64}$"
                ),
                name="ck_retrieval_query_hash",
            ),
            models.CheckConstraint(
                condition=(
                    Q(IsJSONObject(F("filter_payload")))
                    & Q(IsJSONObject(F("retrieval_config")))
                ),
                name="ck_retrieval_json_objects",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        embedding_model__isnull=True,
                        embedding_model_version__isnull=True,
                        distance_metric_code__isnull=True,
                    )
                    | Q(
                        embedding_model__isnull=False,
                        embedding_model_version__isnull=False,
                        distance_metric_code__isnull=False,
                    )
                ),
                name="ck_retrieval_embedding_context",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status_code="FAILED")
                    | Q(
                        error_code__isnull=False,
                        error_message__isnull=False,
                    )
                ),
                name="ck_retrieval_failure",
            ),
            models.CheckConstraint(
                condition=(
                    Q(latency_ms__isnull=True)
                    | Q(latency_ms__gte=0)
                ),
                name="ck_retrieval_latency",
            ),
            models.CheckConstraint(
                condition=(
                    Q(distance_metric_code__isnull=True)
                    | Q(
                        distance_metric_code__in=[
                            "COSINE",
                            "L2",
                            "INNER_PRODUCT",
                        ]
                    )
                ),
                name=(
                    "ck_aiops_retrieval_run_"
                    "distance_metric_code_allowed"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    status_code__in=[
                        "QUEUED",
                        "RUNNING",
                        "SUCCEEDED",
                        "NO_EVIDENCE",
                        "FAILED",
                    ]
                ),
                name=(
                    "ck_aiops_retrieval_run_"
                    "status_code_allowed"
                ),
            ),
        ]
        indexes = [
            models.Index(
                fields=["ai_run", "inquiry"],
                name="ix_retrieval_ai_run",
            ),
            models.Index(
                fields=["inquiry", "-created_at"],
                name="ix_retrieval_inquiry",
            ),
            models.Index(
                fields=["status_code", "created_at"],
                name="ix_retrieval_status",
            ),
            models.Index(
                fields=["correlation_id"],
                name="ix_retrieval_correlation",
            ),
        ]

    def clean(self) -> None:
        """Validate the parent execution context before persistence."""

        super().clean()
        errors: dict[str, str] = {}

        if self.ai_run_id is not None:
            if (
                self.inquiry_id is not None
                and self.ai_run.inquiry_id != self.inquiry_id
            ):
                errors["inquiry"] = (
                    "검색 실행과 AI 실행은 같은 문의에 속해야 합니다."
                )
            if (
                self.correlation_id is not None
                and self.ai_run.correlation_id
                != self.correlation_id
            ):
                errors["correlation_id"] = (
                    "검색 실행은 AI 실행의 correlation_id를 "
                    "사용해야 합니다."
                )

        if not isinstance(self.filter_payload, dict):
            errors["filter_payload"] = (
                "filter_payload는 JSON object여야 합니다."
            )
        if not isinstance(self.retrieval_config, dict):
            errors["retrieval_config"] = (
                "retrieval_config는 JSON object여야 합니다."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.public_id} ({self.status_code})"
