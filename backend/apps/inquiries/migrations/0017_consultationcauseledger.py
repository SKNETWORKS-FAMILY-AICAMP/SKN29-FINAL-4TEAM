import django.db.models.deletion
from django.db import migrations, models
from django.db.models import F, Q

import apps.common_codes.db_expressions


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0005_airun_analyze_symptom_task"),
        ("inquiries", "0016_humanreview_consultation_policy"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConsultationCauseLedger",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("ledger_id", models.UUIDField(editable=False, unique=True)),
                ("contract_version", models.CharField(max_length=20)),
                ("correlation_id", models.UUIDField()),
                ("ai_request_id", models.CharField(max_length=100)),
                (
                    "source_inquiry_state_version",
                    models.PositiveIntegerField(),
                ),
                ("model_code", models.CharField(max_length=100)),
                ("producer", models.CharField(max_length=40)),
                ("policy_version", models.CharField(max_length=100)),
                ("execution_identity", models.JSONField(default=dict)),
                ("analysis_result_sha256", models.CharField(max_length=64)),
                ("causes", models.JSONField(blank=True, default=list)),
                ("ledger_sha256", models.CharField(max_length=64)),
                (
                    "ai_run",
                    models.OneToOneField(
                        db_column="ai_run_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="consultation_cause_ledger",
                        to="audit.airun",
                    ),
                ),
                (
                    "inquiry",
                    models.ForeignKey(
                        db_column="inquiry_id",
                        db_index=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="consultation_cause_ledgers",
                        to="inquiries.inquiry",
                    ),
                ),
            ],
            options={
                "db_table": "support_consultation_cause_ledger",
                "indexes": [
                    models.Index(
                        fields=["inquiry", "-created_at"],
                        name="ix_ccledger_inquiry_created",
                    ),
                    models.Index(
                        fields=["model_code", "-created_at"],
                        name="ix_ccledger_model_created",
                    ),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="consultationcauseledger",
            constraint=models.UniqueConstraint(
                fields=("inquiry", "ai_request_id"),
                name="ux_ccledger_inquiry_request",
            ),
        ),
        migrations.AddConstraint(
            model_name="consultationcauseledger",
            constraint=models.CheckConstraint(
                condition=Q(contract_version="1.0.0"),
                name="ck_ccledger_contract_v1",
            ),
        ),
        migrations.AddConstraint(
            model_name="consultationcauseledger",
            constraint=models.CheckConstraint(
                condition=Q(producer="AI_HARNESS"),
                name="ck_ccledger_producer",
            ),
        ),
        migrations.AddConstraint(
            model_name="consultationcauseledger",
            constraint=models.CheckConstraint(
                condition=Q(source_inquiry_state_version__gt=0),
                name="ck_ccledger_state_version",
            ),
        ),
        migrations.AddConstraint(
            model_name="consultationcauseledger",
            constraint=models.CheckConstraint(
                condition=apps.common_codes.db_expressions.IsJSONObject(
                    F("execution_identity")
                ),
                name="ck_ccledger_execution_object",
            ),
        ),
        migrations.AddConstraint(
            model_name="consultationcauseledger",
            constraint=models.CheckConstraint(
                condition=apps.common_codes.db_expressions.IsJSONArray(
                    F("causes")
                ),
                name="ck_ccledger_causes_array",
            ),
        ),
        migrations.AddConstraint(
            model_name="consultationcauseledger",
            constraint=models.CheckConstraint(
                condition=Q(
                    analysis_result_sha256__regex=r"^[0-9a-f]{64}$"
                ),
                name="ck_ccledger_analysis_hash",
            ),
        ),
        migrations.AddConstraint(
            model_name="consultationcauseledger",
            constraint=models.CheckConstraint(
                condition=Q(ledger_sha256__regex=r"^[0-9a-f]{64}$"),
                name="ck_ccledger_ledger_hash",
            ),
        ),
    ]
