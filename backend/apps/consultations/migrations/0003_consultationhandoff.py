"""Create the sanitized AI consultation-handoff persistence ledger."""

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0005_airun_analyze_symptom_task"),
        ("consultations", "0002_consultation_runtime_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConsultationHandoff",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "public_id",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("ai_request_id", models.CharField(max_length=128)),
                ("correlation_id", models.UUIDField()),
                ("model_code_snapshot", models.CharField(max_length=100)),
                ("product_family_snapshot", models.CharField(max_length=100)),
                ("schema_version", models.CharField(max_length=30)),
                ("sanitized_payload", models.JSONField(default=dict)),
                ("payload_sha256", models.CharField(max_length=64)),
                ("ai_draft_summary", models.TextField()),
                (
                    "data_classification",
                    models.CharField(
                        choices=[
                            ("synthetic", "Synthetic"),
                            ("operational", "Operational"),
                        ],
                        default="operational",
                        max_length=40,
                    ),
                ),
                (
                    "ai_run",
                    models.OneToOneField(
                        db_column="ai_run_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="consultation_handoff",
                        to="audit.airun",
                    ),
                ),
                (
                    "consultation",
                    models.ForeignKey(
                        blank=True,
                        db_column="consultation_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ai_handoffs",
                        to="consultations.consultation",
                    ),
                ),
                (
                    "inquiry",
                    models.ForeignKey(
                        db_column="inquiry_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="consultation_handoffs",
                        to="inquiries.inquiry",
                    ),
                ),
            ],
            options={
                "db_table": "support_consultation_handoff",
                "indexes": [
                    models.Index(
                        fields=["inquiry", "-created_at"],
                        name="ix_handoff_inquiry_created",
                    ),
                    models.Index(
                        fields=["correlation_id"],
                        name="ix_handoff_correlation",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("inquiry", "ai_request_id"),
                        name="ux_handoff_inquiry_ai_request",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("ai_request_id", ""), _negated=True),
                        name="ck_handoff_ai_request_nonempty",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("payload_sha256__regex", "^[0-9a-f]{64}$")
                        ),
                        name="ck_handoff_payload_sha256",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("ai_draft_summary", ""), _negated=True),
                        name="ck_handoff_draft_nonempty",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("data_classification__in", ["synthetic", "operational"])
                        ),
                        name="ck_handoff_data_class",
                    ),
                ],
            },
        ),
    ]
