from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("operations", "0002_consultant_dashboard_projection"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="syntheticimportbatch",
            name="ck_syn_import_batch_profile",
        ),
        migrations.RemoveConstraint(
            model_name="syntheticimportbatch",
            name="ck_syn_import_profile_count",
        ),
        migrations.AlterField(
            model_name="syntheticimportbatch",
            name="profile",
            field=models.CharField(
                choices=[
                    ("db-smoke", "DB smoke"),
                    ("db-full", "DB full"),
                    ("db-product-expansion", "DB product expansion"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="syntheticimportbatch",
            constraint=models.CheckConstraint(
                condition=Q(
                    profile__in=[
                        "db-smoke",
                        "db-full",
                        "db-product-expansion",
                    ]
                ),
                name="ck_syn_import_batch_profile",
            ),
        ),
        migrations.AddConstraint(
            model_name="syntheticimportbatch",
            constraint=models.CheckConstraint(
                condition=(
                    Q(profile="db-smoke", source_count=37)
                    | Q(profile="db-full", source_count=367)
                    | Q(profile="db-product-expansion", source_count=2)
                ),
                name="ck_syn_import_profile_count",
            ),
        ),
    ]
