"""VisitResult schema, integrity, and Care bridge coverage."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from threading import Event
from uuid import UUID, uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, connections, transaction
from django.db.utils import OperationalError
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


def create_result_in_open_transaction(
    *,
    visit_pk: int,
    submitter_pk: int,
    inserted: Event,
    release: Event,
) -> int:
    """Create a result and hold its parent KEY SHARE lock until released."""

    connections.close_all()
    try:
        with transaction.atomic():
            result = VisitResult.objects.create(
                visit_id=visit_pk,
                inspection_summary="Concurrent inspection summary",
                action_summary="Concurrent action summary",
                resolved_on_site=True,
                revisit_required=False,
                submitted_by_id=submitter_pk,
                idempotency_key=f"visit-result-concurrent-{uuid4()}",
            )
            inserted.set()
            if not release.wait(timeout=10):
                raise TimeoutError("Result transaction release timed out")
        return result.pk
    finally:
        connections.close_all()


def reassign_with_short_lock_timeout(
    *,
    visit_pk: int,
    technician_pk: int,
) -> str:
    """Attempt reassignment without waiting indefinitely for the guard lock."""

    connections.close_all()
    try:
        try:
            with transaction.atomic():
                with connections["default"].cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '750ms'")
                Visit.objects.filter(pk=visit_pk).update(
                    technician_id=technician_pk
                )
        except OperationalError as exc:
            if getattr(exc.__cause__, "sqlstate", None) == "55P03":
                return "LOCK_TIMEOUT"
            raise
        return "UPDATED"
    finally:
        connections.close_all()


def insert_result_for_submitter(
    *,
    visit_pk: int,
    submitter_pk: int,
) -> str:
    """Insert on a separate connection and report the guard decision."""

    connections.close_all()
    try:
        try:
            with transaction.atomic():
                VisitResult.objects.create(
                    visit_id=visit_pk,
                    inspection_summary="Post-reassignment inspection",
                    action_summary="Post-reassignment action",
                    resolved_on_site=True,
                    revisit_required=False,
                    submitted_by_id=submitter_pk,
                    idempotency_key=f"visit-result-after-reassign-{uuid4()}",
                )
        except IntegrityError:
            return "REJECTED"
        return "CREATED"
    finally:
        connections.close_all()


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


def test_postgresql_submitter_guard_exists_with_bigint_columns():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL structural assertion")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM pg_constraint
            WHERE conname = %s
              AND conrelid = 'field_service_visit_result'::regclass
            """,
            ["fk_visit_result_assigned_technician"],
        )
        legacy_constraint = cursor.fetchone()
        cursor.execute(
            """
            SELECT trigger.tgenabled
            FROM pg_trigger trigger
            WHERE trigger.tgname = %s
              AND trigger.tgrelid = 'field_service_visit_result'::regclass
              AND NOT trigger.tgisinternal
            """,
            ["trg_visit_result_submitter_assignment"],
        )
        trigger = cursor.fetchone()
        cursor.execute(
            """
            SELECT 1
            FROM pg_proc procedure
            JOIN pg_namespace namespace
              ON namespace.oid = procedure.pronamespace
            WHERE procedure.proname = %s
              AND namespace.nspname = current_schema()
            """,
            ["check_visit_result_submitter_assignment"],
        )
        function = cursor.fetchone()
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

    assert legacy_constraint is None
    assert trigger == ("O",)
    assert function == (1,)
    assert column_types == {
        "id": "bigint",
        "public_id": "uuid",
        "visit_id": "bigint",
        "submitted_by_id": "bigint",
    }


def test_postgresql_submitter_guard_rejects_unassigned_technician():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL submitter guard assertion")

    visit = create_completed_visit(9)
    other_technician = create_technician(99)
    values = result_values(visit, 9)
    values["submitted_by"] = other_technician

    with pytest.raises(IntegrityError), transaction.atomic():
        VisitResult.objects.create(**values)


def test_postgresql_submitter_guard_preserves_historical_assignment():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL submitter guard assertion")

    visit = create_completed_visit(10)
    original_technician = visit.technician
    result = VisitResult.objects.create(**result_values(visit, 10))
    replacement_technician = create_technician(100)

    visit.technician = replacement_technician
    visit.save(update_fields=["technician", "updated_at"])
    result.refresh_from_db()

    assert visit.technician == replacement_technician
    assert result.submitted_by == original_technician
    result.full_clean()

    result.submitted_by = replacement_technician
    with pytest.raises(ValidationError) as error:
        result.full_clean()
    assert "submitted_by" in error.value.message_dict

    with pytest.raises(IntegrityError), transaction.atomic():
        result.save(update_fields=["submitted_by", "updated_at"])


def test_existing_result_validation_uses_historical_submission_context():
    visit = create_completed_visit(11)
    original_technician = visit.technician
    result = VisitResult.objects.create(**result_values(visit, 11))
    replacement_technician = create_technician(110)

    visit.technician = replacement_technician
    visit.save(update_fields=["technician", "updated_at"])

    result.refresh_from_db()
    result.full_clean()
    assert result.submitted_by == original_technician

    result.visit = create_completed_visit(12)
    with pytest.raises(ValidationError) as error:
        result.full_clean()
    assert "visit" in error.value.message_dict


@pytest.mark.django_db(transaction=True)
def test_postgresql_submitter_guard_serializes_insert_and_reassignment():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL submitter guard concurrency assertion")

    visit = create_completed_visit(13)
    original_technician = visit.technician
    replacement_technician = create_technician(130)
    inserted = Event()
    release = Event()

    with ThreadPoolExecutor(max_workers=2) as executor:
        insert_future = executor.submit(
            create_result_in_open_transaction,
            visit_pk=visit.pk,
            submitter_pk=original_technician.pk,
            inserted=inserted,
            release=release,
        )
        assert inserted.wait(timeout=10)
        try:
            update_future = executor.submit(
                reassign_with_short_lock_timeout,
                visit_pk=visit.pk,
                technician_pk=replacement_technician.pk,
            )
            assert update_future.result(timeout=10) == "LOCK_TIMEOUT"
        finally:
            release.set()
        result_pk = insert_future.result(timeout=10)

    Visit.objects.filter(pk=visit.pk).update(
        technician_id=replacement_technician.pk
    )
    result = VisitResult.objects.get(pk=result_pk)
    visit.refresh_from_db()

    assert visit.technician == replacement_technician
    assert result.submitted_by == original_technician


@pytest.mark.django_db(transaction=True)
def test_postgresql_submitter_guard_rejects_old_submitter_after_reassignment():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL submitter guard concurrency assertion")

    visit = create_completed_visit(14)
    original_technician = visit.technician
    replacement_technician = create_technician(140)

    with ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(
            reassign_with_short_lock_timeout,
            visit_pk=visit.pk,
            technician_pk=replacement_technician.pk,
        ).result(timeout=10) == "UPDATED"
        result = executor.submit(
            insert_result_for_submitter,
            visit_pk=visit.pk,
            submitter_pk=original_technician.pk,
        ).result(timeout=10)

    assert result == "REJECTED"
    assert not VisitResult.objects.filter(visit=visit).exists()
