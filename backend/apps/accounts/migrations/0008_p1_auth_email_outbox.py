"""Add the asynchronous P1 OTP email outbox."""

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


def forward_reverse_guard_noop(apps, schema_editor) -> None:
    del apps, schema_editor


def require_empty_p1_outbox_for_reverse(apps, schema_editor) -> None:
    """0008 Outbox 데이터가 남은 rollback을 사전에 차단한다."""

    P1AuthEmailOutbox = apps.get_model("accounts", "P1AuthEmailOutbox")
    using = schema_editor.connection.alias
    outbox_count = P1AuthEmailOutbox.objects.using(using).count()
    if outbox_count:
        raise RuntimeError(
            "accounts.0008 reverse is blocked while P1 outbox data exists: "
            f"outbox_count={outbox_count}."
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0007_p1_auth_runtime")]

    operations = [
        migrations.CreateModel(
            name="P1AuthEmailOutbox",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("encrypted_otp", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "전송 대기"),
                            ("SENT", "전송 완료"),
                            ("FAILED", "전송 실패"),
                            ("SUPPRESSED", "대상 없음"),
                        ],
                        default="PENDING",
                        max_length=16,
                    ),
                ),
                ("attempt_count", models.PositiveSmallIntegerField(default=0)),
                ("max_attempts", models.PositiveSmallIntegerField(default=3)),
                (
                    "available_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("last_error_code", models.CharField(blank=True, max_length=40)),
                (
                    "data_classification",
                    models.CharField(
                        default="synthetic", editable=False, max_length=20
                    ),
                ),
                (
                    "challenge",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="email_outbox",
                        to="accounts.p1authotpchallenge",
                    ),
                ),
                (
                    "contact",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="p1_auth_email_outbox_rows",
                        to="accounts.contractemailcontact",
                    ),
                ),
            ],
            options={
                "db_table": "accounts_p1_auth_email_outbox",
                "indexes": [
                    models.Index(
                        fields=["status", "available_at"],
                        name="ix_p1_email_outbox_pending",
                    )
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("data_classification", "synthetic")
                        ),
                        name="ck_p1_email_outbox_synthetic_only",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("max_attempts__gte", 1)),
                        name="ck_p1_email_outbox_max_attempts",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("attempt_count__lte", models.F("max_attempts"))
                        ),
                        name="ck_p1_email_outbox_attempts_lte_max",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "attempt_count__lt",
                                models.F("max_attempts"),
                            ),
                            ("encrypted_otp__gt", ""),
                            ("sent_at__isnull", True),
                            ("status", "PENDING"),
                        )
                        | models.Q(
                            ("attempt_count__gte", 1),
                            ("encrypted_otp", ""),
                            ("sent_at__isnull", False),
                            ("status", "SENT"),
                        )
                        | models.Q(
                            (
                                "attempt_count",
                                models.F("max_attempts"),
                            ),
                            ("encrypted_otp", ""),
                            ("sent_at__isnull", True),
                            ("status", "FAILED"),
                        )
                        | models.Q(
                            ("encrypted_otp", ""),
                            ("sent_at__isnull", True),
                            ("status", "SUPPRESSED"),
                        ),
                        name="ck_p1_email_outbox_state",
                    ),
                ],
            },
        ),
        # Reverse에서는 operations가 역순 실행되므로 이 guard가 가장 먼저
        # 평가되어 0007 인증 원장을 부분 삭제하기 전에 중단한다.
        migrations.RunPython(
            forward_reverse_guard_noop,
            require_empty_p1_outbox_for_reverse,
        ),
    ]
