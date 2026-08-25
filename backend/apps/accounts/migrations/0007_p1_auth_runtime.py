"""Add P1 OTP, single-use ticket, consent and rate-limit ledgers."""

import uuid

import django.db.models.deletion
import django.db.models.functions.text
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def require_case_insensitive_unique_usernames(apps, schema_editor) -> None:
    User = apps.get_model("accounts", "User")
    using = schema_editor.connection.alias
    seen: set[str] = set()
    duplicates: set[str] = set()
    for username in User.objects.using(using).values_list(
        "username", flat=True
    ).iterator():
        normalized = str(username).casefold()
        if normalized in seen:
            duplicates.add(normalized)
        seen.add(normalized)
    if duplicates:
        raise RuntimeError(
            "P1 auth cutover found case-insensitive duplicate usernames: "
            f"count={len(duplicates)}."
        )


def preserve_case_insensitive_usernames(apps, schema_editor) -> None:
    del apps, schema_editor


def forward_reverse_guard_noop(apps, schema_editor) -> None:
    del apps, schema_editor


def require_empty_p1_auth_runtime_for_reverse(apps, schema_editor) -> None:
    """0007 인증 원장 데이터가 남은 rollback을 사전에 차단한다."""

    using = schema_editor.connection.alias
    model_names = (
        "P1AccountConsent",
        "P1AuthChallengeRateBucket",
        "P1AuthIdempotencyLock",
        "P1AuthLoginRateBucket",
        "P1AuthOperationReceipt",
        "P1AuthOtpChallenge",
        "P1AuthRateLimitEvent",
        "P1AuthTicket",
    )
    counts = {
        name: apps.get_model("accounts", name).objects.using(using).count()
        for name in model_names
    }
    if any(counts.values()):
        summary = ", ".join(
            f"{name}={counts[name]}" for name in sorted(counts)
        )
        raise RuntimeError(
            "accounts.0007 reverse is blocked while P1 auth data exists: "
            + summary
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_p1_account_link_foundation"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("subscriptions", "0002_add_synthetic_projection_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="P1AccountConsent",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "code",
                    models.CharField(
                        choices=[
                            ("TERMS_OF_SERVICE", "이용약관"),
                            (
                                "PRIVACY_COLLECTION_USE",
                                "개인정보 수집 이용",
                            ),
                            ("MARKETING", "마케팅"),
                        ],
                        max_length=40,
                    ),
                ),
                ("version", models.CharField(max_length=40)),
                ("agreed", models.BooleanField()),
                (
                    "recorded_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                (
                    "data_classification",
                    models.CharField(
                        default="synthetic", editable=False, max_length=20
                    ),
                ),
            ],
            options={"db_table": "accounts_p1_account_consent"},
        ),
        migrations.CreateModel(
            name="P1AuthChallengeRateBucket",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "purpose",
                    models.CharField(
                        choices=[
                            ("SIGNUP", "회원가입"),
                            ("USERNAME_RECOVERY", "아이디 찾기"),
                            ("PASSWORD_RESET", "비밀번호 재설정"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "request_fingerprint_hmac",
                    models.CharField(max_length=64),
                ),
                (
                    "window_started_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("request_count", models.PositiveIntegerField(default=0)),
                (
                    "last_requested_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "data_classification",
                    models.CharField(
                        default="synthetic", editable=False, max_length=20
                    ),
                ),
            ],
            options={
                "db_table": "accounts_p1_auth_challenge_rate_bucket",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("purpose", "request_fingerprint_hmac"),
                        name="ux_p1_challenge_rate_subject",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("data_classification", "synthetic")
                        ),
                        name="ck_p1_challenge_rate_synthetic",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="P1AuthIdempotencyLock",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "operation",
                    models.CharField(
                        choices=[
                            ("SIGNUP", "회원가입"),
                            ("PASSWORD_RESET", "비밀번호 재설정"),
                        ],
                        max_length=24,
                    ),
                ),
                ("idempotency_key_hmac", models.CharField(max_length=64)),
                (
                    "data_classification",
                    models.CharField(
                        default="synthetic", editable=False, max_length=20
                    ),
                ),
            ],
            options={
                "db_table": "accounts_p1_auth_idempotency_lock",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("operation", "idempotency_key_hmac"),
                        name="ux_p1_idempotency_lock_key",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("data_classification", "synthetic")
                        ),
                        name="ck_p1_idempotency_lock_synthetic",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="P1AuthOperationReceipt",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "operation",
                    models.CharField(
                        choices=[
                            ("SIGNUP", "회원가입"),
                            ("PASSWORD_RESET", "비밀번호 재설정"),
                        ],
                        max_length=24,
                    ),
                ),
                ("idempotency_key_hmac", models.CharField(max_length=64)),
                ("request_fingerprint_hmac", models.CharField(max_length=64)),
                (
                    "auth_version_at_completion",
                    models.PositiveIntegerField(default=1),
                ),
                (
                    "completed_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                (
                    "data_classification",
                    models.CharField(
                        default="synthetic", editable=False, max_length=20
                    ),
                ),
            ],
            options={"db_table": "accounts_p1_auth_operation_receipt"},
        ),
        migrations.CreateModel(
            name="P1AuthOtpChallenge",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "public_id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                (
                    "purpose",
                    models.CharField(
                        choices=[
                            ("SIGNUP", "회원가입"),
                            ("USERNAME_RECOVERY", "아이디 찾기"),
                            ("PASSWORD_RESET", "비밀번호 재설정"),
                        ],
                        max_length=32,
                    ),
                ),
                ("target_resolved", models.BooleanField(default=False)),
                ("idempotency_key_hmac", models.CharField(max_length=64)),
                ("request_fingerprint_hmac", models.CharField(max_length=64)),
                ("otp_digest", models.CharField(max_length=64)),
                ("expires_at", models.DateTimeField()),
                ("resend_not_before", models.DateTimeField()),
                ("failure_count", models.PositiveSmallIntegerField(default=0)),
                ("max_failures", models.PositiveSmallIntegerField(default=5)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("delivery_attempted", models.BooleanField(default=False)),
                (
                    "data_classification",
                    models.CharField(
                        default="synthetic", editable=False, max_length=20
                    ),
                ),
            ],
            options={"db_table": "accounts_p1_auth_otp_challenge"},
        ),
        migrations.CreateModel(
            name="P1AuthRateLimitEvent",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "action",
                    models.CharField(
                        choices=[("LOGIN_FAILURE", "로그인 실패")],
                        max_length=24,
                    ),
                ),
                ("subject_hmac", models.CharField(max_length=64)),
                (
                    "occurred_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now, editable=False
                    ),
                ),
            ],
            options={"db_table": "accounts_p1_auth_rate_limit_event"},
        ),
        migrations.CreateModel(
            name="P1AuthLoginRateBucket",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("subject_hmac", models.CharField(max_length=64, unique=True)),
                (
                    "window_started_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("failure_count", models.PositiveIntegerField(default=0)),
                (
                    "last_failed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "data_classification",
                    models.CharField(
                        default="synthetic", editable=False, max_length=20
                    ),
                ),
            ],
            options={
                "db_table": "accounts_p1_auth_login_rate_bucket",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("data_classification", "synthetic")
                        ),
                        name="ck_p1_login_rate_synthetic",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="P1AuthTicket",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "public_id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                (
                    "purpose",
                    models.CharField(
                        choices=[
                            ("CLAIM", "회원가입 Claim"),
                            ("PASSWORD_RESET", "비밀번호 재설정"),
                        ],
                        max_length=24,
                    ),
                ),
                ("digest", models.CharField(max_length=64, unique=True)),
                (
                    "auth_version_at_issue",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("expires_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "data_classification",
                    models.CharField(
                        default="synthetic", editable=False, max_length=20
                    ),
                ),
            ],
            options={"db_table": "accounts_p1_auth_ticket"},
        ),
        migrations.RunPython(
            require_case_insensitive_unique_usernames,
            preserve_case_insensitive_usernames,
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower("username"),
                name="ux_accounts_user_username_ci",
            ),
        ),
        migrations.AddField(
            model_name="p1accountconsent",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="p1_account_consents",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="p1authoperationreceipt",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="p1_auth_operation_receipts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="p1authotpchallenge",
            name="contact",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="p1_auth_challenges",
                to="accounts.contractemailcontact",
            ),
        ),
        migrations.AddField(
            model_name="p1authotpchallenge",
            name="customer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="p1_auth_challenges",
                to="accounts.customerprofile",
            ),
        ),
        migrations.AddField(
            model_name="p1authotpchallenge",
            name="subscription",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="p1_auth_challenges",
                to="subscriptions.customersubscription",
            ),
        ),
        migrations.AddField(
            model_name="p1authotpchallenge",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="p1_auth_challenges",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name="p1authratelimitevent",
            index=models.Index(
                fields=["action", "subject_hmac", "occurred_at"],
                name="ix_p1_rate_subject_time",
            ),
        ),
        migrations.AddField(
            model_name="p1authticket",
            name="challenge",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ticket",
                to="accounts.p1authotpchallenge",
            ),
        ),
        migrations.AddField(
            model_name="p1authticket",
            name="customer",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="p1_auth_tickets",
                to="accounts.customerprofile",
            ),
        ),
        migrations.AddField(
            model_name="p1authticket",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="p1_auth_tickets",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="p1accountconsent",
            constraint=models.UniqueConstraint(
                fields=("user", "code", "version"),
                name="ux_p1_consent_user_code_version",
            ),
        ),
        migrations.AddConstraint(
            model_name="p1accountconsent",
            constraint=models.CheckConstraint(
                condition=models.Q(("data_classification", "synthetic")),
                name="ck_p1_consent_synthetic_only",
            ),
        ),
        migrations.AddConstraint(
            model_name="p1authoperationreceipt",
            constraint=models.UniqueConstraint(
                fields=("operation", "idempotency_key_hmac"),
                name="ux_p1_receipt_operation_idem",
            ),
        ),
        migrations.AddConstraint(
            model_name="p1authoperationreceipt",
            constraint=models.CheckConstraint(
                condition=models.Q(("data_classification", "synthetic")),
                name="ck_p1_receipt_synthetic_only",
            ),
        ),
        migrations.AddConstraint(
            model_name="p1authoperationreceipt",
            constraint=models.CheckConstraint(
                condition=models.Q(("auth_version_at_completion__gte", 1)),
                name="ck_p1_receipt_auth_version_gte_1",
            ),
        ),
        migrations.AddIndex(
            model_name="p1authotpchallenge",
            index=models.Index(
                fields=["purpose", "request_fingerprint_hmac", "created_at"],
                name="ix_p1_otp_request_created",
            ),
        ),
        migrations.AddIndex(
            model_name="p1authotpchallenge",
            index=models.Index(
                fields=["expires_at"], name="ix_p1_otp_expires"
            ),
        ),
        migrations.AddConstraint(
            model_name="p1authotpchallenge",
            constraint=models.UniqueConstraint(
                fields=("purpose", "idempotency_key_hmac"),
                name="ux_p1_otp_purpose_idem_hmac",
            ),
        ),
        migrations.AddConstraint(
            model_name="p1authotpchallenge",
            constraint=models.CheckConstraint(
                condition=models.Q(("data_classification", "synthetic")),
                name="ck_p1_otp_synthetic_only",
            ),
        ),
        migrations.AddConstraint(
            model_name="p1authotpchallenge",
            constraint=models.CheckConstraint(
                condition=models.Q(("max_failures__gte", 1)),
                name="ck_p1_otp_max_failures_gte_1",
            ),
        ),
        migrations.AddConstraint(
            model_name="p1authotpchallenge",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("failure_count__lte", models.F("max_failures"))
                ),
                name="ck_p1_otp_failures_lte_max",
            ),
        ),
        migrations.AddIndex(
            model_name="p1authticket",
            index=models.Index(
                fields=["expires_at"], name="ix_p1_ticket_expires"
            ),
        ),
        migrations.AddConstraint(
            model_name="p1authticket",
            constraint=models.CheckConstraint(
                condition=models.Q(("data_classification", "synthetic")),
                name="ck_p1_ticket_synthetic_only",
            ),
        ),
        migrations.AddConstraint(
            model_name="p1authticket",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("auth_version_at_issue__isnull", True),
                    ("purpose", "CLAIM"),
                    ("user__isnull", True),
                )
                | models.Q(
                    ("auth_version_at_issue__gte", 1),
                    ("purpose", "PASSWORD_RESET"),
                    ("user__isnull", False),
                ),
                name="ck_p1_ticket_purpose_binding",
            ),
        ),
        migrations.RunPython(
            forward_reverse_guard_noop,
            require_empty_p1_auth_runtime_for_reverse,
        ),
    ]
