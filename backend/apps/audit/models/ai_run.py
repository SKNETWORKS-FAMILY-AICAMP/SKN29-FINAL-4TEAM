"""AI execution persistence aligned with the active T-005 contract."""

from __future__ import annotations

import uuid

from django.db import models
from django.db.models import F, Q

from common.models.base import TimestampedModel


class IsJSONObject(models.Func):
    """Return whether a JSON expression is an object on supported DBs."""

    output_field = models.BooleanField()

    def as_postgresql(self, compiler, connection, **extra_context):
        return super().as_sql(
            compiler,
            connection,
            template="jsonb_typeof(%(expressions)s) = 'object'",
            **extra_context,
        )

    def as_sqlite(self, compiler, connection, **extra_context):
        return super().as_sql(
            compiler,
            connection,
            template="JSON_TYPE(%(expressions)s) = 'object'",
            **extra_context,
        )


class IsJSONArray(models.Func):
    """Return whether a JSON expression is an array on supported DBs."""

    output_field = models.BooleanField()

    def as_postgresql(self, compiler, connection, **extra_context):
        return super().as_sql(
            compiler,
            connection,
            template="jsonb_typeof(%(expressions)s) = 'array'",
            **extra_context,
        )

    def as_sqlite(self, compiler, connection, **extra_context):
        return super().as_sql(
            compiler,
            connection,
            template="JSON_TYPE(%(expressions)s) = 'array'",
            **extra_context,
        )


class IsNonEmptyJSONArray(models.Func):
    """Return whether a JSON array has at least one item."""

    output_field = models.BooleanField()

    def as_postgresql(self, compiler, connection, **extra_context):
        return super().as_sql(
            compiler,
            connection,
            template="jsonb_array_length(%(expressions)s) > 0",
            **extra_context,
        )

    def as_sqlite(self, compiler, connection, **extra_context):
        return super().as_sql(
            compiler,
            connection,
            template="JSON_ARRAY_LENGTH(%(expressions)s) > 0",
            **extra_context,
        )


