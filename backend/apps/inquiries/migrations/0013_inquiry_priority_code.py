from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("inquiries", "0012_alter_inquiry_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="inquiry",
            name="priority_code",
            field=models.CharField(
                choices=[
                    ("LOW", "Low"),
                    ("NORMAL", "Normal"),
                    ("HIGH", "High"),
                    ("URGENT", "Urgent"),
                ],
                default="NORMAL",
                max_length=40,
            ),
        ),
        migrations.AddConstraint(
            model_name="inquiry",
            constraint=models.CheckConstraint(
                condition=Q(
                    priority_code__in=[
                        "LOW",
                        "NORMAL",
                        "HIGH",
                        "URGENT",
                    ]
                ),
                name="ck_inquiry_priority_code",
            ),
        ),
    ]
