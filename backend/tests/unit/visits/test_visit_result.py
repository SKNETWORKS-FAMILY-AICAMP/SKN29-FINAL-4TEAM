"""VisitResult schema, integrity, and Care bridge coverage."""

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError

from apps.accounts.models import CustomerProfile, User
from apps.care.models import CareRecord
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.visits.models import Visit, VisitResult


pytestmark = pytest.mark.django_db


def create_inquiry(sequence: int) -> Inquiry:
    customer_user = User.objects.create_user(
        username=f"VISIT-RESULT-CUSTOMER-{sequence:03d}",
        password=None,
        full_name=f"Visit result customer {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    customer = CustomerProfile.objects.create(
        user=customer_user,
        customer_no=f"VISIT-RESULT-CUS-{sequence:03d}",
        customer_name=f"Visit result customer {sequence}",
    )
    product = ProductModel.objects.create(
        model_code=f"VISIT-RESULT-PMD-{sequence:03d}",
        model_name=f"Visit result product {sequence}",
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"VISIT-RESULT-SUB-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"VISIT-RESULT-SERIAL-{sequence:03d}",
        started_on=date(2026, 7, 1),
    )
    return Inquiry.objects.create(
        subscription=subscription,
        initiated_by=customer_user,
        channel_code=Inquiry.Channel.WEB,
        raw_text="A field result is required.",
    )


def create_technician(sequence: int) -> User:
    return User.objects.create_user(
        username=f"VISIT-RESULT-TECH-{sequence:03d}",
        password=None,
        full_name=f"Visit result technician {sequence}",
        role_code=User.Role.TECHNICIAN,
        employee_no=f"VISIT-RESULT-EMP-{sequence:03d}",
    )


def create_completed_visit(
    sequence: int,
    *,
    technician: User | None = None,
) -> Visit:
    assigned = technician or create_technician(sequence)
    return Visit.objects.create(
        visit_code=f"VISIT-RESULT-VIS-{sequence:03d}",
        inquiry=create_inquiry(sequence),
        technician=assigned,
        status=Visit.Status.COMPLETED,
        requested_at=datetime(
            2026,
            7,
            1,
            8,
            tzinfo=timezone.utc,
        ),
        scheduled_at=datetime(
            2026,
            7,
            1,
            9,
            tzinfo=timezone.utc,
        ),
        started_at=datetime(
            2026,
            7,
            1,
            10,
            tzinfo=timezone.utc,
        ),
        completed_at=datetime(
            2026,
            7,
            1,
            11,
            tzinfo=timezone.utc,
        ),
        confirmed_cause="Synthetic confirmed cause",
        action_taken="Synthetic action",
        state_version=4,
        idempotency_key=f"visit-result-visit-{sequence:03d}",
        correlation_id=uuid4(),
        data_classification=Visit.DataClassification.SYNTHETIC,
    )


def result_values(visit: Visit, sequence: int) -> dict:
    return {
        "visit": visit,
        "cause_category_code": "PRODUCT",
        "inspection_summary": "Synthetic inspection summary",
        "action_summary": "Synthetic action summary",
        "parts_used_text": "Synthetic filter",
        "customer_guidance": "Synthetic after-care guidance",
        "resolved_on_site": True,
        "revisit_required": False,
        "revisit_reason": None,
        "technician_note": "Synthetic technician note",
        "submitted_by": visit.technician,
        "idempotency_key": f"visit-result-submit-{sequence:03d}",
        "completed_at": visit.completed_at,
        "next_care_on": date(2026, 10, 1),
    }


def test_visit_result_preserves_contract_fields_and_identifiers():
    visit = create_completed_visit(1)
    result = VisitResult.objects.create(**result_values(visit, 1))

    assert isinstance(result.pk, int)
    assert isinstance(result.public_id, UUID)
    assert result._meta.db_table == "field_service_visit_result"
    assert result.visit == visit
    assert visit.result == result
    assert result.submitted_by == visit.technician
    cause_category = VisitResult._meta.get_field(
        "cause_category_code"
    )
    assert cause_category.choices is None
    assert cause_category.null is True

    constraint_names = {
        constraint.name for constraint in VisitResult._meta.constraints
    }
    assert constraint_names == {
        "ux_visit_result_idempotency",
        "ck_visit_result_revisit_reason",
    }
    assert {
        constraint.name for constraint in Visit._meta.constraints
    } >= {"ux_visit_id_technician"}


