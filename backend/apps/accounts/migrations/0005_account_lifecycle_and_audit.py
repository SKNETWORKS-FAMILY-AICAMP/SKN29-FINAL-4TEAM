"""Add T-017C token generation, lifecycle lock, and account audit ledger."""

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def initialize_lifecycle_cutover(apps, schema_editor):
    del schema_editor
    LifecycleLock = apps.get_model("accounts", "AccountLifecycleLock")
    OutstandingToken = apps.get_model("token_blacklist", "OutstandingToken")
    BlacklistedToken = apps.get_model("token_blacklist", "BlacklistedToken")

    LifecycleLock.objects.update_or_create(
        pk=1,
        defaults={"label": "ACCOUNT_LIFECYCLE"},
    )
    for token_id in OutstandingToken.objects.values_list("pk", flat=True).iterator():
        BlacklistedToken.objects.get_or_create(token_id=token_id)


def preserve_revocations_on_reverse(apps, schema_editor):
    # Never resurrect refresh tokens during a disposable-QA schema rollback.
    del apps, schema_editor


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_add_user_is_synthetic"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("token_blacklist", "0013_alter_blacklistedtoken_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountAuditEvent",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "public_id",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("CREATE", "Create"),
                            ("UPDATE", "Update"),
                            ("DEACTIVATE", "Deactivate"),
                            ("REACTIVATE", "Reactivate"),
                            ("ROLE_CHANGE", "Role change"),
                            (
                                "ADMIN_PERMISSION_CHANGE",
                                "Admin permission change",
                            ),
                            ("PASSWORD_CHANGE", "Password change"),
                            ("PASSWORD_RESET", "Password reset"),
                            ("CREDENTIAL_RECOVERY", "Credential recovery"),
                        ],
                        max_length=40,
                    ),
                ),
                ("before_values", models.JSONField(blank=True, default=dict)),
                ("after_values", models.JSONField(default=dict)),
                ("changed_fields", models.JSONField(default=list)),
                ("reason", models.TextField()),
                ("correlation_id", models.UUIDField()),
                (
                    "occurred_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        editable=False,
                    ),
                ),
                (
                    "data_classification",
                    models.CharField(
                        default="synthetic",
                        editable=False,
                        max_length=20,
                    ),
                ),
            ],
            options={
                "db_table": "accounts_account_audit_event",
                "ordering": ("occurred_at", "id"),
            },
        ),
        migrations.CreateModel(
            name="AccountLifecycleLock",
            fields=[
                (
                    "id",
                    models.PositiveSmallIntegerField(
                        default=1,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        default="ACCOUNT_LIFECYCLE",
                        max_length=40,
                    ),
                ),
            ],
            options={"db_table": "accounts_account_lifecycle_lock"},
        ),
        migrations.AddField(
            model_name="user",
            name="auth_version",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(("auth_version__gte", 1)),
                name="accounts_user_auth_version_gte_1",
            ),
        ),
        migrations.AddField(
            model_name="accountauditevent",
            name="actor",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="performed_account_audit_events",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="accountauditevent",
            name="target_user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="account_audit_events",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="accountlifecyclelock",
            constraint=models.CheckConstraint(
                condition=models.Q(("id", 1)),
                name="acct_lifecycle_lock_singleton",
            ),
        ),
        migrations.AddIndex(
            model_name="accountauditevent",
            index=models.Index(
                fields=["target_user", "occurred_at"],
                name="acct_audit_target_time_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="accountauditevent",
            index=models.Index(
                fields=["correlation_id"],
                name="acct_audit_correlation_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="accountauditevent",
            constraint=models.CheckConstraint(
                condition=models.Q(("data_classification", "synthetic")),
                name="acct_audit_synthetic_only",
            ),
        ),
        migrations.AddConstraint(
            model_name="accountauditevent",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "event_type__in",
                        (
                            "CREATE",
                            "UPDATE",
                            "DEACTIVATE",
                            "REACTIVATE",
                            "ROLE_CHANGE",
                            "ADMIN_PERMISSION_CHANGE",
                            "PASSWORD_CHANGE",
                            "PASSWORD_RESET",
                            "CREDENTIAL_RECOVERY",
                        ),
                    )
                ),
                name="acct_audit_valid_event_type",
            ),
        ),
        migrations.RunPython(
            initialize_lifecycle_cutover,
            preserve_revocations_on_reverse,
        ),
    ]
