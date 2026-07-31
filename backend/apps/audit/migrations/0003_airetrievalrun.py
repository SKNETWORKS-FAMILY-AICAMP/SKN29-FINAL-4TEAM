# Generated from the active T-005 Wave 2A contract on 2026-07-30.

import uuid

import apps.common_codes.db_expressions
import django.db.models.deletion
from django.db import migrations, models


CONSTRAINT_NAME = "fk_retrieval_ai_run_context"
RETRIEVAL_TABLE = "aiops_retrieval_run"
AI_RUN_TABLE = "aiops_ai_run"
SQLITE_TRIGGER_NAMES = (
    "fk_retrieval_context_child_insert",
    "fk_retrieval_context_child_update",
    "fk_retrieval_context_parent_update",
)


def add_retrieval_context_fk(apps, schema_editor):
    """Enforce AI run, inquiry, and correlation context together."""

    del apps
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            f"""
            ALTER TABLE {RETRIEVAL_TABLE}
            ADD CONSTRAINT {CONSTRAINT_NAME}
            FOREIGN KEY (ai_run_id, inquiry_id, correlation_id)
            REFERENCES {AI_RUN_TABLE}
                (id, inquiry_id, correlation_id)
            MATCH SIMPLE
            ON DELETE RESTRICT
            """
        )
        return

    if vendor == "sqlite":
        child_insert, child_update, parent_update = (
            SQLITE_TRIGGER_NAMES
        )
        schema_editor.execute(
            f"""
            CREATE TRIGGER {child_insert}
            BEFORE INSERT ON {RETRIEVAL_TABLE}
            FOR EACH ROW
            WHEN NOT EXISTS (
                SELECT 1
                FROM {AI_RUN_TABLE} parent
                WHERE parent.id = NEW.ai_run_id
                  AND parent.inquiry_id = NEW.inquiry_id
                  AND parent.correlation_id = NEW.correlation_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    '{CONSTRAINT_NAME}'
                );
            END
            """
        )
        schema_editor.execute(
            f"""
            CREATE TRIGGER {child_update}
            BEFORE UPDATE OF
                ai_run_id,
                inquiry_id,
                correlation_id
            ON {RETRIEVAL_TABLE}
            FOR EACH ROW
            WHEN NOT EXISTS (
                SELECT 1
                FROM {AI_RUN_TABLE} parent
                WHERE parent.id = NEW.ai_run_id
                  AND parent.inquiry_id = NEW.inquiry_id
                  AND parent.correlation_id = NEW.correlation_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    '{CONSTRAINT_NAME}'
                );
            END
            """
        )
        schema_editor.execute(
            f"""
            CREATE TRIGGER {parent_update}
            BEFORE UPDATE OF inquiry_id, correlation_id
            ON {AI_RUN_TABLE}
            FOR EACH ROW
            WHEN EXISTS (
                SELECT 1
                FROM {RETRIEVAL_TABLE} child
                WHERE child.ai_run_id = OLD.id
                  AND (
                      child.inquiry_id <> NEW.inquiry_id
                      OR child.correlation_id <> NEW.correlation_id
                  )
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    '{CONSTRAINT_NAME}'
                );
            END
            """
        )
        return

    raise RuntimeError(
        "AIRetrievalRun context migration supports PostgreSQL and "
        f"SQLite only, not {vendor!r}."
    )


