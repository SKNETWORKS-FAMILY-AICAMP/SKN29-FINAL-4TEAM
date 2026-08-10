from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("visits", "0003_handoffreport"),
    ]

    operations = [
        migrations.AddField(
            model_name="visit",
            name="preferred_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="visit",
            name="confirmed_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="visit",
            name="visit_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="visit",
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
            model_name="visit",
            name="handoff_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
