"""Project typed CHILD metadata through the AI read-only view."""

from importlib import import_module

from django.db import migrations


BASE = import_module(
    "apps.evidence.migrations.0014_decouple_ai_view_product_eligibility"
)

MARKER = """    jsonb_build_object(
"""
PATCH = """        'record_type', 'child',
"""

if MARKER not in BASE.CREATE_VIEW_SQL:
    raise RuntimeError("AI view metadata marker not found")

CREATE_VIEW_SQL = BASE.CREATE_VIEW_SQL.replace(
    MARKER,
    MARKER + PATCH,
    1,
)

RESTORE_VIEW_SQL = BASE.CREATE_VIEW_SQL


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(CREATE_VIEW_SQL, params=None)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(RESTORE_VIEW_SQL, params=None)


class Migration(migrations.Migration):
    dependencies = [
        ("evidence", "0014_decouple_ai_view_product_eligibility"),
    ]

    operations = [
        migrations.RunPython(forwards, reverse_code=backwards),
    ]
