"""T-005 customer action-result model and migration tests."""

from uuid import UUID

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import PROTECT, ProtectedError
from django.utils import timezone

from apps.accounts.models import User
from apps.inquiries.models import (
    CustomerActionResult,
    Guidance,
    GuidanceItem,
    Inquiry,
)
from tests.unit.inquiries.test_t022_models import create_inquiry


pytestmark = pytest.mark.django_db


def create_guidance_item(
    sequence: int,
    *,
    inquiry: Inquiry | None = None,
) -> GuidanceItem:
    guidance = Guidance.objects.create(
        inquiry=inquiry or create_inquiry(sequence),
        guidance_version=1,
        title=f"Action result guidance {sequence}",
        summary_text="Follow each action step safely.",
        evidence_sufficiency_code="SUFFICIENT",
    )
    return GuidanceItem.objects.create(
        guidance=guidance,
        step_no=1,
        action_type_code="FUTURE_GUIDANCE_ACTION",
        instruction_text="Inspect the indicated part safely.",
    )


def create_submitter(sequence: int) -> User:
    return User.objects.create_user(
        username=f"ACTION-RESULT-SUBMITTER-{sequence:04d}",
        password=None,
        full_name=f"Action result submitter {sequence}",
        role_code=User.Role.CUSTOMER,
    )


def result_values(
    sequence: int,
    *,
    guidance_item: GuidanceItem | None = None,
    submitted_by: User | None = None,
    **overrides,
):
    assigned_item = guidance_item or create_guidance_item(sequence)
    values = {
        "guidance_item": assigned_item,
        "attempt_no": 1,
        "result_code": "FUTURE_ACTION_RESULT",
        "submitted_by": (
            submitted_by
            or assigned_item.guidance.inquiry.initiated_by
        ),
        "idempotency_key": f"action-result-{sequence:04d}",
    }
    values.update(overrides)
    return values


def test_action_result_uses_contract_identifiers_fields_and_defaults():
    result = CustomerActionResult.objects.create(**result_values(1))

    assert isinstance(result.pk, int)
    assert isinstance(result.public_id, UUID)
    assert result._meta.db_table == "support_customer_action_result"
    assert result.attempt_no == 1
    assert result.result_text is None
    assert result.performed_at is None
    assert result.customer_comment is None
    assert result.created_at is not None
    assert not hasattr(result, "updated_at")
    assert result.guidance_item.action_results.get() == result
    assert len(CustomerActionResult._meta.concrete_fields) == 11


def test_action_result_declares_contract_constraints_and_index():
    constraint_names = {
        constraint.name
        for constraint in CustomerActionResult._meta.constraints
    }
    index_names = {
        index.name for index in CustomerActionResult._meta.indexes
    }

    assert constraint_names == {
        "ux_action_result_attempt",
        "ux_action_result_idempotency",
        "ck_action_result_attempt",
        "ck_action_result_code_nonempty",
        "ck_action_result_idem_nonempty",
    }
    assert index_names == {
        "ix_action_result_guidance_item",
    }


def test_unapproved_action_result_code_set_and_semantics_remain_open():
    result_field = CustomerActionResult._meta.get_field("result_code")
    constraint_names = {
        constraint.name
        for constraint in CustomerActionResult._meta.constraints
    }

    assert not result_field.choices
    assert "ck_action_result_performed" not in constraint_names
    assert (
        "ck_support_customer_action_result_result_code_allowed"
        not in constraint_names
    )

    result = CustomerActionResult.objects.create(
        **result_values(
            2,
            result_code="FUTURE_ACTION_RESULT",
            performed_at=None,
        )
    )
    assert result.result_code == "FUTURE_ACTION_RESULT"
    assert result.performed_at is None


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("result_code", ""),
        ("result_code", " \t\r\n"),
        ("idempotency_key", ""),
        ("idempotency_key", "   "),
    ],
)
def test_database_rejects_blank_required_codes(field_name, value):
    with pytest.raises(IntegrityError), transaction.atomic():
        CustomerActionResult.objects.create(
            **result_values(
                10,
                **{field_name: value},
            )
        )


