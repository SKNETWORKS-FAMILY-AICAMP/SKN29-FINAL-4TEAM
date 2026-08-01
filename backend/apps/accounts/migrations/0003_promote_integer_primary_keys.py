"""Promote the transitional Accounts string keys to internal bigint keys.

The legacy identifiers are copied to non-public ``legacy_id`` columns before
the primary and foreign-key values are deterministically remapped to numeric
strings. Django can then perform its normal CharField -> BigAutoField schema
alteration without relying on an invalid ``USR-*``/``CUS-*`` bigint cast.
"""

from __future__ import annotations

from django.core.management.color import no_style
from django.db import migrations, models
from django.db.models import F

import common.identifiers


SUPPORTED_VENDORS = {"postgresql", "sqlite"}


def _integer_mapping(model, *, using: str) -> dict[str, int]:
    identifiers = [
        str(value)
        for value in model.objects.using(using)
        .order_by("id")
        .values_list("id", flat=True)
    ]
    if len(identifiers) != len(set(identifiers)):
        raise RuntimeError(
            f"{model._meta.db_table} contains duplicate primary keys."
        )
    if any(not value or value.isdecimal() for value in identifiers):
        raise RuntimeError(
            f"{model._meta.db_table} contains an empty or already-numeric "
            "legacy key; aborting the deterministic Accounts cutover."
        )
    return {
        legacy_id: sequence
        for sequence, legacy_id in enumerate(identifiers, start=1)
    }


def _related_fields(target_model):
    for relation in target_model._meta.related_objects:
        if relation.many_to_many:
            continue
        field = relation.field
        if field.target_field.name == target_model._meta.pk.name:
            yield relation.related_model, field


def _all_inbound_foreign_key_fields(target_model):
    for relation in target_model._meta.get_fields(include_hidden=True):
        if not relation.auto_created or not relation.is_relation:
            continue
        if relation.many_to_many:
            continue
        field = relation.field
        target_field = getattr(field, "target_field", None)
        if (
            target_field is not None
            and target_field.name == target_model._meta.pk.name
        ):
            yield relation.related_model, field


def _m2m_models(user_model):
    groups = user_model._meta.get_field("groups").remote_field.through
    permissions = user_model._meta.get_field(
        "user_permissions"
    ).remote_field.through
    return groups, permissions


def _drop_inbound_foreign_keys(schema_editor, target_model) -> None:
    for related_model, field in _all_inbound_foreign_key_fields(
        target_model
    ):
        names = schema_editor._constraint_names(  # noqa: SLF001
            related_model,
            [field.column],
            foreign_key=True,
        )
        for name in names:
            schema_editor.execute(
                schema_editor._delete_fk_sql(related_model, name)  # noqa: SLF001
            )


def _rewrite_column(
    schema_editor,
    *,
    table: str,
    column: str,
    mapping: dict[str, int],
) -> None:
    if not mapping:
        return
    quote = schema_editor.quote_name
    sql = (
        f"UPDATE {quote(table)} "
        f"SET {quote(column)} = %s "
        f"WHERE {quote(column)} = %s"
    )
    params = [
        (str(internal_id), legacy_id)
        for legacy_id, internal_id in mapping.items()
    ]
    with schema_editor.connection.cursor() as cursor:
        cursor.executemany(sql, params)


def _rewrite_related_columns(
    schema_editor,
    target_model,
    mapping: dict[str, int],
) -> None:
    for related_model, field in _related_fields(target_model):
        _rewrite_column(
            schema_editor,
            table=related_model._meta.db_table,
            column=field.column,
            mapping=mapping,
        )


def _rewrite_user_m2m(
    schema_editor,
    user_model,
    user_mapping: dict[str, int],
) -> None:
    for through_model in _m2m_models(user_model):
        user_field = through_model._meta.get_field("user")
        _rewrite_column(
            schema_editor,
            table=through_model._meta.db_table,
            column=user_field.column,
            mapping=user_mapping,
        )


