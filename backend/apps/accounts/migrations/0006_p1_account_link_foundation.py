"""Add the P1-A pre-signup customer email and account-link foundation."""

from __future__ import annotations

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import apps.accounts.models.contract_email_contact


def backfill_existing_customer_links(apps, schema_editor) -> None:
    """Mirror every existing direct CustomerProfile.user relation once."""

    using = schema_editor.connection.alias
    CustomerProfile = apps.get_model("accounts", "CustomerProfile")
    CustomerAccountLink = apps.get_model(
        "accounts",
        "CustomerAccountLink",
    )

    unsafe_profiles = CustomerProfile.objects.using(using).filter(
        models.Q(is_synthetic=False)
        | models.Q(user_id__isnull=True)
        | models.Q(deleted_at__isnull=False)
        | models.Q(user__is_synthetic=False)
        | ~models.Q(user__role_code="CUSTOMER")
        | models.Q(user__is_active=False)
    )
    duplicate_user_count = (
        CustomerProfile.objects.using(using)
        .values("user_id")
        .annotate(row_count=models.Count("pk"))
        .filter(row_count__gt=1)
        .count()
    )
    if unsafe_profiles.exists() or duplicate_user_count:
        raise RuntimeError(
            "P1-A account-link cutover requires active synthetic customer "
            "users and synthetic, owned, 1:1 CustomerProfile rows: "
            f"unsafe_profiles={unsafe_profiles.count()}, "
            f"duplicate_users={duplicate_user_count}."
        )

    expected: dict[int, int] = dict(
        CustomerProfile.objects.using(using).values_list("pk", "user_id")
    )
    for customer_id, user_id in expected.items():
        if user_id is None:
            raise RuntimeError(
                "P1-A account-link backfill encountered an unowned "
                "CustomerProfile before the nullable cutover."
            )
        link, created = CustomerAccountLink.objects.using(using).get_or_create(
            customer_id=customer_id,
            defaults={
                "user_id": user_id,
                "is_active": True,
                "linked_at": django.utils.timezone.now(),
                "revoked_at": None,
                "link_reason": "LEGACY_BACKFILL",
                "data_classification": "synthetic",
            },
        )
        if not created and (
            link.user_id != user_id
            or not link.is_active
            or link.link_reason != "LEGACY_BACKFILL"
        ):
            raise RuntimeError(
                "P1-A account-link backfill found a conflicting link."
            )

    missing = set(expected) - set(
        CustomerAccountLink.objects.using(using)
        .filter(is_active=True)
        .values_list("customer_id", flat=True)
    )
    duplicate_customers = (
        CustomerAccountLink.objects.using(using)
        .filter(is_active=True)
        .values("customer_id")
        .annotate(row_count=models.Count("pk"))
        .filter(row_count__gt=1)
        .count()
    )
    duplicate_users = (
        CustomerAccountLink.objects.using(using)
        .filter(is_active=True)
        .values("user_id")
        .annotate(row_count=models.Count("pk"))
        .filter(row_count__gt=1)
        .count()
    )
    if missing or duplicate_customers or duplicate_users:
        raise RuntimeError(
            "P1-A account-link backfill verification failed: "
            f"missing={len(missing)}, "
            f"duplicate_customers={duplicate_customers}, "
            f"duplicate_users={duplicate_users}."
        )


def remove_legacy_backfill_links(apps, schema_editor) -> None:
    """Only migration-owned links are eligible for pre-activation rollback."""

    CustomerAccountLink = apps.get_model(
        "accounts",
        "CustomerAccountLink",
    )
    CustomerAccountLink.objects.using(
        schema_editor.connection.alias
    ).filter(link_reason="LEGACY_BACKFILL").delete()


def forward_reverse_guard_noop(apps, schema_editor) -> None:
    del apps, schema_editor


