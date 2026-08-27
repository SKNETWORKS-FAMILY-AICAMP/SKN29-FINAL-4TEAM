from django.db import migrations, models
from django.db.models import Q


CONSTRAINT_NAME = "fk_assessment_ai_run_inquiry"
ASSESSMENT_TABLE = "support_symptom_assessment"
AI_RUN_TABLE = "aiops_ai_run"
SQLITE_TRIGGER_NAMES = (
    "fk_assessment_context_child_insert",
    "fk_assessment_context_child_update",
    "fk_assessment_context_parent_update",
)


def drop_sqlite_assessment_context_triggers(apps, schema_editor):
    del apps
    if schema_editor.connection.vendor != "sqlite":
        return
    for trigger_name in SQLITE_TRIGGER_NAMES:
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")


def create_sqlite_assessment_context_triggers(apps, schema_editor):
    del apps
    if schema_editor.connection.vendor != "sqlite":
        return
    child_insert, child_update, parent_update = SQLITE_TRIGGER_NAMES
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


class Migration(migrations.Migration):
    dependencies = [
        ("inquiries", "0013_inquiry_priority_code"),
    ]

    operations = [
        migrations.RunPython(
            drop_sqlite_assessment_context_triggers,
            reverse_code=create_sqlite_assessment_context_triggers,
        ),
        migrations.RemoveConstraint(
            model_name="symptomassessment",
            name="ck_assessment_danger_safety",
        ),
        migrations.AddConstraint(
            model_name="symptomassessment",
            constraint=models.CheckConstraint(
                condition=(
                    ~Q(risk_level_code="danger")
                    | (
                        Q(
                            usage_guidance_status__isnull=False,
                            usage_guidance_status="TOTAL_STOP",
                            requires_consultation=True,
                        )
                        | Q(
                            usage_guidance_status__isnull=False,
                            usage_guidance_status="PARTIAL_STOP",
                            requires_consultation=True,
                            rule_result__matched_safety_rule_ids=[
                                "SAFETY-HOT-WATER-HEATER-001"
                            ],
                        )
                    )
                ),
                name="ck_assessment_danger_safety",
            ),
        ),
        migrations.RunPython(
            create_sqlite_assessment_context_triggers,
            reverse_code=drop_sqlite_assessment_context_triggers,
        ),
    ]
