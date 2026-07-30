# Generated manually for the official synthetic handoff importer ledger.

import apps.operations.models.synthetic_import_ledger
import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0002_add_public_identifiers"),
        ("audit", "0001_initial"),
        ("care", "0002_add_imported_care_fields"),
        ("consultations", "0001_initial"),
        ("inquiries", "0004_followup_confirmation"),
        ("products", "0001_initial"),
        ("subscriptions", "0002_add_synthetic_projection_fields"),
        ("visits", "0001_initial"),
        ("workflow", "0002_expand_transition_targets"),
    ]

    operations = [
        migrations.CreateModel(
            name="SyntheticImportBatch",
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
                (
                    "batch_code",
                    models.CharField(
                        default=(
                            apps.operations.models
                            .synthetic_import_ledger
                            .generate_import_batch_code
                        ),
                        editable=False,
                        max_length=80,
                        unique=True,
                    ),
                ),
                (
                    "profile",
                    models.CharField(
                        choices=[
                            ("db-smoke", "DB smoke"),
                            ("db-full", "DB full"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("COMPLETED", "Completed")],
                        default="COMPLETED",
                        max_length=20,
                    ),
                ),
                (
                    "dataset_version",
                    models.CharField(max_length=30),
                ),
                (
                    "mapping_version",
                    models.CharField(max_length=30),
                ),
                (
                    "fixture_set_sha256",
                    models.CharField(max_length=64),
                ),
                ("source_count", models.PositiveIntegerField()),
                ("created_count", models.PositiveIntegerField()),
                ("updated_count", models.PositiveIntegerField()),
                ("unchanged_count", models.PositiveIntegerField()),
                ("projected_count", models.PositiveIntegerField()),
                ("completed_at", models.DateTimeField()),
            ],
            options={
                "db_table": "operations_synthetic_import_batch",
                "indexes": [
                    models.Index(
                        fields=["profile", "-completed_at"],
                        name="ix_syn_import_batch_profile",
                    )
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("profile__in", ["db-smoke", "db-full"])
                        ),
                        name="ck_syn_import_batch_profile",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("status", "COMPLETED")),
                        name="ck_syn_import_batch_status",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(
                                ("profile", "db-smoke"),
                                ("source_count", 37),
                            )
                            | models.Q(
                                ("profile", "db-full"),
                                ("source_count", 367),
                            )
                        ),
                        name="ck_syn_import_profile_count",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "source_count",
                                models.F("created_count")
                                + models.F("updated_count")
                                + models.F("unchanged_count")
                                + models.F("projected_count"),
                            )
                        ),
                        name="ck_syn_import_batch_totals",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="SyntheticImportItem",
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
                (
                    "source_dataset",
                    models.CharField(max_length=60),
                ),
                ("source_public_id", models.UUIDField()),
                (
                    "source_business_key",
                    models.CharField(max_length=160),
                ),
                (
                    "source_sha256",
                    models.CharField(max_length=64),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("CREATED", "Created"),
                            ("UPDATED", "Updated"),
                            ("UNCHANGED", "Unchanged"),
                            ("PROJECTED", "Projected"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "target_model",
                    models.CharField(max_length=100),
                ),
                ("target_public_id", models.UUIDField()),
                (
                    "target_business_key",
                    models.CharField(max_length=160),
                ),
                (
                    "batch",
                    models.ForeignKey(
                        db_column="batch_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="items",
                        to="operations.syntheticimportbatch",
                    ),
                ),
            ],
            options={
                "db_table": "operations_synthetic_import_item",
                "indexes": [
                    models.Index(
                        fields=[
                            "source_dataset",
                            "source_public_id",
                        ],
                        name="ix_syn_import_source",
                    ),
                    models.Index(
                        fields=["target_model", "target_public_id"],
                        name="ix_syn_import_target",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "batch",
                            "source_dataset",
                            "source_public_id",
                        ),
                        name="uq_syn_import_item_source",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "action__in",
                                [
                                    "CREATED",
                                    "UPDATED",
                                    "UNCHANGED",
                                    "PROJECTED",
                                ],
                            )
                        ),
                        name="ck_syn_import_item_action",
                    ),
                    models.CheckConstraint(
                        condition=~models.Q(
                            ("source_business_key", "")
                        ),
                        name="ck_syn_import_source_key",
                    ),
                    models.CheckConstraint(
                        condition=~models.Q(("target_model", "")),
                        name="ck_syn_import_target_model",
                    ),
                    models.CheckConstraint(
                        condition=~models.Q(
                            ("target_business_key", "")
                        ),
                        name="ck_syn_import_target_key",
                    ),
                ],
            },
        ),
    ]
