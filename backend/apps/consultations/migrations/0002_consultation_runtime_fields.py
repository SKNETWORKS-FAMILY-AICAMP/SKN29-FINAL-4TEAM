from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("consultations", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="consultation",
            name="summary",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="consultation",
            name="ai_draft_summary",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="consultation",
            name="confirmed_summary",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="consultation",
            name="summary_confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="consultation",
            name="consultation_note",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="consultation",
            name="additional_check",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="consultation",
            name="customer_guidance",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="consultation",
            name="usage_guidance_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("NORMAL", "Normal use"),
                    ("PARTIAL_STOP", "Partial stop"),
                    ("TOTAL_STOP", "Total stop"),
                    ("PENDING_CONSULTATION", "Pending consultation"),
                ],
                max_length=40,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="consultation",
            name="visit_review_reason_code",
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
        migrations.AddField(
            model_name="consultation",
            name="visit_review_reason_detail",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="consultation",
            name="visit_not_needed_reason_code",
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
        migrations.AddField(
            model_name="consultation",
            name="visit_not_needed_reason_detail",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RemoveConstraint(
            model_name="consultation",
            name="ck_consult_summary_nonempty",
        ),
        migrations.RemoveConstraint(
            model_name="consultation",
            name="ck_consult_outcome_lifecycle",
        ),
        migrations.AddConstraint(
            model_name="consultation",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        status="COMPLETED",
                        outcome__in=[
                            "COMPLETED_NO_VISIT",
                            "VISIT_REQUIRED",
                            "REOPENED_FOLLOWUP",
                        ],
                    )
                    | models.Q(
                        status="IN_PROGRESS",
                        outcome__in=[
                            "PENDING",
                            "COMPLETED_NO_VISIT",
                            "VISIT_REQUIRED",
                            "REOPENED_FOLLOWUP",
                        ],
                    )
                    | models.Q(
                        status__in=["WAITING", "ASSIGNED", "CANCELLED"],
                        outcome="PENDING",
                    )
                ),
                name="ck_consult_outcome_lifecycle",
            ),
        ),
    ]
