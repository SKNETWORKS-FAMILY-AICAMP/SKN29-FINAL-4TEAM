"""Allow the approved three-model CHILD-* canonical identity format."""

from django.db import migrations, models


CANONICAL_CHUNK_ID_PATTERN = r"^(?:RAG|CHILD)-[A-Z0-9]+(?:-[A-Z0-9]+)*$"


class Migration(migrations.Migration):
    dependencies = [
        ("evidence", "0011_cast_chunk_embedding_vector_dimensions"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="aichunkcrosswalk",
            name="ck_ai_crosswalk_canonical_id",
        ),
        migrations.AddConstraint(
            model_name="aichunkcrosswalk",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    canonical_chunk_id__regex=CANONICAL_CHUNK_ID_PATTERN
                ),
                name="ck_ai_crosswalk_canonical_id",
            ),
        ),
    ]
