"""T-005 ordered guidance-item model and migration tests."""

from uuid import UUID

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import PROTECT, ProtectedError

from apps.inquiries.models import Guidance, GuidanceItem, Inquiry
from tests.unit.inquiries.test_t022_models import create_inquiry


pytestmark = pytest.mark.django_db


def create_guidance(
    sequence: int,
    *,
    inquiry: Inquiry | None = None,
    review_status_code: str = "PENDING",
) -> Guidance:
    return Guidance.objects.create(
        inquiry=inquiry or create_inquiry(sequence),
        guidance_version=1,
        review_status_code=review_status_code,
        title=f"Guidance {sequence}",
        summary_text="Follow each step safely.",
        evidence_sufficiency_code="SUFFICIENT",
    )


def item_values(
    sequence: int,
    *,
    guidance: Guidance | None = None,
    **overrides,
):
    values = {
        "guidance": guidance or create_guidance(sequence),
        "step_no": 1,
        "action_type_code": "FUTURE_GUIDANCE_ACTION",
        "instruction_text": "Inspect the indicated part safely.",
    }
    values.update(overrides)
    return values


def test_guidance_item_uses_contract_identifiers_fields_and_defaults():
    item = GuidanceItem.objects.create(**item_values(1))

    assert isinstance(item.pk, int)
    assert isinstance(item.public_id, UUID)
    assert item._meta.db_table == "support_guidance_item"
    assert item.step_no == 1
    assert item.caution_text is None
    assert item.requires_confirmation is True
    assert item.created_at is not None
    assert item.updated_at is not None
    assert item.guidance.items.get() == item
    assert (
        GuidanceItem._meta.get_field("guidance").remote_field.on_delete
        is PROTECT
    )


def test_guidance_item_declares_only_approved_structural_constraints():
    constraints = {
        constraint.name
        for constraint in GuidanceItem._meta.constraints
    }

    assert constraints == {
        "ux_guidance_item_step",
        "ck_guidance_item_step",
        "ck_guidance_action_nonempty",
        "ck_guidance_item_instruction",
    }
    assert (
        "ck_support_guidance_item_action_type_code_allowed"
        not in constraints
    )


def test_unapproved_guidance_action_code_set_remains_open_and_required():
    action_field = GuidanceItem._meta.get_field("action_type_code")

    assert not action_field.choices
    item = GuidanceItem.objects.create(**item_values(2))
    assert item.action_type_code == "FUTURE_GUIDANCE_ACTION"

    for invalid_value in ("", "   ", "\t\r\n"):
        with pytest.raises(IntegrityError), transaction.atomic():
            GuidanceItem.objects.create(
                **item_values(
                    3,
                    action_type_code=invalid_value,
                )
            )


def test_database_rejects_nonpositive_or_duplicate_step():
    guidance = create_guidance(10)
    GuidanceItem.objects.create(
        **item_values(10, guidance=guidance)
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        GuidanceItem.objects.create(
            **item_values(
                11,
                guidance=guidance,
                step_no=0,
            )
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        GuidanceItem.objects.create(
            **item_values(
                12,
                guidance=guidance,
                action_type_code="ANOTHER_OPEN_ACTION",
            )
        )

    other_guidance = create_guidance(13)
    GuidanceItem.objects.create(
        **item_values(13, guidance=other_guidance)
    )
    assert GuidanceItem.objects.filter(step_no=1).count() == 2


@pytest.mark.parametrize(
    "instruction_text",
    ["", " ", "\t", "\r\n"],
)
def test_database_rejects_blank_instruction(instruction_text):
    with pytest.raises(IntegrityError), transaction.atomic():
        GuidanceItem.objects.create(
            **item_values(
                20,
                instruction_text=instruction_text,
            )
        )


def test_requires_confirmation_can_be_explicitly_disabled():
    item = GuidanceItem.objects.create(
        **item_values(
            30,
            requires_confirmation=False,
            caution_text="Stop immediately if leakage increases.",
        )
    )

    assert item.requires_confirmation is False
    assert item.caution_text is not None


def test_guidance_parent_deletion_is_protected():
    guidance = create_guidance(40)
    GuidanceItem.objects.create(
        **item_values(40, guidance=guidance)
    )

    with pytest.raises(ProtectedError):
        guidance.delete()


def test_approved_parent_immutability_has_no_unapproved_db_trigger():
    guidance = create_guidance(
        50,
        review_status_code="APPROVED",
    )
    GuidanceItem.objects.create(
        **item_values(50, guidance=guidance)
    )

    with connection.cursor() as cursor:
        if connection.vendor == "sqlite":
            cursor.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'trigger'
                  AND tbl_name = 'support_guidance_item'
                """
            )
            trigger_names = {row[0] for row in cursor.fetchall()}
        elif connection.vendor == "postgresql":
            cursor.execute(
                """
                SELECT tgname
                FROM pg_trigger
                WHERE tgrelid = 'support_guidance_item'::regclass
                  AND NOT tgisinternal
                """
            )
            trigger_names = {row[0] for row in cursor.fetchall()}
        else:
            pytest.fail(
                f"Unsupported database vendor: {connection.vendor}"
            )

    assert trigger_names == set()


def test_database_catalog_contains_guidance_item_constraints():
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(
            cursor,
            "support_guidance_item",
        )

    assert {
        "ux_guidance_item_step",
        "ck_guidance_item_step",
        "ck_guidance_action_nonempty",
        "ck_guidance_item_instruction",
    }.issubset(constraints)
    assert constraints["ux_guidance_item_step"]["unique"] is True
    assert constraints["ck_guidance_item_step"]["check"] is True


@pytest.mark.django_db(transaction=True)
def test_guidance_item_empty_migration_rolls_back_and_reapplies():
    target_0008 = [("inquiries", "0008_guidance")]
    target_0009 = [("inquiries", "0009_guidanceitem")]

    executor = MigrationExecutor(connection)
    executor.migrate(target_0008)
    with connection.cursor() as cursor:
        assert (
            "support_guidance_item"
            not in connection.introspection.table_names(cursor)
        )

    executor = MigrationExecutor(connection)
    executor.migrate(target_0009)
    guidance_item_0009 = executor.loader.project_state(
        target_0009
    ).apps.get_model("inquiries", "GuidanceItem")
    assert guidance_item_0009._meta.db_table == (
        "support_guidance_item"
    )
    with connection.cursor() as cursor:
        assert (
            "support_guidance_item"
            in connection.introspection.table_names(cursor)
        )

    executor = MigrationExecutor(connection)
    executor.migrate(target_0008)
    with connection.cursor() as cursor:
        assert (
            "support_guidance_item"
            not in connection.introspection.table_names(cursor)
        )

    executor = MigrationExecutor(connection)
    executor.migrate(target_0009)