def test_visit_and_idempotency_are_unique():
    first_visit = create_completed_visit(2)
    values = result_values(first_visit, 2)
    VisitResult.objects.create(**values)

    duplicate_visit = result_values(first_visit, 3)
    with pytest.raises(IntegrityError), transaction.atomic():
        VisitResult.objects.create(**duplicate_visit)

    second_visit = create_completed_visit(3)
    duplicate_key = result_values(second_visit, 4)
    duplicate_key["idempotency_key"] = values["idempotency_key"]
    with pytest.raises(IntegrityError), transaction.atomic():
        VisitResult.objects.create(**duplicate_key)


def test_cause_category_stays_open_pending_contract_and_reason_is_enforced():
    pending_category = result_values(create_completed_visit(4), 4)
    pending_category["cause_category_code"] = "TEAM_REVIEW_PENDING"
    saved = VisitResult.objects.create(**pending_category)
    assert saved.cause_category_code == "TEAM_REVIEW_PENDING"

    missing_reason = result_values(create_completed_visit(5), 5)
    missing_reason.update(
        resolved_on_site=False,
        revisit_required=True,
        revisit_reason=None,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        VisitResult.objects.create(**missing_reason)


def test_clean_rejects_a_submitter_outside_the_visit_assignment():
    visit = create_completed_visit(6)
    other_technician = create_technician(66)
    values = result_values(visit, 6)
    values["submitted_by"] = other_technician
    result = VisitResult(**values)

    with pytest.raises(ValidationError) as error:
        result.full_clean()

    assert "submitted_by" in error.value.message_dict


def test_visit_and_submitter_deletion_are_protected():
    visit = create_completed_visit(7)
    result = VisitResult.objects.create(**result_values(visit, 7))

    with pytest.raises(ProtectedError):
        result.visit.delete()

    with pytest.raises(ProtectedError):
        result.submitted_by.delete()


def test_existing_care_uuid_bridge_accepts_result_public_id():
    visit = create_completed_visit(8)
    result = VisitResult.objects.create(**result_values(visit, 8))
    care = CareRecord.objects.create(
        care_code="VISIT-RESULT-CARE-008",
        subscription=visit.inquiry.subscription,
        inquiry=visit.inquiry,
        visit=visit,
        visit_result_public_id=result.public_id,
        care_type_code=CareRecord.CareType.VISIT_SERVICE,
        status_code=CareRecord.Status.SCHEDULED,
        scheduled_on=result.next_care_on,
        source_code=CareRecord.Source.TECHNICIAN,
    )

    assert care.visit_result_public_id == result.public_id
    assert care.visit == result.visit
    bridge = CareRecord._meta.get_field("visit_result_public_id")
    assert bridge.is_relation is False


def test_postgresql_composite_fk_exists_with_bigint_columns():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL structural assertion")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conname = %s
              AND conrelid = 'field_service_visit_result'::regclass
            """,
            ["fk_visit_result_assigned_technician"],
        )
        definition = cursor.fetchone()
        cursor.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'field_service_visit_result'
              AND column_name IN (
                  'id',
                  'public_id',
                  'visit_id',
                  'submitted_by_id'
              )
            """
        )
        column_types = dict(cursor.fetchall())

    assert definition is not None
    assert "FOREIGN KEY (visit_id, submitted_by_id)" in definition[0]
    assert (
        "REFERENCES field_service_visit(id, technician_id)"
        in definition[0]
    )
    assert column_types == {
        "id": "bigint",
        "public_id": "uuid",
        "visit_id": "bigint",
        "submitted_by_id": "bigint",
    }


def test_postgresql_composite_fk_rejects_unassigned_technician():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL composite FK assertion")

    visit = create_completed_visit(9)
    other_technician = create_technician(99)
    values = result_values(visit, 9)
    values["submitted_by"] = other_technician

    with pytest.raises(IntegrityError), transaction.atomic():
        VisitResult.objects.create(**values)
