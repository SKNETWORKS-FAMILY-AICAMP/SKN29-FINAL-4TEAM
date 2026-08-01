"""Ranked document-chunk candidates from one retrieval execution."""

from __future__ import annotations

import uuid

from django.db import models
from django.db.models import Q

from common.models.base import TimestampedModel


class AIRetrievalHit(TimestampedModel):
    """Persist one ranked chunk candidate and its selection metadata."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    retrieval_run = models.ForeignKey(
        "audit.AIRetrievalRun",
        on_delete=models.PROTECT,
        related_name="hits",
        db_column="retrieval_run_id",
        db_index=False,
    )
    chunk = models.ForeignKey(
        "evidence.DocumentChunk",
        on_delete=models.PROTECT,
        related_name="retrieval_hits",
        db_column="chunk_id",
        db_index=False,
    )
    rank_no = models.SmallIntegerField()
    vector_score = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
    )
    keyword_score = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
    )
    hybrid_score = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
    )
    rerank_score = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
    )
    # EVIDENCE_APPLICABILITY has no canonical YAML contract yet.
    applicability_status_code = models.CharField(
        max_length=40,
        default="PENDING",
    )
    applicability_reason = models.TextField(null=True, blank=True)
    selected_for_answer = models.BooleanField(default=False)
    selected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "aiops_retrieval_hit"
        constraints = [
            models.UniqueConstraint(
                fields=["retrieval_run", "rank_no"],
                name="ux_retrieval_hit_rank",
            ),
            models.UniqueConstraint(
                fields=["retrieval_run", "chunk"],
                name="ux_retrieval_hit_chunk",
            ),
            models.UniqueConstraint(
                fields=["id", "chunk"],
                name="ux_retrieval_hit_id_chunk",
            ),
            models.UniqueConstraint(
                fields=["id", "retrieval_run", "chunk"],
                name="ux_retrieval_hit_id_run_chunk",
            ),
            models.CheckConstraint(
                condition=Q(rank_no__gt=0),
                name="ck_retrieval_hit_rank",
            ),
            models.CheckConstraint(
                condition=(
                    Q(vector_score__isnull=False)
                    | Q(keyword_score__isnull=False)
                    | Q(hybrid_score__isnull=False)
                    | Q(rerank_score__isnull=False)
                ),
                name="ck_retrieval_hit_score",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        selected_for_answer=True,
                        selected_at__isnull=False,
                    )
                    | Q(
                        selected_for_answer=False,
                        selected_at__isnull=True,
                    )
                ),
                name="ck_retrieval_hit_selected",
            ),
            models.CheckConstraint(
                condition=Q(
                    applicability_status_code__regex=r".*\S.*"
                ),
                name="ck_retrieval_hit_applicability_nonempty",
            ),
        ]
        indexes = [
            models.Index(
                fields=["retrieval_run", "rank_no"],
                condition=Q(selected_for_answer=True),
                name="ix_retrieval_hit_selected",
            ),
            models.Index(
                fields=["chunk"],
                name="ix_retrieval_hit_chunk",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.retrieval_run.public_id} rank {self.rank_no} "
            f"chunk {self.chunk.public_id}"
        )
