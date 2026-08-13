"""Preserve the VisitResult submitter when a revisit changes technician."""

from django.db import migrations


RESULT_TABLE = "field_service_visit_result"
VISIT_TABLE = "field_service_visit"
LEGACY_CONSTRAINT = "fk_visit_result_assigned_technician"
TRIGGER_NAME = "trg_visit_result_submitter_assignment"
FUNCTION_NAME = "check_visit_result_submitter_assignment"
SUBMISSION_CONSTRAINT = "fk_visit_result_submitter_at_submission"
IMMUTABLE_CONSTRAINT = "ck_visit_result_assignment_immutable"


def replace_assignment_fk_with_trigger(_apps, schema_editor):
    """Validate the assigned technician when a result is first submitted."""

    if schema_editor.connection.vendor != "postgresql":
        return

    schema_editor.execute(
        f"""
        CREATE FUNCTION {FUNCTION_NAME}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        DECLARE
            assigned_technician_id bigint;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                IF NEW.visit_id IS DISTINCT FROM OLD.visit_id
                   OR NEW.submitted_by_id IS DISTINCT FROM OLD.submitted_by_id
                THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '23514',
                        MESSAGE = '{IMMUTABLE_CONSTRAINT}',
                        CONSTRAINT = '{IMMUTABLE_CONSTRAINT}';
                END IF;
                RETURN NEW;
            END IF;

            SELECT parent.technician_id
              INTO assigned_technician_id
              FROM {VISIT_TABLE} parent
             WHERE parent.id = NEW.visit_id
             FOR KEY SHARE;

            IF NOT FOUND
               OR assigned_technician_id IS NULL
               OR assigned_technician_id IS DISTINCT FROM NEW.submitted_by_id
            THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23503',
                    MESSAGE = '{SUBMISSION_CONSTRAINT}',
                    CONSTRAINT = '{SUBMISSION_CONSTRAINT}';
            END IF;

            RETURN NEW;
        END
        $function$
        """
    )
    schema_editor.execute(
        f"""
        CREATE TRIGGER {TRIGGER_NAME}
        BEFORE INSERT OR UPDATE OF visit_id, submitted_by_id
        ON {RESULT_TABLE}
        FOR EACH ROW
        EXECUTE FUNCTION {FUNCTION_NAME}()
        """
    )
    schema_editor.execute(
        f"""
        ALTER TABLE {RESULT_TABLE}
        DROP CONSTRAINT IF EXISTS {LEGACY_CONSTRAINT}
        """
    )


def restore_assignment_fk(_apps, schema_editor):
    """Restore the legacy FK only when no historical reassignment exists."""

    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM {RESULT_TABLE} result
            JOIN {VISIT_TABLE} visit ON visit.id = result.visit_id
            WHERE visit.technician_id IS DISTINCT FROM result.submitted_by_id
            """
        )
        mismatch_count = cursor.fetchone()[0]

    if mismatch_count:
        raise RuntimeError(
            "Cannot restore the mutable assignment FK: "
            f"{mismatch_count} VisitResult row(s) preserve a historical "
            "submitting technician after reassignment."
        )

    schema_editor.execute(
        f"""
        ALTER TABLE {RESULT_TABLE}
        ADD CONSTRAINT {LEGACY_CONSTRAINT}
        FOREIGN KEY (visit_id, submitted_by_id)
        REFERENCES {VISIT_TABLE} (id, technician_id)
        ON DELETE RESTRICT
        """
    )
    schema_editor.execute(
        f"""
        DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON {RESULT_TABLE}
        """
    )
    schema_editor.execute(
        f"""
        DROP FUNCTION IF EXISTS {FUNCTION_NAME}()
        """
    )


class Migration(migrations.Migration):

    dependencies = [
        ("visits", "0004_visit_runtime_fields"),
    ]

    operations = [
        migrations.RunPython(
            replace_assignment_fk_with_trigger,
            restore_assignment_fk,
        ),
    ]