class AIRun(TimestampedModel):
    """Persist one reproducible, contract-validated AI execution."""

    class TaskType(models.TextChoices):
        ANALYZE_SYMPTOM = (
            "ANALYZE_SYMPTOM",
            "Analyze symptom pipeline",
        )
        STRUCTURE_SYMPTOM = (
            "STRUCTURE_SYMPTOM",
            "Structure symptom",
        )
        GENERATE_QUESTIONS = (
            "GENERATE_QUESTIONS",
            "Generate questions",
        )
        ASSESS_RISK = "ASSESS_RISK", "Assess risk"
        RETRIEVE_EVIDENCE = (
            "RETRIEVE_EVIDENCE",
            "Retrieve evidence",
        )
        GENERATE_GUIDANCE = (
            "GENERATE_GUIDANCE",
            "Generate guidance",
        )
        SUMMARIZE_CONSULTATION = (
            "SUMMARIZE_CONSULTATION",
            "Summarize consultation",
        )
        DRAFT_HANDOFF = "DRAFT_HANDOFF", "Draft handoff"

    class SchemaValidationStatus(models.TextChoices):
        NOT_RUN = "NOT_RUN", "Not run"
        PASSED = "PASSED", "Passed"
        FAILED = "FAILED", "Failed"

    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        RUNNING = "RUNNING", "Running"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        NO_EVIDENCE = "NO_EVIDENCE", "No evidence"
        FAILED = "FAILED", "Failed"
        TIMED_OUT = "TIMED_OUT", "Timed out"
        RETRYING = "RETRYING", "Retrying"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.PROTECT,
        related_name="ai_runs",
        db_column="inquiry_id",
        db_index=False,
    )
    task_type_code = models.CharField(
        max_length=50,
        choices=TaskType.choices,
    )
    request_schema_version = models.CharField(
        max_length=30,
        default="v1",
    )
    response_schema_version = models.CharField(max_length=30)
    model_provider = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )
    model_name = models.CharField(
        max_length=120,
        null=True,
        blank=True,
    )
    model_config_version = models.CharField(
        max_length=64,
        default="v1",
    )
    model_config = models.JSONField(default=dict, blank=True)
    prompt_version = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    input_payload = models.JSONField(default=dict, blank=True)
    input_sha256 = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=128)
    raw_output_text = models.TextField(null=True, blank=True)
    validated_output_payload = models.JSONField(
        null=True,
        blank=True,
    )
    schema_validation_status_code = models.CharField(
        max_length=40,
        choices=SchemaValidationStatus.choices,
        default=SchemaValidationStatus.NOT_RUN,
    )
    schema_validation_errors = models.JSONField(
        default=list,
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
    input_tokens = models.IntegerField(null=True, blank=True)
    output_tokens = models.IntegerField(null=True, blank=True)
    error_code = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )
    error_message = models.TextField(null=True, blank=True)
    retry_count = models.SmallIntegerField(default=0)
    correlation_id = models.UUIDField()

    class Meta:
        db_table = "aiops_ai_run"
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_key"],
                name="ux_ai_run_idempotency",
            ),
            models.UniqueConstraint(
                fields=["id", "inquiry"],
                name="ux_ai_run_id_inquiry",
            ),
            models.UniqueConstraint(
                fields=["id", "inquiry", "correlation_id"],
                name="ux_ai_run_id_inquiry_correlation",
            ),
            models.CheckConstraint(
                condition=Q(
                    IsJSONArray(F("schema_validation_errors"))
                ),
                name="ck_ai_run_schema_errors_array",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status_code="SUCCEEDED")
                    | Q(
                        schema_validation_status_code="PASSED",
                        validated_output_payload__isnull=False,
                        completed_at__isnull=False,
                    )
                ),
                name="ck_ai_run_success",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(
                        status_code__in=[
                            "FAILED",
                            "TIMED_OUT",
                        ]
                    )
                    | Q(
                        error_code__isnull=False,
                        completed_at__isnull=False,
                    )
                ),
                name="ck_ai_run_failure",
            ),
            models.CheckConstraint(
                condition=(
                    Q(completed_at__isnull=True)
                    | Q(
                        status_code="CANCELLED",
                        started_at__isnull=True,
                        completed_at__gte=F("created_at"),
                    )
                    | Q(
                        started_at__isnull=False,
                        completed_at__gte=F("started_at"),
                    )
                ),
                name="ck_ai_run_time_order",
            ),
            models.CheckConstraint(
                condition=Q(
                    input_sha256__regex=r"^[0-9a-f]{64}$"
                ),
                name="ck_ai_run_input_hash",
            ),
            models.CheckConstraint(
                condition=Q(IsJSONObject(F("model_config"))),
                name="ck_ai_run_model_config",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status_code="NO_EVIDENCE")
                    | Q(
                        schema_validation_status_code="PASSED",
                        completed_at__isnull=False,
                        validated_output_payload__isnull=False,
                    )
                ),
                name="ck_ai_run_no_evidence",
            ),
            models.CheckConstraint(
                condition=(
                    Q(retry_count__gte=0)
                    & (
                        Q(latency_ms__isnull=True)
                        | Q(latency_ms__gte=0)
                    )
                    & (
                        Q(input_tokens__isnull=True)
                        | Q(input_tokens__gte=0)
                    )
                    & (
                        Q(output_tokens__isnull=True)
                        | Q(output_tokens__gte=0)
                    )
                ),
                name="ck_ai_run_nonnegative_metrics",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status_code__in=[
                            "QUEUED",
                            "CANCELLED",
                        ],
                        started_at__isnull=True,
                    )
                    | Q(
                        model_provider__isnull=False,
                        model_name__isnull=False,
                        prompt_version__isnull=False,
                    )
                ),
                name="ck_ai_run_reproducibility",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status_code="QUEUED",
                        started_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status_code__in=[
                            "RUNNING",
                            "RETRYING",
                        ],
                        started_at__isnull=False,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status_code__in=[
                            "SUCCEEDED",
                            "NO_EVIDENCE",
                            "FAILED",
                            "TIMED_OUT",
                        ],
                        started_at__isnull=False,
                        completed_at__isnull=False,
                    )
                    | Q(
                        status_code="CANCELLED",
                        completed_at__isnull=False,
                    )
                ),
                name="ck_ai_run_lifecycle",
            ),
            models.CheckConstraint(
                condition=(
                    Q(IsJSONObject(F("input_payload")))
                    & (
                        Q(validated_output_payload__isnull=True)
                        | Q(
                            IsJSONObject(
                                F("validated_output_payload")
                            )
                        )
                    )
                ),
                name="ck_ai_run_json_objects",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(
                        schema_validation_status_code="FAILED"
                    )
                    | (
                        Q(raw_output_text__isnull=False)
                        & Q(
                            IsNonEmptyJSONArray(
                                F("schema_validation_errors")
                            )
                        )
                    )
                ),
                name="ck_ai_run_schema_failure",
            ),
            models.CheckConstraint(
                condition=Q(
                    task_type_code__in=[
                        "ANALYZE_SYMPTOM",
                        "STRUCTURE_SYMPTOM",
                        "GENERATE_QUESTIONS",
                        "ASSESS_RISK",
                        "RETRIEVE_EVIDENCE",
                        "GENERATE_GUIDANCE",
                        "SUMMARIZE_CONSULTATION",
                        "DRAFT_HANDOFF",
                    ]
                ),
                name="ck_aiops_ai_run_task_type_code_allowed",
            ),
            models.CheckConstraint(
                condition=Q(
                    schema_validation_status_code__in=[
                        "NOT_RUN",
                        "PASSED",
                        "FAILED",
                    ]
                ),
                name=(
                    "ck_aiops_ai_run_"
                    "schema_validation_status_code_allowed"
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
                        "TIMED_OUT",
                        "RETRYING",
                        "CANCELLED",
                    ]
                ),
                name="ck_aiops_ai_run_status_code_allowed",
            ),
        ]
        indexes = [
            models.Index(
                fields=["inquiry", "task_type_code", "-created_at"],
                name="ix_ai_run_inquiry_task",
            ),
            models.Index(
                fields=["status_code", "created_at"],
                name="ix_ai_run_status",
            ),
            models.Index(
                fields=["correlation_id"],
                name="ix_ai_run_correlation",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.public_id} ({self.status_code})"
