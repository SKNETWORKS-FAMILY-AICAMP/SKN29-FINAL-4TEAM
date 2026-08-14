from django.db import migrations


CONSTRAINT_NAME = "ck_chunk_embedding_dimension"
TABLE_NAME = "knowledge_chunk_embedding"


def _replace_dimension_constraint(schema_editor, *, expression: str) -> None:
    table = schema_editor.quote_name(TABLE_NAME)
    constraint = schema_editor.quote_name(CONSTRAINT_NAME)
    schema_editor.execute(
        f"ALTER TABLE {table} DROP CONSTRAINT {constraint}"
    )
    schema_editor.execute(
        f"""
        ALTER TABLE {table}
        ADD CONSTRAINT {constraint}
        CHECK (
            embedding_dimension = 1024
            AND embedding_dimension = {expression}
        )
        """
    )


def add_explicit_vector_cast(apps, schema_editor):
    """Make the pgvector overload deterministic for every validation path."""

    if schema_editor.connection.vendor != "postgresql":
        return
    _replace_dimension_constraint(
        schema_editor,
        expression="vector_dims((embedding)::vector)",
    )


def restore_implicit_vector_type(apps, schema_editor):
    """Restore the pre-fix constraint when this migration is reversed."""

    if schema_editor.connection.vendor != "postgresql":
        return
    _replace_dimension_constraint(
        schema_editor,
        expression="vector_dims(embedding)",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("evidence", "0010_backend_ai_rag_chunks_view"),
    ]

    operations = [
        migrations.RunPython(
            add_explicit_vector_cast,
            restore_implicit_vector_type,
        ),
    ]
