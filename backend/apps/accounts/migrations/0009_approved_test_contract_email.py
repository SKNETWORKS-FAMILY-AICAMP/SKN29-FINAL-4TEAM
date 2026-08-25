"""Allow PM-approved local E2E recipients without weakening production."""

from django.db import migrations, models


def forward_reverse_guard_noop(apps, schema_editor) -> None:
    del apps, schema_editor


def require_no_approved_test_contacts_for_reverse(apps, schema_editor) -> None:
    ContractEmailContact = apps.get_model("accounts", "ContractEmailContact")
    count = ContractEmailContact.objects.using(
        schema_editor.connection.alias
    ).filter(data_classification="approved_test_pii").count()
    if count:
        raise RuntimeError(
            "accounts.0009 reverse is blocked while PM-approved local "
            f"test contacts exist: count={count}."
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0008_p1_auth_email_outbox")]

    operations = [
        migrations.RemoveConstraint(
            model_name="contractemailcontact",
            name="ck_contract_email_synthetic_only",
        ),
        migrations.AlterField(
            model_name="contractemailcontact",
            name="data_classification",
            field=models.CharField(
                choices=[
                    ("synthetic", "합성 데이터"),
                    ("approved_test_pii", "PM 승인 로컬 시험 개인정보"),
                ],
                default="synthetic",
                editable=False,
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="contractemailcontact",
            name="delivery_policy",
            field=models.CharField(
                choices=[
                    ("RUNTIME_REDIRECT_ONLY", "시험 Runtime Redirect 전용"),
                    ("APPROVED_TEST_RECIPIENT", "PM 승인 로컬 시험 수신자"),
                ],
                default="RUNTIME_REDIRECT_ONLY",
                max_length=40,
            ),
        ),
        migrations.AddConstraint(
            model_name="contractemailcontact",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        data_classification="synthetic",
                        delivery_policy="RUNTIME_REDIRECT_ONLY",
                    )
                    | models.Q(
                        data_classification="approved_test_pii",
                        delivery_policy="APPROVED_TEST_RECIPIENT",
                    )
                ),
                name="ck_contract_email_class_policy",
            ),
        ),
        migrations.RunPython(
            forward_reverse_guard_noop,
            require_no_approved_test_contacts_for_reverse,
        ),
    ]
