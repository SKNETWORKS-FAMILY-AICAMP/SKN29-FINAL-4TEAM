"""Batch and item ledgers for the official synthetic handoff importer."""

from __future__ import annotations

import uuid

from django.db import models
from django.db.models import F, Q

from common.models.base import TimestampedModel


def generate_import_batch_code() -> str:
    """Generate an opaque business identifier for one importer execution."""

    return f"SYN-IMPORT-{uuid.uuid4().hex.upper()}"


class SyntheticImportBatch(TimestampedModel):
    """Completed transactional import summary.

    Dry runs execute through the same transaction but their ledger is rolled
    back together with every domain write.
    """

    class Profile(models.TextChoices):
        DB_SMOKE = "db-smoke", "DB smoke"
        DB_FULL = "db-full", "DB full"
        DB_PRODUCT_EXPANSION = (
            "db-product-expansion",
            "DB product expansion",
        )

    class Status(models.TextChoices):
        COMPLETED = "COMPLETED", "Completed"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    batch_code = models.CharField(
        max_length=80,
        unique=True,
        default=generate_import_batch_code,
        editable=False,
    )
    profile = models.CharField(max_length=20, choices=Profile.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
    )
    dataset_version = models.CharField(max_length=30)
    mapping_version = models.CharField(max_length=30)
    fixture_set_sha256 = models.CharField(max_length=64)
    source_count = models.PositiveIntegerField()
    created_count = models.PositiveIntegerField()
    updated_count = models.PositiveIntegerField()
    unchanged_count = models.PositiveIntegerField()
    projected_count = models.PositiveIntegerField()
    completed_at = models.DateTimeField()

    class Meta:
        db_table = "operations_synthetic_import_batch"
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    profile__in=[
                        "db-smoke",
                        "db-full",
                        "db-product-expansion",
                    ]
                ),
                name="ck_syn_import_batch_profile",
            ),
            models.CheckConstraint(
                condition=Q(status="COMPLETED"),
                name="ck_syn_import_batch_status",
            ),
            models.CheckConstraint(
                condition=(
                    Q(profile="db-smoke", source_count=37)
                    | Q(profile="db-full", source_count=367)
                    | Q(profile="db-product-expansion", source_count=2)
                ),
                name="ck_syn_import_profile_count",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        source_count=(
                            F("created_count")
                            + F("updated_count")
                            + F("unchanged_count")
                            + F("projected_count")
                        )
                    )
                ),
                name="ck_syn_import_batch_totals",
            ),
        ]
        indexes = [
            models.Index(
                fields=["profile", "-completed_at"],
                name="ix_syn_import_batch_profile",
            )
        ]

    def __str__(self) -> str:
        return f"{self.batch_code} ({self.profile})"


class SyntheticImportItem(TimestampedModel):
    """One source fixture row accounted for by an import batch."""

    class Action(models.TextChoices):
        CREATED = "CREATED", "Created"
        UPDATED = "UPDATED", "Updated"
        UNCHANGED = "UNCHANGED", "Unchanged"
        PROJECTED = "PROJECTED", "Projected"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    batch = models.ForeignKey(
        SyntheticImportBatch,
        on_delete=models.PROTECT,
        related_name="items",
        db_column="batch_id",
    )
    source_dataset = models.CharField(max_length=60)
    source_public_id = models.UUIDField()
    source_business_key = models.CharField(max_length=160)
    source_sha256 = models.CharField(max_length=64)
    action = models.CharField(max_length=20, choices=Action.choices)
    target_model = models.CharField(max_length=100)
    target_public_id = models.UUIDField()
    target_business_key = models.CharField(max_length=160)

    class Meta:
        db_table = "operations_synthetic_import_item"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "batch",
                    "source_dataset",
                    "source_public_id",
                ],
                name="uq_syn_import_item_source",
            ),
            models.CheckConstraint(
                condition=Q(
                    action__in=[
                        "CREATED",
                        "UPDATED",
                        "UNCHANGED",
                        "PROJECTED",
                    ]
                ),
                name="ck_syn_import_item_action",
            ),
            models.CheckConstraint(
                condition=~Q(source_business_key=""),
                name="ck_syn_import_source_key",
            ),
            models.CheckConstraint(
                condition=~Q(target_model=""),
                name="ck_syn_import_target_model",
            ),
            models.CheckConstraint(
                condition=~Q(target_business_key=""),
                name="ck_syn_import_target_key",
            ),
        ]
        indexes = [
            models.Index(
                fields=["source_dataset", "source_public_id"],
                name="ix_syn_import_source",
            ),
            models.Index(
                fields=["target_model", "target_public_id"],
                name="ix_syn_import_target",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.source_dataset}:{self.source_business_key} "
            f"({self.action})"
        )
