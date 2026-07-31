"""PostgreSQL에서 문진 세션과 문의의 동일 구독을 강제한다."""

from django.db import migrations


CONSTRAINT_NAME = "fk_questionnaire_inquiry_subscription"
QUESTIONNAIRE_TABLE = "support_questionnaire_session"
INQUIRY_TABLE = "support_inquiry"


def add_inquiry_subscription_fk(apps, schema_editor):
    """PostgreSQL에 계약상의 복합 FK를 추가한다."""

    if schema_editor.connection.vendor != "postgresql":
        return

    schema_editor.execute(
        f"""
        ALTER TABLE {QUESTIONNAIRE_TABLE}
        ADD CONSTRAINT {CONSTRAINT_NAME}
        FOREIGN KEY (inquiry_id, subscription_id)
        REFERENCES {INQUIRY_TABLE} (id, subscription_id)
        MATCH SIMPLE
        ON DELETE RESTRICT
        """
    )


def remove_inquiry_subscription_fk(apps, schema_editor):
    """역방향 Migration에서 복합 FK만 제거한다."""

    if schema_editor.connection.vendor != "postgresql":
        return

    schema_editor.execute(
        f"""
        ALTER TABLE {QUESTIONNAIRE_TABLE}
        DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}
        """
    )


class Migration(migrations.Migration):

    dependencies = [
        ("inquiries", "0005_inquiry_ux_inquiry_id_subscription"),
        ("questionnaires", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            add_inquiry_subscription_fk,
            reverse_code=remove_inquiry_subscription_fk,
        ),
    ]
