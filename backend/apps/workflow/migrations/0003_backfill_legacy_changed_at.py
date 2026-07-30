"""Restore legacy transition timestamps changed by workflow.0002."""

from django.db import migrations
from django.db.models import F


def backfill_legacy_changed_at(apps, schema_editor):
    """Use row creation time for legacy rows stamped after their insert.

    A transition history row is appended when its transition occurs, so its
    business timestamp cannot be later than the row creation timestamp.
    workflow.0002 violated that invariant for pre-existing rows by assigning
    its one-off migration timestamp as ``changed_at``.
    """

    transition_history = apps.get_model(
        "workflow",
        "TransitionHistory",
    )
    database_alias = schema_editor.connection.alias
    candidates = transition_history.objects.using(database_alias).filter(
        changed_at__gt=F("created_at"),
    ).only(
        "id",
        "public_id",
        "status_history_code",
        "created_at",
        "changed_at",
    )

    pending = []
    for record in candidates.iterator(chunk_size=500):
        legacy_code = f"HST-{record.public_id.hex.upper()}"
        if record.status_history_code != legacy_code:
            continue
        record.changed_at = record.created_at
        pending.append(record)
        if len(pending) == 500:
            transition_history.objects.using(database_alias).bulk_update(
                pending,
                ["changed_at"],
                batch_size=500,
            )
            pending.clear()

    if pending:
        transition_history.objects.using(database_alias).bulk_update(
            pending,
            ["changed_at"],
            batch_size=500,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("workflow", "0002_expand_transition_targets"),
    ]

    operations = [
        migrations.RunPython(
            backfill_legacy_changed_at,
            migrations.RunPython.noop,
        ),
    ]
