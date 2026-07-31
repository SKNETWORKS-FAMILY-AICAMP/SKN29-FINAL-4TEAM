# Generated from the active T-005 Wave 5A contract on 2026-07-30.

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0003_airetrievalrun"),
        ("evidence", "0005_documentchunk"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIRetrievalHit",
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
                ("rank_no", models.SmallIntegerField()),
                (
                    "vector_score",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=10,
                        null=True,
                    ),
                ),
                (
                    "keyword_score",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=10,
                        null=True,
                    ),
                ),
                (
                    "hybrid_score",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=10,
                        null=True,
                    ),
                ),
                (
                    "rerank_score",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=10,
                        null=True,
                    ),
                ),
                (
                    "applicability_status_code",
                    models.CharField(
                        default="PENDING",
                        max_length=40,
                    ),
                ),
                (
                    "applicability_reason",
                    models.TextField(blank=True, null=True),
                ),
                (
                    "selected_for_answer",
                    models.BooleanField(default=False),
                ),
                (
                    "selected_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "chunk",
                    models.ForeignKey(
                        db_column="chunk_id",
                        db_index=False,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="retrieval_hits",
                        to="evidence.documentchunk",
                    ),
                ),
                (
                    "retrieval_run",
                    models.ForeignKey(
                        db_column="retrieval_run_id",
                        db_index=False,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="hits",
                        to="audit.airetrievalrun",
                    ),
                ),
            ],
            options={
                "db_table": "aiops_retrieval_hit",
                "indexes": [
                    models.Index(
                        condition=models.Q(
                            ("selected_for_answer", True)
                        ),
                        fields=["retrieval_run", "rank_no"],
                        name="ix_retrieval_hit_selected",
                    ),
                    models.Index(
                        fields=["chunk"],
                        name="ix_retrieval_hit_chunk",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("retrieval_run", "rank_no"),
                        name="ux_retrieval_hit_rank",
                    ),
                    models.UniqueConstraint(
                        fields=("retrieval_run", "chunk"),
                        name="ux_retrieval_hit_chunk",
                    ),
                    models.UniqueConstraint(
                        fields=("id", "chunk"),
                        name="ux_retrieval_hit_id_chunk",
                    ),
                    models.UniqueConstraint(
                        fields=(
                            "id",
                            "retrieval_run",
                            "chunk",
                        ),
                        name=(
                            "ux_retrieval_hit_"
                            "id_run_chunk"
                        ),
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("rank_no__gt", 0)),
                        name="ck_retrieval_hit_rank",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("vector_score__isnull", False),
                            ("keyword_score__isnull", False),
                            ("hybrid_score__isnull", False),
                            ("rerank_score__isnull", False),
                            _connector="OR",
                        ),
                        name="ck_retrieval_hit_score",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                (
                                    "selected_at__isnull",
                                    False,
                                ),
                                (
                                    "selected_for_answer",
                                    True,
                                ),
                            ),
                            models.Q(
                                (
                                    "selected_at__isnull",
                                    True,
                                ),
                                (
                                    "selected_for_answer",
                                    False,
                                ),
                            ),
                            _connector="OR",
                        ),
                        name="ck_retrieval_hit_selected",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "applicability_status_code__regex",
                                r".*\S.*",
                            )
                        ),
                        name=(
                            "ck_retrieval_hit_"
                            "applicability_nonempty"
                        ),
                    ),
                ],
            },
        ),
    ]
