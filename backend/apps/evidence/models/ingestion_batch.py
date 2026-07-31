"""공식 지식 수집 파이프라인의 실행 배치 Model."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from common.models.base import TimestampedModel


class IngestionBatch(TimestampedModel):
    """수집·파싱·검수·적재 실행의 범위와 결과를 보존한다."""

    class DatasetScope(models.TextChoices):
        MVP = "MVP", "MVP"
        EXPANSION = "EXPANSION", "Expansion"

    class SourceType(models.TextChoices):
        LOCAL_FILE = "LOCAL_FILE", "Local file"
        HTTP_DOWNLOAD = "HTTP_DOWNLOAD", "HTTP download"
        WEB_PAGE = "WEB_PAGE", "Web page"
        MANUAL_UPLOAD = "MANUAL_UPLOAD", "Manual upload"

    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        RUNNING = "RUNNING", "Running"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        PARTIAL = "PARTIAL", "Partial"
        FAILED = "FAILED", "Failed"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    batch_no = models.CharField(max_length=50)
    dataset_scope_code = models.CharField(
        max_length=30,
        choices=DatasetScope.choices,
        default=DatasetScope.MVP,
    )
    source_type_code = models.CharField(
        max_length=40,
        choices=SourceType.choices,
    )
    status_code = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    idempotency_key = models.CharField(max_length=128)
    correlation_id = models.UUIDField()
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="started_ingestion_batches",
        db_column="started_by_id",
        db_index=False,
        null=True,
        blank=True,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    total_count = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)
    pipeline_version = models.CharField(max_length=50)
    log_uri = models.CharField(max_length=500, null=True, blank=True)
    error_summary = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "knowledge_ingestion_batch"
        constraints = [
            models.UniqueConstraint(
                fields=["batch_no"],
                name="ux_ingestion_batch_no",
            ),
            models.UniqueConstraint(
                fields=["idempotency_key"],
                name="ux_ingestion_batch_idempotency",
            ),
            models.UniqueConstraint(
                fields=["id", "dataset_scope_code"],
                name="ux_ingestion_batch_id_scope",
            ),
            models.CheckConstraint(
                condition=(
                    Q(total_count__gte=0)
                    & Q(success_count__gte=0)
                    & Q(failure_count__gte=0)
                    & Q(
                        total_count__gte=(
                            F("success_count") + F("failure_count")
                        )
                    )
                ),
                name="ck_ingestion_counts",
            ),
            models.CheckConstraint(
                condition=(
                    Q(completed_at__isnull=True)
                    | Q(
                        started_at__isnull=False,
                        completed_at__gte=F("started_at"),
                    )
                ),
                name="ck_ingestion_time_order",
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
                        status_code="SUCCEEDED",
                        started_at__isnull=False,
                        completed_at__isnull=False,
                        success_count=F("total_count"),
                        failure_count=0,
                    )
                    | Q(
                        status_code="PARTIAL",
                        started_at__isnull=False,
                        completed_at__isnull=False,
                        success_count__gt=0,
                        failure_count__gt=0,
                        total_count=(
                            F("success_count") + F("failure_count")
                        ),
                    )
                    | Q(
                        status_code="FAILED",
                        started_at__isnull=False,
                        completed_at__isnull=False,
                        success_count=0,
                        failure_count=F("total_count"),
                    )
                ),
                name="ck_ingestion_terminal",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status_code__in=["PARTIAL", "FAILED"])
                    | Q(error_summary__isnull=False)
                ),
                name="ck_ingestion_error_summary",
            ),
            models.CheckConstraint(
                condition=Q(
                    dataset_scope_code__in=["MVP", "EXPANSION"]
                ),
                name=(
                    "ck_knowledge_ingestion_batch_"
                    "dataset_scope_code_allowed"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    source_type_code__in=[
                        "LOCAL_FILE",
                        "HTTP_DOWNLOAD",
                        "WEB_PAGE",
                        "MANUAL_UPLOAD",
                    ]
                ),
                name=(
                    "ck_knowledge_ingestion_batch_"
                    "source_type_code_allowed"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    status_code__in=[
                        "QUEUED",
                        "RUNNING",
                        "SUCCEEDED",
                        "PARTIAL",
                        "FAILED",
                    ]
                ),
                name=(
                    "ck_knowledge_ingestion_batch_"
                    "status_code_allowed"
                ),
            ),
        ]
        indexes = [
            models.Index(
                fields=["status_code", "-created_at"],
                name="ix_ingestion_batch_status",
            ),
            models.Index(
                fields=["correlation_id"],
                name="ix_ingestion_batch_correlation",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.batch_no} ({self.status_code})"
