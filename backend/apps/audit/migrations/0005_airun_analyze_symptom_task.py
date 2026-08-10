"""Allow one AIRun to represent the integrated symptom-analysis endpoint."""

from django.db import migrations, models
from django.db.models import Q


TASK_TYPES = [
    "ANALYZE_SYMPTOM",
    "STRUCTURE_SYMPTOM",
    "GENERATE_QUESTIONS",
    "ASSESS_RISK",
    "RETRIEVE_EVIDENCE",
    "GENERATE_GUIDANCE",
    "SUMMARIZE_CONSULTATION",
    "DRAFT_HANDOFF",
]

SQLITE_TRIGGER_BACKUP_TABLE = "_migration_audit_0005_ai_run_triggers"


def suspend_ai_run_triggers(apps, schema_editor):
    """Temporarily remove SQLite triggers that reference aiops_ai_run.

    SQLite implements check-constraint changes by rebuilding the table.  The
    project already has several cross-table integrity triggers that point at
    aiops_ai_run; those triggers must be restored after the rebuild.
    """

    del apps
    if schema_editor.connection.vendor != "sqlite":
        return

    cursor = schema_editor.connection.cursor()
    cursor.execute(f'DROP TABLE IF EXISTS "{SQLITE_TRIGGER_BACKUP_TABLE}"')
    cursor.execute(
        f'CREATE TABLE "{SQLITE_TRIGGER_BACKUP_TABLE}" '
        '(name TEXT PRIMARY KEY, sql TEXT NOT NULL)'
    )
    cursor.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type = 'trigger' "
        "AND sql IS NOT NULL "
        "AND lower(sql) LIKE '%aiops_ai_run%'"
    )
    trigger_rows = cursor.fetchall()
    for trigger_name, trigger_sql in trigger_rows:
        cursor.execute(
            f'INSERT INTO "{SQLITE_TRIGGER_BACKUP_TABLE}" '
            '(name, sql) VALUES (%s, %s)',
            [trigger_name, trigger_sql],
        )
        quoted_name = schema_editor.quote_name(trigger_name)
        cursor.execute(f"DROP TRIGGER IF EXISTS {quoted_name}")


def restore_ai_run_triggers(apps, schema_editor):
    """Restore the SQLite integrity triggers saved before the table rebuild."""

    del apps
    if schema_editor.connection.vendor != "sqlite":
        return

    cursor = schema_editor.connection.cursor()
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = %s",
        [SQLITE_TRIGGER_BACKUP_TABLE],
    )
    if cursor.fetchone() is None:
        return

    cursor.execute(
        f'SELECT sql FROM "{SQLITE_TRIGGER_BACKUP_TABLE}" ORDER BY name'
    )
    for (trigger_sql,) in cursor.fetchall():
        cursor.execute(trigger_sql)
    cursor.execute(f'DROP TABLE "{SQLITE_TRIGGER_BACKUP_TABLE}"')


class Migration(migrations.Migration):
    dependencies = [("audit", "0004_airetrievalhit")]

    operations = [
        migrations.RunPython(
            suspend_ai_run_triggers,
            reverse_code=restore_ai_run_triggers,
        ),
        migrations.RemoveConstraint(
            model_name="airun",
            name="ck_aiops_ai_run_task_type_code_allowed",
        ),
        migrations.AlterField(
            model_name="airun",
            name="task_type_code",
            field=models.CharField(
                choices=[
                    ("ANALYZE_SYMPTOM", "Analyze symptom pipeline"),
                    ("STRUCTURE_SYMPTOM", "Structure symptom"),
                    ("GENERATE_QUESTIONS", "Generate questions"),
                    ("ASSESS_RISK", "Assess risk"),
                    ("RETRIEVE_EVIDENCE", "Retrieve evidence"),
                    ("GENERATE_GUIDANCE", "Generate guidance"),
                    ("SUMMARIZE_CONSULTATION", "Summarize consultation"),
                    ("DRAFT_HANDOFF", "Draft handoff"),
                ],
                max_length=50,
            ),
        ),
        migrations.AddConstraint(
            model_name="airun",
            constraint=models.CheckConstraint(
                condition=Q(task_type_code__in=TASK_TYPES),
                name="ck_aiops_ai_run_task_type_code_allowed",
            ),
        ),
        migrations.RunPython(
            restore_ai_run_triggers,
            reverse_code=suspend_ai_run_triggers,
        ),
    ]
