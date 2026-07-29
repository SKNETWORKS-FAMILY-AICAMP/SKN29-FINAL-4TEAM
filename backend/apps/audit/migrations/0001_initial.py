# Generated manually for the synthetic handoff audit ledger.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0002_add_public_identifiers"),
        ("inquiries", "0003_add_synthetic_handoff_fields"),
        ("visits", "0001_initial"),
        ("workflow", "0002_expand_transition_targets"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
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
                    "audit_code",
                    models.CharField(max_length=80, unique=True),
                ),
                (
                    "entity_type",
                    models.CharField(
                        choices=[
                            ("INQUIRY", "Inquiry"),
                            ("VISIT", "Visit"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "event_code",
                    models.CharField(max_length=80),
                ),
                (
                    "actor_role",
                    models.CharField(
                        choices=[
                            ("CUSTOMER", "Customer"),
                            ("CONSULTANT", "Consultant"),
                            ("TECHNICIAN", "Technician"),
                            ("SYSTEM", "System"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "state_version",
                    models.PositiveIntegerField(),
                ),
                (
                    "idempotency_key",
                    models.CharField(max_length=128),
                ),
                ("correlation_id", models.UUIDField()),
                ("occurred_at", models.DateTimeField()),
                (
                    "data_classification",
                    models.CharField(
                        choices=[("synthetic", "Synthetic")],
                        default="synthetic",
                        max_length=20,
                    ),
                ),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        db_column="actor_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="audit_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "inquiry",
                    models.ForeignKey(
                        blank=True,
                        db_column="inquiry_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="audit_events",
                        to="inquiries.inquiry",
                    ),
                ),
                (
                    "transition",
                    models.OneToOneField(
                        db_column="transition_history_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="audit_event",
                        to="workflow.transitionhistory",
                    ),
                ),
                (
                    "visit",
                    models.ForeignKey(
                        blank=True,
                        db_column="visit_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="audit_events",
                        to="visits.visit",
                    ),
                ),
            ],
            options={
                "db_table": "audit_event",
                "indexes": [
                    models.Index(
                        fields=["entity_type", "occurred_at"],
                        name="ix_audit_entity_time",
                    ),
                    models.Index(
                        fields=["correlation_id"],
                        name="ix_audit_correlation",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("entity_type__in", ["INQUIRY", "VISIT"])
                        ),
                        name="ck_audit_entity_type",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "actor_role__in",
                                [
                                    "CUSTOMER",
                                    "CONSULTANT",
                                    "TECHNICIAN",
                                    "SYSTEM",
                                ],
                            )
                        ),
                        name="ck_audit_actor_role",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("state_version__gt", 0)),
                        name="ck_audit_state_version_positive",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(
                                ("entity_type", "INQUIRY"),
                                ("inquiry__isnull", False),
                                ("visit__isnull", True),
                            )
                            | models.Q(
                                ("entity_type", "VISIT"),
                                ("inquiry__isnull", True),
                                ("visit__isnull", False),
                            )
                        ),
                        name="ck_audit_entity_target_match",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(
                                ("actor__isnull", True),
                                ("actor_role", "SYSTEM"),
                            )
                            | models.Q(
                                ("actor__isnull", False),
                                (
                                    "actor_role__in",
                                    [
                                        "CUSTOMER",
                                        "CONSULTANT",
                                        "TECHNICIAN",
                                    ],
                                ),
                            )
                        ),
                        name="ck_audit_actor_presence",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("data_classification", "synthetic")
                        ),
                        name="ck_audit_data_synthetic",
                    ),
                ],
            },
        )
    ]
