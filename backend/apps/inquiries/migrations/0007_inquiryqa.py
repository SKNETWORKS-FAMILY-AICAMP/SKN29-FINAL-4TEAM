# Generated from the active T-005 Wave 2F contract on 2026-07-30.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


CONSTRAINT_NAME = "fk_inquiry_qa_ai_run_inquiry"
QA_TABLE = "support_inquiry_qa"
AI_RUN_TABLE = "aiops_ai_run"
SQLITE_TRIGGER_NAMES = (
    "fk_inquiry_qa_context_child_insert",
    "fk_inquiry_qa_context_child_update",
    "fk_inquiry_qa_context_parent_update",
)


def add_inquiry_qa_ai_run_inquiry_fk(apps, schema_editor):
    """Enforce that an optional source AI run has the same inquiry."""

    del apps
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            f"""
            ALTER TABLE {QA_TABLE}
            ADD CONSTRAINT {CONSTRAINT_NAME}
            FOREIGN KEY (source_ai_run_id, inquiry_id)
            REFERENCES {AI_RUN_TABLE} (id, inquiry_id)
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
            BEFORE INSERT ON {QA_TABLE}
            FOR EACH ROW
            WHEN NEW.source_ai_run_id IS NOT NULL
             AND NOT EXISTS (
                SELECT 1
                FROM {AI_RUN_TABLE} parent
                WHERE parent.id = NEW.source_ai_run_id
                  AND parent.inquiry_id = NEW.inquiry_id
            )
            BEGIN
                SELECT RAISE(ABORT, '{CONSTRAINT_NAME}');
            END
            """
        )
        schema_editor.execute(
            f"""
            CREATE TRIGGER {child_update}
            BEFORE UPDATE OF source_ai_run_id, inquiry_id
            ON {QA_TABLE}
            FOR EACH ROW
            WHEN NEW.source_ai_run_id IS NOT NULL
             AND NOT EXISTS (
                SELECT 1
                FROM {AI_RUN_TABLE} parent
                WHERE parent.id = NEW.source_ai_run_id
                  AND parent.inquiry_id = NEW.inquiry_id
            )
            BEGIN
                SELECT RAISE(ABORT, '{CONSTRAINT_NAME}');
            END
            """
        )
        schema_editor.execute(
            f"""
            CREATE TRIGGER {parent_update}
            BEFORE UPDATE OF id, inquiry_id
            ON {AI_RUN_TABLE}
            FOR EACH ROW
            WHEN EXISTS (
                SELECT 1
                FROM {QA_TABLE} child
                WHERE child.source_ai_run_id = OLD.id
                  AND (
                      child.source_ai_run_id <> NEW.id
                      OR child.inquiry_id <> NEW.inquiry_id
                  )
            )
            BEGIN
                SELECT RAISE(ABORT, '{CONSTRAINT_NAME}');
            END
            """
        )
        return

    raise RuntimeError(
        "InquiryQA context migration supports PostgreSQL and SQLite "
        f"only, not {vendor!r}."
    )


def remove_inquiry_qa_ai_run_inquiry_fk(apps, schema_editor):
    """Remove the vendor-specific composite context constraint."""

    del apps
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            f"""
            ALTER TABLE {QA_TABLE}
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
        "InquiryQA context rollback supports PostgreSQL and SQLite "
        f"only, not {vendor!r}."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_promote_integer_primary_keys"),
        ("audit", "0002_airun"),
        ("inquiries", "0006_symptomassessment"),
    ]

    operations = [
        migrations.CreateModel(
            name="InquiryQA",
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
                    "sequence_no",
                    models.PositiveSmallIntegerField(),
                ),
                (
                    "question_code",
                    models.CharField(
                        blank=True,
                        max_length=80,
                        null=True,
                    ),
                ),
                ("question_text", models.TextField()),
                (
                    "answer_type_code",
                    models.CharField(
                        default="FREE_TEXT",
                        max_length=40,
                    ),
                ),
                (
                    "answer_text",
                    models.TextField(blank=True, null=True),
                ),
                (
                    "answer_payload",
                    models.JSONField(blank=True, null=True),
                ),
                (
                    "asked_by_type_code",
                    models.CharField(
                        default="RULE",
                        max_length=40,
                    ),
                ),
                (
                    "answered_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "answered_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="answered_by_id",
                        db_index=False,
                        null=True,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name=(
                            "answered_inquiry_qa_entries"
                        ),
                        to=settings.AUTH_USER_MODEL,
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
                        related_name="qa_entries",
                        to="inquiries.inquiry",
                    ),
                ),
                (
                    "source_ai_run",
                    models.ForeignKey(
                        blank=True,
                        db_column="source_ai_run_id",
                        db_index=False,
                        null=True,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name=(
                            "generated_inquiry_qa_entries"
                        ),
                        to="audit.airun",
                    ),
                ),
            ],
            options={
                "db_table": "support_inquiry_qa",
                "indexes": [
                    models.Index(
                        fields=["inquiry", "answered_at"],
                        name="ix_inquiry_qa_answered",
                    ),
                    models.Index(
                        fields=[
                            "source_ai_run",
                            "inquiry",
                        ],
                        name="ix_inquiry_qa_ai_run",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("inquiry", "sequence_no"),
                        name="ux_inquiry_qa_sequence",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(
                            ("question_code__isnull", False)
                        ),
                        fields=("inquiry", "question_code"),
                        name="ux_inquiry_qa_question",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("answered_at__isnull", True),
                            models.Q(
                                ("answered_by__isnull", False),
                                models.Q(
                                    (
                                        "answer_text__isnull",
                                        False,
                                    ),
                                    (
                                        "answer_payload__isnull",
                                        False,
                                    ),
                                    _connector="OR",
                                ),
                            ),
                            _connector="OR",
                        ),
                        name=(
                            "ck_inquiry_qa_"
                            "answer_consistency"
                        ),
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("sequence_no__gt", 0)
                        ),
                        name="ck_inquiry_qa_sequence",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("asked_by_type_code", "AI"),
                                (
                                    "source_ai_run__isnull",
                                    False,
                                ),
                            ),
                            models.Q(
                                models.Q(
                                    (
                                        "asked_by_type_code",
                                        "AI",
                                    ),
                                    _negated=True,
                                ),
                                (
                                    "source_ai_run__isnull",
                                    True,
                                ),
                            ),
                            _connector="OR",
                        ),
                        name="ck_inquiry_qa_ai_origin",
                    ),
                ],
            },
        ),
        migrations.RunPython(
            add_inquiry_qa_ai_run_inquiry_fk,
            reverse_code=(
                remove_inquiry_qa_ai_run_inquiry_fk
            ),
        ),
    ]
