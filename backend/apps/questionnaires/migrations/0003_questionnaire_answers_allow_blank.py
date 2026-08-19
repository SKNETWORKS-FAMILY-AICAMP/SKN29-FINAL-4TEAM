"""Allow the intentional empty payload of a new UNANSWERED precheck."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("questionnaires", "0002_postgresql_inquiry_subscription_fk"),
    ]

    operations = [
        migrations.AlterField(
            model_name="questionnairesession",
            name="answers_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
