# Generated manually from T-005 Physical Contract v1.2 on 2026-07-30.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0003_promote_integer_primary_keys"),
    ]

    operations = [
        migrations.CreateModel(
            name="IngestionBatch",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "id",
                    models.BigAutoField(
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "public_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                    ),
                ),
                ("batch_no", models.CharField(max_length=50)),
                (
                    "dataset_scope_code",
                    models.CharField(
                        choices=[
                            ("MVP", "MVP"),
                            ("EXPANSION", "Expansion"),
                        ],
                        default="MVP",
                        max_length=30,
                    ),
                ),
                (
                    "source_type_code",
                    models.CharField(
                        choices=[
                            ("LOCAL_FILE", "Local file"),
                            ("HTTP_DOWNLOAD", "HTTP download"),
                            ("WEB_PAGE", "Web page"),
                            ("MANUAL_UPLOAD", "Manual upload"),
                        ],
                        max_length=40,
                    ),
                ),
                (
                    "status_code",
                    models.CharField(
                        choices=[
                            ("QUEUED", "Queued"),
                            ("RUNNING", "Running"),
                            ("SUCCEEDED", "Succeeded"),
                            ("PARTIAL", "Partial"),
                            ("FAILED", "Failed"),
                        ],
                        default="QUEUED",
                        max_length=40,
                    ),
                ),
                (
                    "idempotency_key",
                    models.CharField(max_length=128),
                ),
                ("correlation_id", models.UUIDField()),
                (
                    "started_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "completed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("total_count", models.IntegerField(default=0)),
                ("success_count", models.IntegerField(default=0)),
                ("failure_count", models.IntegerField(default=0)),
                (
                    "pipeline_version",
                    models.CharField(max_length=50),
                ),
                (
                    "log_uri",
                    models.CharField(
                        blank=True,
                        max_length=500,
                        null=True,
                    ),
                ),
                (
                    "error_summary",
                    models.TextField(blank=True, null=True),
                ),
                (
                    "started_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="started_by_id",
                        db_index=False,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="started_ingestion_batches",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "knowledge_ingestion_batch",
                "indexes": [
                    models.Index(
                        fields=["status_code", "-created_at"],
                        name="ix_ingestion_batch_status",
                    ),
                    models.Index(
                        fields=["correlation_id"],
                        name="ix_ingestion_batch_correlation",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("batch_no",),
                        name="ux_ingestion_batch_no",
                    ),
                    models.UniqueConstraint(
                        fields=("idempotency_key",),
                        name="ux_ingestion_batch_idempotency",
                    ),
                    models.UniqueConstraint(
                        fields=("id", "dataset_scope_code"),
                        name="ux_ingestion_batch_id_scope",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(("total_count__gte", 0))
                            & models.Q(("success_count__gte", 0))
                            & models.Q(("failure_count__gte", 0))
                            & models.Q(
                                (
                                    "total_count__gte",
                                    models.F("success_count")
                                    + models.F("failure_count"),
                                )
                            )
                        ),
                        name="ck_ingestion_counts",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(("completed_at__isnull", True))
                            | models.Q(
                                (
                                    "completed_at__gte",
                                    models.F("started_at"),
                                ),
                                ("started_at__isnull", False),
                            )
                        ),
                        name="ck_ingestion_time_order",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(
                                ("completed_at__isnull", True),
                                ("started_at__isnull", True),
                                ("status_code", "QUEUED"),
                            )
                            | models.Q(
                                ("completed_at__isnull", True),
                                ("started_at__isnull", False),
                                ("status_code", "RUNNING"),
                            )
                            | models.Q(
                                ("completed_at__isnull", False),
                                ("failure_count", 0),
                                ("started_at__isnull", False),
                                ("status_code", "SUCCEEDED"),
                                (
                                    "success_count",
                                    models.F("total_count"),
                                ),
                            )
                            | models.Q(
                                ("completed_at__isnull", False),
                                ("failure_count__gt", 0),
                                ("started_at__isnull", False),
                                ("status_code", "PARTIAL"),
                                ("success_count__gt", 0),
                                (
                                    "total_count",
                                    models.F("success_count")
                                    + models.F("failure_count"),
                                ),
                            )
                            | models.Q(
                                ("completed_at__isnull", False),
                                (
                                    "failure_count",
                                    models.F("total_count"),
                                ),
                                ("started_at__isnull", False),
                                ("status_code", "FAILED"),
                                ("success_count", 0),
                            )
                        ),
                        name="ck_ingestion_terminal",
                    ),
                    models.CheckConstraint(
                        condition=(
                            ~models.Q(
                                (
                                    "status_code__in",
                                    ["PARTIAL", "FAILED"],
                                )
                            )
                            | models.Q(("error_summary__isnull", False))
                        ),
                        name="ck_ingestion_error_summary",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "dataset_scope_code__in",
                                ["MVP", "EXPANSION"],
                            )
                        ),
                        name=(
                            "ck_knowledge_ingestion_batch_"
                            "dataset_scope_code_allowed"
                        ),
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "source_type_code__in",
                                [
                                    "LOCAL_FILE",
                                    "HTTP_DOWNLOAD",
                                    "WEB_PAGE",
                                    "MANUAL_UPLOAD",
                                ],
                            )
                        ),
                        name=(
                            "ck_knowledge_ingestion_batch_"
                            "source_type_code_allowed"
                        ),
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "status_code__in",
                                [
                                    "QUEUED",
                                    "RUNNING",
                                    "SUCCEEDED",
                                    "PARTIAL",
                                    "FAILED",
                                ],
                            )
                        ),
                        name=(
                            "ck_knowledge_ingestion_batch_"
                            "status_code_allowed"
                        ),
                    ),
                ],
            },
        ),
    ]
