# Generated from the active T-005 Wave 2D contract on 2026-07-30.

import uuid

import apps.visits.models.technician_report
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


HANDOFF_TABLE = "support_handoff_report"
CONSULTATION_TABLE = "support_consultation"
AI_RUN_TABLE = "aiops_ai_run"
AI_RUN_CONSTRAINT = "fk_handoff_ai_run_inquiry"
CONSULTATION_CONTEXT_NAME = "fk_handoff_consultation_inquiry"
POSTGRES_CHILD_TRIGGER = "trg_handoff_consult_context_child"
POSTGRES_PARENT_TRIGGER = "trg_handoff_consult_context_parent"
POSTGRES_CHILD_FUNCTION = "check_handoff_consultation_inquiry"
POSTGRES_PARENT_FUNCTION = "protect_handoff_consultation_inquiry"
SQLITE_TRIGGER_NAMES = (
    "fk_handoff_consult_context_child_insert",
    "fk_handoff_consult_context_child_update",
    "fk_handoff_consult_context_parent_update",
    "fk_handoff_ai_context_child_insert",
    "fk_handoff_ai_context_child_update",
    "fk_handoff_ai_context_parent_update",
)


def add_handoff_context_integrity(apps, schema_editor):
    """Keep consultation and optional AI run in the report inquiry."""

    del apps
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            f"""
            ALTER TABLE {HANDOFF_TABLE}
            ADD CONSTRAINT {AI_RUN_CONSTRAINT}
            FOREIGN KEY (generated_by_ai_run_id, inquiry_id)
            REFERENCES {AI_RUN_TABLE} (id, inquiry_id)
            MATCH SIMPLE
            ON DELETE RESTRICT
            """
        )
        schema_editor.execute(
            f"""
            CREATE FUNCTION {POSTGRES_CHILD_FUNCTION}()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $function$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM {CONSULTATION_TABLE} parent
                    WHERE parent.id = NEW.consultation_id
                      AND parent.inquiry_id = NEW.inquiry_id
                ) THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '23503',
                        MESSAGE = '{CONSULTATION_CONTEXT_NAME}',
                        CONSTRAINT = '{CONSULTATION_CONTEXT_NAME}';
                END IF;
                RETURN NEW;
            END
            $function$
            """
        )
        schema_editor.execute(
            f"""
            CREATE TRIGGER {POSTGRES_CHILD_TRIGGER}
            BEFORE INSERT OR UPDATE OF consultation_id, inquiry_id
            ON {HANDOFF_TABLE}
            FOR EACH ROW
            EXECUTE FUNCTION {POSTGRES_CHILD_FUNCTION}()
            """
        )
        schema_editor.execute(
            f"""
            CREATE FUNCTION {POSTGRES_PARENT_FUNCTION}()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $function$
            BEGIN
                IF NEW.inquiry_id IS DISTINCT FROM OLD.inquiry_id
                   AND EXISTS (
                       SELECT 1
                       FROM {HANDOFF_TABLE} child
                       WHERE child.consultation_id = OLD.id
                   )
                THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '23503',
                        MESSAGE = '{CONSULTATION_CONTEXT_NAME}',
                        CONSTRAINT = '{CONSULTATION_CONTEXT_NAME}';
                END IF;
                RETURN NEW;
            END
            $function$
            """
        )
        schema_editor.execute(
            f"""
            CREATE TRIGGER {POSTGRES_PARENT_TRIGGER}
            BEFORE UPDATE OF inquiry_id
            ON {CONSULTATION_TABLE}
            FOR EACH ROW
            EXECUTE FUNCTION {POSTGRES_PARENT_FUNCTION}()
            """
        )
        return

    if vendor == "sqlite":
        (
            consult_insert,
            consult_update,
            consult_parent,
            ai_insert,
            ai_update,
            ai_parent,
        ) = SQLITE_TRIGGER_NAMES
        schema_editor.execute(
            f"""
            CREATE TRIGGER {consult_insert}
            BEFORE INSERT ON {HANDOFF_TABLE}
            FOR EACH ROW
            WHEN NOT EXISTS (
                SELECT 1
                FROM {CONSULTATION_TABLE} parent
                WHERE parent.id = NEW.consultation_id
                  AND parent.inquiry_id = NEW.inquiry_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    '{CONSULTATION_CONTEXT_NAME}'
                );
            END
            """
        )
        schema_editor.execute(
            f"""
            CREATE TRIGGER {consult_update}
            BEFORE UPDATE OF consultation_id, inquiry_id
            ON {HANDOFF_TABLE}
            FOR EACH ROW
            WHEN NOT EXISTS (
                SELECT 1
                FROM {CONSULTATION_TABLE} parent
                WHERE parent.id = NEW.consultation_id
                  AND parent.inquiry_id = NEW.inquiry_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    '{CONSULTATION_CONTEXT_NAME}'
                );
            END
            """
        )
        schema_editor.execute(
            f"""
            CREATE TRIGGER {consult_parent}
            BEFORE UPDATE OF inquiry_id
            ON {CONSULTATION_TABLE}
            FOR EACH ROW
            WHEN EXISTS (
                SELECT 1
                FROM {HANDOFF_TABLE} child
                WHERE child.consultation_id = OLD.id
                  AND child.inquiry_id <> NEW.inquiry_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    '{CONSULTATION_CONTEXT_NAME}'
                );
            END
            """
        )
        schema_editor.execute(
            f"""
            CREATE TRIGGER {ai_insert}
            BEFORE INSERT ON {HANDOFF_TABLE}
            FOR EACH ROW
            WHEN NEW.generated_by_ai_run_id IS NOT NULL
             AND NOT EXISTS (
                SELECT 1
                FROM {AI_RUN_TABLE} parent
                WHERE parent.id = NEW.generated_by_ai_run_id
                  AND parent.inquiry_id = NEW.inquiry_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    '{AI_RUN_CONSTRAINT}'
                );
            END
            """
        )
        schema_editor.execute(
            f"""
            CREATE TRIGGER {ai_update}
            BEFORE UPDATE OF generated_by_ai_run_id, inquiry_id
            ON {HANDOFF_TABLE}
            FOR EACH ROW
            WHEN NEW.generated_by_ai_run_id IS NOT NULL
             AND NOT EXISTS (
                SELECT 1
                FROM {AI_RUN_TABLE} parent
                WHERE parent.id = NEW.generated_by_ai_run_id
                  AND parent.inquiry_id = NEW.inquiry_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    '{AI_RUN_CONSTRAINT}'
                );
            END
            """
        )
        schema_editor.execute(
            f"""
            CREATE TRIGGER {ai_parent}
            BEFORE UPDATE OF inquiry_id
            ON {AI_RUN_TABLE}
            FOR EACH ROW
            WHEN EXISTS (
                SELECT 1
                FROM {HANDOFF_TABLE} child
                WHERE child.generated_by_ai_run_id = OLD.id
                  AND child.inquiry_id <> NEW.inquiry_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    '{AI_RUN_CONSTRAINT}'
                );
            END
            """
        )
        return

    raise RuntimeError(
        "Handoff report context migration supports PostgreSQL and "
        f"SQLite only, not {vendor!r}."
    )


