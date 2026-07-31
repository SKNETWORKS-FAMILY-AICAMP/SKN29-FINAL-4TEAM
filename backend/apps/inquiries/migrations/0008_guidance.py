# Generated from the active T-005 Wave 2G contract on 2026-07-30.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


CONSTRAINT_NAME = "fk_guidance_ai_run_inquiry"
GUIDANCE_TABLE = "support_guidance"
AI_RUN_TABLE = "aiops_ai_run"
SQLITE_TRIGGER_NAMES = (
    "fk_guidance_context_child_insert",
    "fk_guidance_context_child_update",
    "fk_guidance_context_parent_update",
)


def add_guidance_ai_run_inquiry_fk(apps, schema_editor):
    """Enforce that an optional generation run has the same inquiry."""

    del apps
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            f"""
            ALTER TABLE {GUIDANCE_TABLE}
            ADD CONSTRAINT {CONSTRAINT_NAME}
            FOREIGN KEY (generated_by_ai_run_id, inquiry_id)
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
            BEFORE INSERT ON {GUIDANCE_TABLE}
            FOR EACH ROW
            WHEN NEW.generated_by_ai_run_id IS NOT NULL
             AND NOT EXISTS (
                SELECT 1
                FROM {AI_RUN_TABLE} parent
                WHERE parent.id = NEW.generated_by_ai_run_id
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
            BEFORE UPDATE OF generated_by_ai_run_id, inquiry_id
            ON {GUIDANCE_TABLE}
            FOR EACH ROW
            WHEN NEW.generated_by_ai_run_id IS NOT NULL
             AND NOT EXISTS (
                SELECT 1
                FROM {AI_RUN_TABLE} parent
                WHERE parent.id = NEW.generated_by_ai_run_id
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
                FROM {GUIDANCE_TABLE} child
                WHERE child.generated_by_ai_run_id = OLD.id
                  AND (
                      child.generated_by_ai_run_id <> NEW.id
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
        "Guidance context migration supports PostgreSQL and SQLite "
        f"only, not {vendor!r}."
    )


def remove_guidance_ai_run_inquiry_fk(apps, schema_editor):
    """Remove the vendor-specific composite context constraint."""

    del apps
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            f"""
            ALTER TABLE {GUIDANCE_TABLE}
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
        "Guidance context rollback supports PostgreSQL and SQLite "
        f"only, not {vendor!r}."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_promote_integer_primary_keys"),
        ("audit", "0002_airun"),
        ("inquiries", "0007_inquiryqa"),
    ]

    operations = [
        migrations.CreateModel(
            name="Guidance",
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
                    "guidance_version",
                    models.IntegerField(default=1),
                ),
                (
                    "review_status_code",
                    models.CharField(
                        default="PENDING",
                        max_length=40,
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                ("summary_text", models.TextField()),
                (
                    "safety_notice",
                    models.TextField(blank=True, null=True),
                ),
                (
                    "evidence_sufficiency_code",
                    models.CharField(max_length=40),
                ),
                (
                    "requires_consultation",
                    models.BooleanField(default=False),
                ),
                (
                    "reviewed_at",
                    models.DateTimeField(blank=True, null=True),
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
                        related_name="generated_guidance_versions",
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
                        related_name="guidance_versions",
                        to="inquiries.inquiry",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="reviewed_by_id",
                        db_index=False,
                        null=True,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="reviewed_guidance_versions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "support_guidance",
                "indexes": [
                    models.Index(
                        condition=models.Q(
                            ("review_status_code", "PENDING")
                        ),
                        fields=[
                            "review_status_code",
                            "created_at",
                        ],
                        name="ix_guidance_review_queue",
                    ),
                    models.Index(
                        fields=[
                            "generated_by_ai_run",
                            "inquiry",
                        ],
                        name="ix_guidance_ai_run",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "inquiry",
                            "guidance_version",
                        ),
                        name="ux_guidance_version",
                    ),
                    models.UniqueConstraint(
                        fields=("id", "inquiry"),
                        name="ux_guidance_id_inquiry",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("guidance_version__gt", 0)
                        ),
                        name="ck_guidance_version_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            review_status_code__regex=r".*\S.*"
                        ),
                        name=(
                            "ck_guidance_"
                            "review_status_nonempty"
                        ),
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            title__regex=r".*\S.*"
                        ),
                        name="ck_guidance_title_nonempty",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            summary_text__regex=r".*\S.*"
                        ),
                        name="ck_guidance_summary_nonempty",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            evidence_sufficiency_code__regex=(
                                r".*\S.*"
                            )
                        ),
                        name=(
                            "ck_guidance_"
                            "evidence_code_nonempty"
                        ),
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                (
                                    "reviewed_at__isnull",
                                    True,
                                ),
                                (
                                    "reviewed_by__isnull",
                                    True,
                                ),
                            ),
                            models.Q(
                                (
                                    "reviewed_at__isnull",
                                    False,
                                ),
                                (
                                    "reviewed_by__isnull",
                                    False,
                                ),
                            ),
                            _connector="OR",
                        ),
                        name="ck_guidance_review_pair",
                    ),
                ],
            },
        ),
        migrations.RunPython(
            add_guidance_ai_run_inquiry_fk,
            reverse_code=remove_guidance_ai_run_inquiry_fk,
        ),
    ]