def test_database_rejects_nonpositive_or_duplicate_attempt():
    item = create_guidance_item(20)
    CustomerActionResult.objects.create(
        **result_values(20, guidance_item=item)
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        CustomerActionResult.objects.create(
            **result_values(
                21,
                guidance_item=item,
                attempt_no=0,
            )
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        CustomerActionResult.objects.create(
            **result_values(
                22,
                guidance_item=item,
            )
        )

    second = CustomerActionResult.objects.create(
        **result_values(
            23,
            guidance_item=item,
            attempt_no=2,
        )
    )
    assert second.attempt_no == 2


def test_idempotency_key_is_globally_unique():
    first_item = create_guidance_item(30)
    second_item = create_guidance_item(31)
    CustomerActionResult.objects.create(
        **result_values(
            30,
            guidance_item=first_item,
            idempotency_key="global-idempotency-key",
        )
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        CustomerActionResult.objects.create(
            **result_values(
                31,
                guidance_item=second_item,
                idempotency_key="global-idempotency-key",
            )
        )


def test_optional_result_details_accept_valid_submission():
    performed_at = timezone.now()
    result = CustomerActionResult.objects.create(
        **result_values(
            40,
            result_text="The water flow returned to normal.",
            performed_at=performed_at,
            customer_comment="No additional leakage observed.",
        )
    )

    assert result.result_text is not None
    assert result.performed_at == performed_at
    assert result.customer_comment is not None


def test_guidance_item_and_submitter_deletions_are_protected():
    item = create_guidance_item(50)
    submitter = create_submitter(50)
    CustomerActionResult.objects.create(
        **result_values(
            50,
            guidance_item=item,
            submitted_by=submitter,
        )
    )

    with pytest.raises(ProtectedError):
        item.delete()
    with pytest.raises(ProtectedError):
        submitter.delete()

    assert (
        CustomerActionResult._meta.get_field(
            "guidance_item"
        ).remote_field.on_delete
        is PROTECT
    )
    assert (
        CustomerActionResult._meta.get_field(
            "submitted_by"
        ).remote_field.on_delete
        is PROTECT
    )


def test_append_only_policy_has_no_unapproved_database_trigger():
    CustomerActionResult.objects.create(**result_values(60))

    with connection.cursor() as cursor:
        if connection.vendor == "sqlite":
            cursor.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'trigger'
                  AND tbl_name = 'support_customer_action_result'
                """
            )
            trigger_names = {row[0] for row in cursor.fetchall()}
        elif connection.vendor == "postgresql":
            cursor.execute(
                """
                SELECT tgname
                FROM pg_trigger
                WHERE tgrelid =
                    'support_customer_action_result'::regclass
                  AND NOT tgisinternal
                """
            )
            trigger_names = {row[0] for row in cursor.fetchall()}
        else:
            pytest.fail(
                f"Unsupported database vendor: {connection.vendor}"
            )

    assert trigger_names == set()


def test_database_catalog_contains_action_result_contract_objects():
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(
            cursor,
            "support_customer_action_result",
        )

    assert {
        "ux_action_result_attempt",
        "ux_action_result_idempotency",
        "ck_action_result_attempt",
        "ck_action_result_code_nonempty",
        "ck_action_result_idem_nonempty",
        "ix_action_result_guidance_item",
    }.issubset(constraints)
    assert constraints["ux_action_result_attempt"]["unique"] is True
    assert (
        constraints["ux_action_result_idempotency"]["unique"]
        is True
    )
    assert constraints["ck_action_result_attempt"]["check"] is True
    assert constraints["ix_action_result_guidance_item"]["index"] is True


@pytest.mark.django_db(transaction=True)
def test_action_result_empty_migration_rolls_back_and_reapplies():
    target_0009 = [("inquiries", "0009_guidanceitem")]
    target_0010 = [("inquiries", "0010_customeractionresult")]

    executor = MigrationExecutor(connection)
    executor.migrate(target_0009)
    with connection.cursor() as cursor:
        assert (
            "support_customer_action_result"
            not in connection.introspection.table_names(cursor)
        )

    executor = MigrationExecutor(connection)
    executor.migrate(target_0010)
    action_result_0010 = executor.loader.project_state(
        target_0010
    ).apps.get_model("inquiries", "CustomerActionResult")
    assert action_result_0010._meta.db_table == (
        "support_customer_action_result"
    )
    with connection.cursor() as cursor:
        assert (
            "support_customer_action_result"
            in connection.introspection.table_names(cursor)
        )

    executor = MigrationExecutor(connection)
    executor.migrate(target_0009)
    with connection.cursor() as cursor:
        assert (
            "support_customer_action_result"
            not in connection.introspection.table_names(cursor)
        )

    executor = MigrationExecutor(connection)
    executor.migrate(target_0010)
