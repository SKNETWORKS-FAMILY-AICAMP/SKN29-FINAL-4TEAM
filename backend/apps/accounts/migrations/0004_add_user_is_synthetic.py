"""Add an explicit synthetic-account boundary and classify existing users."""

from __future__ import annotations

from django.db import migrations, models
from django.db.models import Count


DEMO_USERNAMES = {
    "DEMO-CUSTOMER-001",
    "DEMO-CONSULTANT-001",
    "DEMO-TECHNICIAN-001",
    "DEMO-OPERATOR-001",
}


def _duplicate_count(model, field_name: str, *, using: str) -> int:
    queryset = model.objects.using(using).exclude(
        **{f"{field_name}__isnull": True}
    )
    if model._meta.get_field(field_name).get_internal_type() == "CharField":
        queryset = queryset.exclude(**{field_name: ""})
    return (
        queryset.values(field_name)
        .annotate(row_count=Count("pk"))
        .filter(row_count__gt=1)
        .count()
    )


def classify_existing_users(apps, schema_editor) -> None:
    using = schema_editor.connection.alias
    User = apps.get_model("accounts", "User")
    CustomerProfile = apps.get_model("accounts", "CustomerProfile")
    SyntheticImportItem = apps.get_model(
        "operations",
        "SyntheticImportItem",
    )

    duplicate_counts = {
        "username": _duplicate_count(User, "username", using=using),
        "employee_no": _duplicate_count(
            User,
            "employee_no",
            using=using,
        ),
        "customer_no": _duplicate_count(
            CustomerProfile,
            "customer_no",
            using=using,
        ),
    }
    if any(duplicate_counts.values()):
        raise RuntimeError(
            "T-017B synthetic backfill aborted: duplicate business keys "
            f"detected ({duplicate_counts})."
        )

    classified_user_ids = set(
        User.objects.using(using)
        .filter(username__in=DEMO_USERNAMES)
        .values_list("pk", flat=True)
    )
    classified_user_ids.update(
        CustomerProfile.objects.using(using)
        .filter(is_synthetic=True)
        .values_list("user_id", flat=True)
    )

    ledger_rows = (
        SyntheticImportItem.objects.using(using)
        .filter(
            batch__profile="db-full",
            batch__status="COMPLETED",
            source_dataset="users",
            target_model="accounts.User",
        )
        .values(
            "source_public_id",
            "source_business_key",
            "target_public_id",
            "target_business_key",
        )
        .order_by("source_public_id", "pk")
    )

    source_mappings: dict[str, tuple[str, str, str]] = {}
    ledger_conflicts = 0
    ledger_targets: dict[str, str] = {}
    for row in ledger_rows.iterator():
        source_public_id = str(row["source_public_id"])
        source_business_key = str(row["source_business_key"])
        target_public_id = str(row["target_public_id"])
        target_business_key = str(row["target_business_key"])
        mapping = (
            source_business_key,
            target_public_id,
            target_business_key,
        )
        previous = source_mappings.setdefault(source_public_id, mapping)
        if previous != mapping:
            ledger_conflicts += 1
        if (
            source_public_id != target_public_id
            or source_business_key != target_business_key
        ):
            ledger_conflicts += 1
        ledger_targets[target_public_id] = target_business_key

    target_users = {
        str(public_id): (pk, username)
        for pk, public_id, username in User.objects.using(using)
        .filter(public_id__in=ledger_targets)
        .values_list("pk", "public_id", "username")
    }
    for target_public_id, target_business_key in ledger_targets.items():
        target = target_users.get(target_public_id)
        if target is None or target[1] != target_business_key:
            ledger_conflicts += 1
            continue
        classified_user_ids.add(target[0])

    if ledger_conflicts:
        raise RuntimeError(
            "T-017B synthetic backfill aborted: importer ledger "
            f"conflicts={ledger_conflicts}."
        )

    unclassified_count = (
        User.objects.using(using)
        .exclude(pk__in=classified_user_ids)
        .count()
    )
    if unclassified_count:
        raise RuntimeError(
            "T-017B synthetic backfill aborted: "
            f"unclassified_users={unclassified_count}."
        )

    User.objects.using(using).filter(pk__in=classified_user_ids).update(
        is_synthetic=True
    )
    remaining_null_count = User.objects.using(using).filter(
        is_synthetic__isnull=True
    ).count()
    if remaining_null_count:
        raise RuntimeError(
            "T-017B synthetic backfill verification failed: "
            f"remaining_null={remaining_null_count}."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_promote_integer_primary_keys"),
        ("operations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_synthetic",
            field=models.BooleanField(null=True),
        ),
        migrations.RunPython(
            classify_existing_users,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="user",
            name="is_synthetic",
            field=models.BooleanField(default=False),
        ),
    ]
