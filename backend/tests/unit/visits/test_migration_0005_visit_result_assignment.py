"""Forward, reverse, and safety proof for the VisitResult submitter guard."""

from importlib import import_module
from unittest.mock import MagicMock

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


OLD_TARGET = [("visits", "0004_visit_runtime_fields")]
NEW_TARGET = [("visits", "0005_replace_visit_result_assignment_fk")]


def postgres_guard_state() -> tuple[bool, bool]:
    """Return whether the legacy FK and replacement trigger exist."""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_visit_result_assigned_technician'
                  AND conrelid = 'field_service_visit_result'::regclass
            )
            """
        )
        legacy_fk = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_trigger
                WHERE tgname = 'trg_visit_result_submitter_assignment'
                  AND tgrelid = 'field_service_visit_result'::regclass
                  AND NOT tgisinternal
            )
            """
        )
        trigger = cursor.fetchone()[0]
    return legacy_fk, trigger


@pytest.mark.django_db(transaction=True)
def test_0005_forward_reverse_and_reapply_are_symmetric(request):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL migration symmetry assertion")

    request.addfinalizer(
        lambda: MigrationExecutor(connection).migrate(NEW_TARGET)
    )
    MigrationExecutor(connection).migrate(NEW_TARGET)
    assert postgres_guard_state() == (False, True)

    MigrationExecutor(connection).migrate(OLD_TARGET)
    assert postgres_guard_state() == (True, False)

    MigrationExecutor(connection).migrate(NEW_TARGET)
    assert postgres_guard_state() == (False, True)


def test_reverse_refuses_to_rewrite_historical_submitters():
    migration = import_module(
        "apps.visits.migrations.0005_replace_visit_result_assignment_fk"
    )
    schema_editor = MagicMock()
    schema_editor.connection.vendor = "postgresql"
    cursor = (
        schema_editor.connection.cursor.return_value
        .__enter__.return_value
    )
    cursor.fetchone.return_value = (2,)

    with pytest.raises(RuntimeError, match="2 VisitResult row"):
        migration.restore_assignment_fk(None, schema_editor)

    schema_editor.execute.assert_not_called()