def remove_handoff_context_integrity(apps, schema_editor):
    """Remove vendor-specific context enforcement on rollback."""

    del apps
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            f"""
            DROP TRIGGER IF EXISTS {POSTGRES_PARENT_TRIGGER}
            ON {CONSULTATION_TABLE}
            """
        )
        schema_editor.execute(
            f"""
            DROP TRIGGER IF EXISTS {POSTGRES_CHILD_TRIGGER}
            ON {HANDOFF_TABLE}
            """
        )
        schema_editor.execute(
            f"""
            DROP FUNCTION IF EXISTS {POSTGRES_PARENT_FUNCTION}()
            """
        )
        schema_editor.execute(
            f"""
            DROP FUNCTION IF EXISTS {POSTGRES_CHILD_FUNCTION}()
            """
        )
        schema_editor.execute(
            f"""
            ALTER TABLE {HANDOFF_TABLE}
            DROP CONSTRAINT IF EXISTS {AI_RUN_CONSTRAINT}
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
        "Handoff report context rollback supports PostgreSQL and "
        f"SQLite only, not {vendor!r}."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0003_airetrievalrun"),
        ("consultations", "0001_initial"),
        ("inquiries", "0006_symptomassessment"),
        ("visits", "0002_visitresult"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HandoffReport",
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
                (
                    "report_version",
                    models.PositiveIntegerField(default=1),
                ),
                (
                    "report_status_code",
                    models.CharField(max_length=40),
                ),
                ("product_summary", models.TextField()),
                ("symptom_summary", models.TextField()),
                ("action_summary", models.TextField()),
                ("risk_summary", models.TextField()),
                (
                    "evidence_summary",
                    models.TextField(blank=True, null=True),
                ),
                (
                    "priority_check_items",
                    models.JSONField(blank=True, default=list),
                ),
                (
                    "ai_draft",
                    models.TextField(blank=True, null=True),
                ),
                (
                    "consultant_final",
                    models.TextField(blank=True, null=True),
                ),
                (
                    "confirmed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "confirmed_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="confirmed_by_id",
                        db_index=False,
                        limit_choices_to={
                            "role_code": "CONSULTANT"
                        },
                        null=True,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="confirmed_handoff_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "consultation",
                    models.ForeignKey(
                        db_column="consultation_id",
                        db_index=False,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="handoff_reports",
                        to="consultations.consultation",
                    ),
                ),
                (
                    "generated_by_ai_run",
                    models.ForeignKey(
                        blank=True,
                        db_column="generated_by_ai_run_id",
                        db_index=False,
                        null=True,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="generated_handoff_reports",
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
                        related_name="handoff_reports",
                        to="inquiries.inquiry",
                    ),
                ),
            ],
            options={
                "db_table": "support_handoff_report",
                "indexes": [
                    models.Index(
                        fields=["consultation", "inquiry"],
                        name="ix_handoff_consultation",
                    ),
                    models.Index(
                        fields=[
                            "report_status_code",
                            "created_at",
                        ],
                        name="ix_handoff_status",
                    ),
                    models.Index(
                        fields=[
                            "generated_by_ai_run",
                            "inquiry",
                        ],
                        name="ix_handoff_ai_run",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("inquiry", "report_version"),
                        name="ux_handoff_report_version",
                    ),
                    models.UniqueConstraint(
                        fields=("id", "inquiry"),
                        name="ux_handoff_id_inquiry",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("report_version__gt", 0)
                        ),
                        name="ck_handoff_report_version",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("report_status_code", ""),
                            _negated=True,
                        ),
                        name="ck_handoff_status_nonempty",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("confirmed_at__isnull", True),
                                ("confirmed_by__isnull", True),
                            ),
                            models.Q(
                                ("confirmed_at__isnull", False),
                                ("confirmed_by__isnull", False),
                                (
                                    "consultant_final__isnull",
                                    False,
                                ),
                            ),
                            _connector="OR",
                        ),
                        name="ck_handoff_report_confirmation",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            apps.visits.models.technician_report.IsJSONArray(
                                models.F("priority_check_items")
                            )
                        ),
                        name="ck_handoff_priority_items_array",
                    ),
                ],
            },
        ),
        migrations.RunPython(
            add_handoff_context_integrity,
            remove_handoff_context_integrity,
        ),
    ]