def require_no_pre_signup_customers_for_reverse(apps, schema_editor) -> None:
    """0006 소유 데이터가 남은 rollback을 사전에 차단한다."""

    CustomerProfile = apps.get_model("accounts", "CustomerProfile")
    ContractEmailContact = apps.get_model("accounts", "ContractEmailContact")
    CustomerAccountLink = apps.get_model("accounts", "CustomerAccountLink")
    using = schema_editor.connection.alias
    null_owner_count = CustomerProfile.objects.using(using).filter(
        user_id__isnull=True
    ).count()
    contact_count = ContractEmailContact.objects.using(using).count()
    signup_link_count = CustomerAccountLink.objects.using(using).filter(
        link_reason="SIGN_UP_EMAIL_OTP"
    ).count()
    if null_owner_count or contact_count or signup_link_count:
        raise RuntimeError(
            "accounts.0006 reverse is blocked while P1-owned data exists: "
            f"null_owner_count={null_owner_count}, "
            f"contact_count={contact_count}, "
            f"signup_link_count={signup_link_count}."
        )


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ("accounts", "0005_account_lifecycle_and_audit"),
    ]
    operations = [
        migrations.CreateModel(
            name="ContractEmailContact",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "id",
                    models.BigAutoField(
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "public_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                    ),
                ),
                ("encrypted_email", models.TextField()),
                (
                    "email_lookup_hmac",
                    models.CharField(
                        max_length=64,
                        validators=[
                            apps.accounts.models.contract_email_contact
                            .validate_sha256_hex
                        ],
                    ),
                ),
                ("key_version", models.CharField(max_length=40)),
                ("is_active", models.BooleanField(default=True)),
                ("is_primary", models.BooleanField(default=True)),
                (
                    "delivery_policy",
                    models.CharField(
                        choices=[
                            (
                                "RUNTIME_REDIRECT_ONLY",
                                "시험 Runtime Redirect 전용",
                            )
                        ],
                        default="RUNTIME_REDIRECT_ONLY",
                        max_length=40,
                    ),
                ),
                (
                    "source_system",
                    models.CharField(
                        default="P1_ACCOUNT_LINK_FIXTURE",
                        max_length=40,
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
                (
                    "customer",
                    models.ForeignKey(
                        db_column="customer_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contract_email_contacts",
                        to="accounts.customerprofile",
                    ),
                ),
            ],
            options={
                "db_table": "accounts_contract_email_contact",
                "indexes": [
                    models.Index(
                        fields=["email_lookup_hmac", "is_active"],
                        name="ix_contract_email_hmac_active",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(
                            ("is_active", True),
                            ("is_primary", True),
                        ),
                        fields=("customer",),
                        name="ux_contract_email_active_primary_customer",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("is_active", True)),
                        fields=("customer", "email_lookup_hmac"),
                        name="ux_contract_email_active_customer_hmac",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("is_primary", False),
                            ("is_active", True),
                            _connector="OR",
                        ),
                        name="ck_contract_email_primary_active",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("data_classification", "synthetic")
                        ),
                        name="ck_contract_email_synthetic_only",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="CustomerAccountLink",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "id",
                    models.BigAutoField(
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "public_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "linked_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now
                    ),
                ),
                (
                    "revoked_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "link_reason",
                    models.CharField(
                        choices=[
                            (
                                "LEGACY_BACKFILL",
                                "기존 1:1 관계 Backfill",
                            ),
                            (
                                "SIGN_UP_EMAIL_OTP",
                                "계약 이메일 OTP 회원가입",
                            ),
                        ],
                        max_length=40,
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
                (
                    "customer",
                    models.ForeignKey(
                        db_column="customer_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="account_links",
                        to="accounts.customerprofile",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="customer_account_links",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "accounts_customer_account_link",
                "indexes": [
                    models.Index(
                        fields=["customer", "is_active"],
                        name="ix_cust_link_customer_active",
                    ),
                    models.Index(
                        fields=["user", "is_active"],
                        name="ix_cust_link_user_active",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("is_active", True)),
                        fields=("user",),
                        name="ux_customer_link_active_user",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("is_active", True)),
                        fields=("customer",),
                        name="ux_customer_link_active_customer",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("is_active", True),
                                ("revoked_at__isnull", True),
                            ),
                            models.Q(
                                ("is_active", False),
                                ("revoked_at__isnull", False),
                            ),
                            _connector="OR",
                        ),
                        name="ck_customer_link_active_revoked",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("data_classification", "synthetic")
                        ),
                        name="ck_customer_link_synthetic_only",
                    ),
                ],
            },
        ),
        migrations.RunPython(
            backfill_existing_customer_links,
            remove_legacy_backfill_links,
        ),
        migrations.AlterField(
            model_name="customerprofile",
            name="user",
            field=models.OneToOneField(
                blank=True,
                db_column="user_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="customer_profile",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(
            forward_reverse_guard_noop,
            require_no_pre_signup_customers_for_reverse,
        ),
    ]
