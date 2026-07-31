# Generated from the active T-005 Wave 2B contract on 2026-07-30.

import uuid

import apps.common_codes.db_expressions
import django.db.models.deletion
from django.db import migrations, models


CONSTRAINT_NAME = "fk_assessment_ai_run_inquiry"
ASSESSMENT_TABLE = "support_symptom_assessment"
AI_RUN_TABLE = "aiops_ai_run"
SQLITE_TRIGGER_NAMES = (
    "fk_assessment_context_child_insert",
    "fk_assessment_context_child_update",
    "fk_assessment_context_parent_update",
)


def add_assessment_ai_run_inquiry_fk(apps, schema_editor):
    """Enforce that an optional AI run belongs to the same inquiry."""

    del apps
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            f"""
            ALTER TABLE {ASSESSMENT_TABLE}
            ADD CONSTRAINT {CONSTRAINT_NAME}
            FOREIGN KEY (ai_run_id, inquiry_id)
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
            BEFORE INSERT ON {ASSESSMENT_TABLE}
            FOR EACH ROW
            WHEN NEW.ai_run_id IS NOT NULL
             AND NOT EXISTS (
                SELECT 1
                FROM {AI_RUN_TABLE} parent
                WHERE parent.id = NEW.ai_run_id
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
            BEFORE UPDATE OF ai_run_id, inquiry_id
            ON {ASSESSMENT_TABLE}
            FOR EACH ROW
            WHEN NEW.ai_run_id IS NOT NULL
             AND NOT EXISTS (
                SELECT 1
                FROM {AI_RUN_TABLE} parent
                WHERE parent.id = NEW.ai_run_id
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
                FROM {ASSESSMENT_TABLE} child
                WHERE child.ai_run_id = OLD.id
                  AND (
                      child.ai_run_id <> NEW.id
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
        "SymptomAssessment context migration supports PostgreSQL and "
        f"SQLite only, not {vendor!r}."
    )


def remove_assessment_ai_run_inquiry_fk(apps, schema_editor):
    """Remove the vendor-specific composite context constraint."""

    del apps
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            f"""
            ALTER TABLE {ASSESSMENT_TABLE}
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
        "SymptomAssessment context rollback supports PostgreSQL and "
        f"SQLite only, not {vendor!r}."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0002_airun"),
        ("inquiries", "0005_inquiry_ux_inquiry_id_subscription"),
    ]

    operations = [
        migrations.CreateModel(
            name="SymptomAssessment",
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
                    "assessment_version",
                    models.PositiveIntegerField(default=1),
                ),
                (
                    "ruleset_version",
                    models.CharField(max_length=40),
                ),
                (
                    "risk_level_code",
                    models.CharField(
                        choices=[
                            ("general", "General"),
                            ("caution", "Caution"),
                            ("danger", "Danger"),
                        ],
                        max_length=40,
                    ),
                ),
                (
                    "priority_code",
                    models.CharField(max_length=40),
                ),
                (
                    "usage_guidance_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("NORMAL", "Normal use"),
                            ("PARTIAL_STOP", "Partial stop"),
                            ("TOTAL_STOP", "Total stop"),
                            (
                                "PENDING_CONSULTATION",
                                "Pending consultation",
                            ),
                        ],
                        max_length=32,
                        null=True,
                    ),
                ),
                (
                    "requires_consultation",
                    models.BooleanField(default=False),
                ),
                ("reason", models.TextField()),
                ("rule_result", models.JSONField(default=dict)),
                (
                    "assessed_by_type_code",
                    models.CharField(
                        default="RULE",
                        max_length=40,
                    ),
                ),
                (
                    "ai_run",
                    models.ForeignKey(
                        blank=True,
                        db_column="ai_run_id",
                        db_index=False,
                        null=True,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="symptom_assessments",
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
                        related_name="symptom_assessments",
                        to="inquiries.inquiry",
                    ),
                ),
            ],
            options={
                "db_table": "support_symptom_assessment",
                "indexes": [
                    models.Index(
                        fields=[
                            "risk_level_code",
                            "created_at",
                        ],
                        name="ix_assessment_risk",
                    ),
                    models.Index(
                        fields=["ai_run", "inquiry"],
                        name="ix_assessment_ai_run",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "inquiry",
                            "assessment_version",
                        ),
                        name="ux_assessment_version",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("assessment_version__gt", 0)
                        ),
                        name="ck_assessment_version_positive",
                    ),
                    models.CheckConstraint(
                        condition=(
                            apps.common_codes.db_expressions
                            .IsJSONObject(
                                models.F("rule_result")
                            )
                        ),
                        name="ck_assessment_rule_result_object",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                (
                                    "assessed_by_type_code",
                                    "AI",
                                ),
                                _negated=True,
                            ),
                            ("ai_run__isnull", False),
                            _connector="OR",
                        ),
                        name="ck_assessment_ai_origin",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                (
                                    "risk_level_code",
                                    "danger",
                                ),
                                _negated=True,
                            ),
                            models.Q(
                                (
                                    "requires_consultation",
                                    True,
                                ),
                                (
                                    "usage_guidance_status",
                                    "TOTAL_STOP",
                                ),
                                (
                                    "usage_guidance_status__isnull",
                                    False,
                                ),
                            ),
                            _connector="OR",
                        ),
                        name="ck_assessment_danger_safety",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                (
                                    "risk_level_code",
                                    "caution",
                                ),
                                _negated=True,
                            ),
                            models.Q(
                                (
                                    "usage_guidance_status__in",
                                    [
                                        "PARTIAL_STOP",
                                        "TOTAL_STOP",
                                        (
                                            "PENDING_"
                                            "CONSULTATION"
                                        ),
                                    ],
                                ),
                                (
                                    "usage_guidance_status__isnull",
                                    False,
                                ),
                            ),
                            _connector="OR",
                        ),
                        name="ck_assessment_caution_safety",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "usage_guidance_status__isnull",
                                True,
                            ),
                            models.Q(
                                (
                                    "usage_guidance_status",
                                    (
                                        "PENDING_"
                                        "CONSULTATION"
                                    ),
                                ),
                                _negated=True,
                            ),
                            (
                                "requires_consultation",
                                True,
                            ),
                            _connector="OR",
                        ),
                        name=(
                            "ck_assessment_"
                            "pending_consultation"
                        ),
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "risk_level_code__in",
                                [
                                    "general",
                                    "caution",
                                    "danger",
                                ],
                            )
                        ),
                        name=(
                            "ck_support_symptom_assessment_"
                            "risk_level_code_allowed"
                        ),
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "usage_guidance_status__isnull",
                                True,
                            ),
                            (
                                "usage_guidance_status__in",
                                [
                                    "NORMAL",
                                    "PARTIAL_STOP",
                                    "TOTAL_STOP",
                                    (
                                        "PENDING_"
                                        "CONSULTATION"
                                    ),
                                ],
                            ),
                            _connector="OR",
                        ),
                        name=(
                            "ck_support_symptom_assessment_"
                            "usage_guidance_status_allowed"
                        ),
                    ),
                ],
            },
        ),
        migrations.RunPython(
            add_assessment_ai_run_inquiry_fk,
            reverse_code=remove_assessment_ai_run_inquiry_fk,
        ),
    ]