def prepare_integer_primary_keys(apps, schema_editor) -> None:
    connection = schema_editor.connection
    if connection.vendor not in SUPPORTED_VENDORS:
        raise RuntimeError(
            "Accounts integer-PK migration supports PostgreSQL and SQLite "
            f"only, not {connection.vendor!r}."
        )

    using = connection.alias
    user_model = apps.get_model("accounts", "User")
    profile_model = apps.get_model("accounts", "CustomerProfile")
    user_mapping = _integer_mapping(user_model, using=using)
    profile_mapping = _integer_mapping(profile_model, using=using)

    user_model.objects.using(using).filter(
        legacy_id__isnull=True
    ).update(legacy_id=F("id"))
    profile_model.objects.using(using).filter(
        legacy_id__isnull=True
    ).update(legacy_id=F("id"))

    if connection.vendor == "postgresql":
        _drop_inbound_foreign_keys(schema_editor, user_model)
        _drop_inbound_foreign_keys(schema_editor, profile_model)
    else:
        # SQLite's AlterField implementation rebuilds the related tables.
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA defer_foreign_keys = ON")

    # Keep the implicit through tables in place. Django's PK AlterField sees
    # their hidden reverse FKs and changes user_id to bigint together with
    # every other inbound relation. Deleting the tables first makes that
    # AlterField fail on PostgreSQL with UndefinedTable.
    _rewrite_user_m2m(
        schema_editor,
        user_model,
        user_mapping,
    )

    _rewrite_related_columns(
        schema_editor,
        user_model,
        user_mapping,
    )
    _rewrite_column(
        schema_editor,
        table=user_model._meta.db_table,
        column=user_model._meta.pk.column,
        mapping=user_mapping,
    )
    _rewrite_related_columns(
        schema_editor,
        profile_model,
        profile_mapping,
    )
    _rewrite_column(
        schema_editor,
        table=profile_model._meta.db_table,
        column=profile_model._meta.pk.column,
        mapping=profile_mapping,
    )

    expected_user_ids = {str(value) for value in user_mapping.values()}
    expected_profile_ids = {
        str(value) for value in profile_mapping.values()
    }
    actual_user_ids = {
        str(value)
        for value in user_model.objects.using(using).values_list(
            "id",
            flat=True,
        )
    }
    actual_profile_ids = {
        str(value)
        for value in profile_model.objects.using(using).values_list(
            "id",
            flat=True,
        )
    }
    if actual_user_ids != expected_user_ids:
        raise RuntimeError("User primary-key backfill verification failed.")
    if actual_profile_ids != expected_profile_ids:
        raise RuntimeError(
            "CustomerProfile primary-key backfill verification failed."
        )

    if connection.vendor == "postgresql":
        # UPDATE statements against tables with deferred foreign keys can
        # leave queued RI trigger events. PostgreSQL rejects the following
        # AlterField DDL while those events are pending, even when the rows
        # are already consistent. Validate and drain them without giving up
        # the migration's single atomic transaction.
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def _assert_no_orphans(schema_editor, target_model) -> None:
    quote = schema_editor.quote_name
    parent_table = quote(target_model._meta.db_table)
    parent_column = quote(target_model._meta.pk.column)
    with schema_editor.connection.cursor() as cursor:
        for related_model, field in _related_fields(target_model):
            child_table = quote(related_model._meta.db_table)
            child_column = quote(field.column)
            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM {child_table} child
                LEFT JOIN {parent_table} parent
                  ON child.{child_column} = parent.{parent_column}
                WHERE child.{child_column} IS NOT NULL
                  AND parent.{parent_column} IS NULL
                """
            )
            if cursor.fetchone()[0]:
                raise RuntimeError(
                    f"Orphaned FK detected: "
                    f"{related_model._meta.db_table}.{field.column}"
                )


def reset_sequences_and_verify(apps, schema_editor) -> None:
    user_model = apps.get_model("accounts", "User")
    profile_model = apps.get_model("accounts", "CustomerProfile")
    if user_model._meta.pk.get_internal_type() != "BigAutoField":
        raise RuntimeError("accounts.User.id is not a BigAutoField.")
    if profile_model._meta.pk.get_internal_type() != "BigAutoField":
        raise RuntimeError(
            "accounts.CustomerProfile.id is not a BigAutoField."
        )

    _assert_no_orphans(schema_editor, user_model)
    _assert_no_orphans(schema_editor, profile_model)

    sql_list = schema_editor.connection.ops.sequence_reset_sql(
        no_style(),
        [user_model, profile_model],
    )
    with schema_editor.connection.cursor() as cursor:
        for sql in sql_list:
            cursor.execute(sql)


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ("accounts", "0002_add_public_identifiers"),
        ("audit", "0001_initial"),
        ("care", "0001_initial"),
        ("token_blacklist", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="legacy_id",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=48,
                null=True,
                unique=True,
                validators=[common.identifiers.validate_domain_id],
            ),
        ),
        migrations.AddField(
            model_name="customerprofile",
            name="legacy_id",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=48,
                null=True,
                unique=True,
                validators=[common.identifiers.validate_domain_id],
            ),
        ),
        migrations.RunPython(prepare_integer_primary_keys),
        migrations.AlterField(
            model_name="user",
            name="id",
            field=models.BigAutoField(
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.AlterField(
            model_name="customerprofile",
            name="id",
            field=models.BigAutoField(
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.RunPython(
            reset_sequences_and_verify,
            migrations.RunPython.noop,
        ),
    ]