def remove_retrieval_context_fk(apps, schema_editor):
    """Remove the vendor-specific composite context constraint."""

    del apps
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            f"""
            ALTER TABLE {RETRIEVAL_TABLE}
            DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}
            """
        )
        return

    if vendor == "sqlite":
        for trigger_name in SQLITE_TRIGGER_NAMES:
            schema_editor.execute(
                f"DROP TRIGGER IF EXISTS {trigger_name}"
            )
        return

    raise RuntimeError(
        "AIRetrievalRun context rollback supports PostgreSQL and "
        f"SQLite only, not {vendor!r}."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0002_airun"),
        ("inquiries", "0005_inquiry_ux_inquiry_id_subscription"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIRetrievalRun",
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
                ("query_text", models.TextField()),
                (
                    "query_sha256",
                    models.CharField(max_length=64),
                ),
                (
                    "filter_payload",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "retrieval_config_version",
                    models.CharField(max_length=50),
                ),
                (
                    "retrieval_config",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "embedding_model",
                    models.CharField(
                        blank=True,
                        max_length=120,
                        null=True,
                    ),
                ),
                (
                    "embedding_model_version",
                    models.CharField(
                        blank=True,
                        max_length=80,
                        null=True,
                    ),
                ),
                (
                    "distance_metric_code",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("COSINE", "Cosine"),
                            ("L2", "L2"),
                            (
                                "INNER_PRODUCT",
                                "Inner product",
                            ),
                        ],
                        max_length=30,
                        null=True,
                    ),
                ),
                (
                    "top_k",
                    models.SmallIntegerField(default=5),
                ),
                (
                    "reranker_name",
                    models.CharField(
                        blank=True,
                        max_length=120,
                        null=True,
                    ),
                ),
                (
                    "status_code",
                    models.CharField(
                        choices=[
                            ("QUEUED", "Queued"),
                            ("RUNNING", "Running"),
                            ("SUCCEEDED", "Succeeded"),
                            ("NO_EVIDENCE", "No evidence"),
                            ("FAILED", "Failed"),
                        ],
                        default="QUEUED",
                        max_length=40,
                    ),
                ),
                (
                    "started_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "completed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "latency_ms",
                    models.IntegerField(blank=True, null=True),
                ),
                (
                    "no_evidence_reason",
                    models.TextField(blank=True, null=True),
                ),
                (
                    "error_code",
                    models.CharField(
                        blank=True,
                        max_length=80,
                        null=True,
                    ),
                ),
                (
                    "error_message",
                    models.TextField(blank=True, null=True),
                ),
                ("correlation_id", models.UUIDField()),
                (
                    "ai_run",
                    models.ForeignKey(
                        db_column="ai_run_id",
                        db_index=False,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="retrieval_runs",
                        to="audit.airun",
                    ),
                ),
                (
                    "inquiry",
                    models.ForeignKey(
                        db_column="inquiry_id",
                        db_index=False,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="retrieval_runs",
                        to="inquiries.inquiry",
                    ),
                ),
            ],
            options={
                "db_table": "aiops_retrieval_run",
                "indexes": [
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
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("id", "ai_run", "inquiry"),
                        name="ux_retrieval_id_ai_inquiry",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("top_k__gte", 1),
                            ("top_k__lte", 100),
                        ),
                        name="ck_retrieval_top_k",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("status_code", "NO_EVIDENCE"),
                                _negated=True,
                            ),
                            ("no_evidence_reason__isnull", False),
                            _connector="OR",
                        ),
                        name="ck_retrieval_no_evidence",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("completed_at__isnull", True),
                            models.Q(
                                (
                                    "completed_at__gte",
                                    models.F("started_at"),
                                ),
                                ("started_at__isnull", False),
                            ),
                            _connector="OR",
                        ),
                        name="ck_retrieval_time_order",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("completed_at__isnull", True),
                                ("started_at__isnull", True),
                                ("status_code", "QUEUED"),
                            ),
                            models.Q(
                                ("completed_at__isnull", True),
                                ("started_at__isnull", False),
                                ("status_code", "RUNNING"),
                            ),
                            models.Q(
                                ("completed_at__isnull", False),
                                ("started_at__isnull", False),
                                (
                                    "status_code__in",
                                    [
                                        "SUCCEEDED",
                                        "NO_EVIDENCE",
                                        "FAILED",
                                    ],
                                ),
                            ),
                            _connector="OR",
                        ),
                        name="ck_retrieval_terminal",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "query_sha256__regex",
                                "^[0-9a-f]{64}$",
                            )
                        ),
                        name="ck_retrieval_query_hash",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            apps.common_codes.db_expressions.IsJSONObject(
                                models.F("filter_payload")
                            ),
                            apps.common_codes.db_expressions.IsJSONObject(
                                models.F("retrieval_config")
                            ),
                        ),
                        name="ck_retrieval_json_objects",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                (
                                    "distance_metric_code__isnull",
                                    True,
                                ),
                                (
                                    "embedding_model__isnull",
                                    True,
                                ),
                                (
                                    "embedding_model_version__isnull",
                                    True,
                                ),
                            ),
                            models.Q(
                                (
                                    "distance_metric_code__isnull",
                                    False,
                                ),
                                (
                                    "embedding_model__isnull",
                                    False,
                                ),
                                (
                                    "embedding_model_version__isnull",
                                    False,
                                ),
                            ),
                            _connector="OR",
                        ),
                        name="ck_retrieval_embedding_context",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("status_code", "FAILED"),
                                _negated=True,
                            ),
                            models.Q(
                                ("error_code__isnull", False),
                                ("error_message__isnull", False),
                            ),
                            _connector="OR",
                        ),
                        name="ck_retrieval_failure",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("latency_ms__isnull", True),
                            ("latency_ms__gte", 0),
                            _connector="OR",
                        ),
                        name="ck_retrieval_latency",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "distance_metric_code__isnull",
                                True,
                            ),
                            (
                                "distance_metric_code__in",
                                [
                                    "COSINE",
                                    "L2",
                                    "INNER_PRODUCT",
                                ],
                            ),
                            _connector="OR",
                        ),
                        name=(
                            "ck_aiops_retrieval_run_"
                            "distance_metric_code_allowed"
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
                                    "NO_EVIDENCE",
                                    "FAILED",
                                ],
                            )
                        ),
                        name=(
                            "ck_aiops_retrieval_run_"
                            "status_code_allowed"
                        ),
                    ),
                ],
            },
        ),
        migrations.RunPython(
            add_retrieval_context_fk,
            reverse_code=remove_retrieval_context_fk,
        ),
    ]
