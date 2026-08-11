from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("inquiries", "0011_split_followup_question_metadata_and_answers"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="inquiry",
            options={
                "permissions": [("cancel_inquiry", "Can cancel inquiry")],
            },
        ),
    ]
