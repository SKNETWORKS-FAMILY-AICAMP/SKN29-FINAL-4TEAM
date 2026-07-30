"""CareRecord 필드·제약·삭제 보호·Wave 4 bridge 검증."""

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest
from django.db import IntegrityError, models, transaction
from django.db.models.deletion import ProtectedError

from apps.accounts.models import CustomerProfile, User
from apps.care.models import CareRecord
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db


def create_subscription(sequence: int = 1) -> CustomerSubscription:
    customer_user = User.objects.create_user(
        id=f"DEMO-USR-{sequence + 400:03d}",
        username=f"TEST-CARE-CUSTOMER-{sequence:03d}",
        password=None,
        full_name=f"케어 테스트 고객 {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    customer = CustomerProfile.objects.create(
        id=f"DEMO-CUS-{sequence + 400:03d}",
        user=customer_user,
        customer_no=f"TEST-CARE-CUSTOMER-NO-{sequence:03d}",
        customer_name=f"케어 테스트 고객 {sequence}",
    )
    product = ProductModel.objects.create(
        model_code=f"TEST-CARE-PMD-{sequence:03d}",
        model_name=f"케어 테스트 제품 {sequence}",
    )
    return CustomerSubscription.objects.create(
        contract_no=f"TEST-CARE-SUB-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"TEST-CARE-SERIAL-{sequence:03d}",
        started_on=date(2026, 1, 1),
    )


def create_technician(sequence: int = 1) -> User:
    return User.objects.create_user(
        id=f"DEMO-USR-{sequence + 500:03d}",
        username=f"TEST-CARE-TECHNICIAN-{sequence:03d}",
        password=None,
        full_name=f"케어 테스트 기사 {sequence}",
        role_code=User.Role.TECHNICIAN,
        employee_no=f"TEST-CARE-EMP-{sequence:03d}",
    )


def create_care_record(sequence: int = 1, **overrides) -> CareRecord:
    subscription = overrides.pop("subscription", None)
    values = {
        "care_code": f"TEST-CAR-{sequence:03d}",
        "subscription": subscription or create_subscription(sequence),
        "care_type_code": CareRecord.CareType.FILTER_REPLACEMENT,
        "scheduled_on": date(2026, 2, min(sequence, 28)),
    }
    values.update(overrides)
    return CareRecord.objects.create(**values)


def test_care_record_uses_three_layer_identifier_and_defaults():
    record = create_care_record()

    assert isinstance(record.pk, int)
    assert isinstance(record.public_id, UUID)
    assert record.care_code == "TEST-CAR-001"
    assert record.status_code == CareRecord.Status.SCHEDULED
    assert record.source_code == CareRecord.Source.SYSTEM


def test_care_codes_are_database_constrained():
    with pytest.raises(IntegrityError), transaction.atomic():
        create_care_record(care_type_code="UNSUPPORTED")

    with pytest.raises(IntegrityError), transaction.atomic():
        create_care_record(sequence=2, status_code="UNKNOWN")

    with pytest.raises(IntegrityError), transaction.atomic():
        create_care_record(sequence=3, source_code="EXTERNAL")


def test_completed_state_requires_timestamp_and_performer():
    technician = create_technician()

    with pytest.raises(IntegrityError), transaction.atomic():
        create_care_record(
            status_code=CareRecord.Status.COMPLETED,
            completed_at=datetime(
                2026,
                2,
                1,
                tzinfo=timezone.utc,
            ),
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_care_record(
            sequence=2,
            status_code=CareRecord.Status.COMPLETED,
            performed_by=technician,
        )

    completed = create_care_record(
        sequence=3,
        status_code=CareRecord.Status.COMPLETED,
        completed_at=datetime(
            2026,
            2,
            3,
            tzinfo=timezone.utc,
        ),
        performed_by=technician,
    )
    assert completed.status_code == CareRecord.Status.COMPLETED


def test_imported_completed_care_preserves_date_without_inventing_actor():
    imported = create_care_record(
        status_code=CareRecord.Status.COMPLETED,
        care_type_code=CareRecord.CareType.VISIT_SERVICE,
        source_code=CareRecord.Source.IMPORT,
        performed_on=date(2026, 7, 4),
        result_code=CareRecord.Result.ISSUE_RESOLVED,
        completed_at=None,
        performed_by=None,
    )

    assert imported.performed_on == date(2026, 7, 4)
    assert imported.completed_at is None
    assert imported.performed_by is None


def test_completed_state_rejects_cancellation_fields():
    technician = create_technician()

    with pytest.raises(IntegrityError), transaction.atomic():
        create_care_record(
            status_code=CareRecord.Status.COMPLETED,
            completed_at=datetime(
                2026,
                2,
                1,
                tzinfo=timezone.utc,
            ),
            performed_by=technician,
            cancelled_at=datetime(
                2026,
                2,
                1,
                tzinfo=timezone.utc,
            ),
            cancellation_reason="중복 결과",
        )


def test_cancelled_state_requires_timestamp_and_reason():
    with pytest.raises(IntegrityError), transaction.atomic():
        create_care_record(
            status_code=CareRecord.Status.CANCELLED,
            cancellation_reason="고객 요청",
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_care_record(
            sequence=2,
            status_code=CareRecord.Status.CANCELLED,
            cancelled_at=datetime(
                2026,
                2,
                2,
                tzinfo=timezone.utc,
            ),
        )

    cancelled = create_care_record(
        sequence=3,
        status_code=CareRecord.Status.CANCELLED,
        cancelled_at=datetime(
            2026,
            2,
            3,
            tzinfo=timezone.utc,
        ),
        cancellation_reason="고객 요청",
    )
    assert cancelled.status_code == CareRecord.Status.CANCELLED


@pytest.mark.parametrize(
    "status_code",
    [
        CareRecord.Status.DUE,
        CareRecord.Status.SCHEDULED,
        CareRecord.Status.OVERDUE,
    ],
)
def test_pending_states_reject_outcome_fields(status_code):
    with pytest.raises(IntegrityError), transaction.atomic():
        create_care_record(
            status_code=status_code,
            completed_at=datetime(
                2026,
                2,
                1,
                tzinfo=timezone.utc,
            ),
        )


def test_subscription_and_performer_deletion_are_protected():
    subscription = create_subscription()
    technician = create_technician()
    record = create_care_record(
        subscription=subscription,
        status_code=CareRecord.Status.COMPLETED,
        completed_at=datetime(
            2026,
            2,
            1,
            tzinfo=timezone.utc,
        ),
        performed_by=technician,
    )

    with pytest.raises(ProtectedError):
        record.subscription.delete()

    with pytest.raises(ProtectedError):
        record.performed_by.delete()


def test_wave4_visit_result_bridge_is_nullable_non_relation_uuid():
    field = CareRecord._meta.get_field("visit_result_public_id")

    assert isinstance(field, models.UUIDField)
    assert field.null is True
    assert field.blank is True
    assert field.is_relation is False
    assert field.remote_field is None

    bridge_id = uuid4()
    record = create_care_record(visit_result_public_id=bridge_id)
    assert record.visit_result_public_id == bridge_id


def test_care_indexes_are_declared():
    indexes = {
        index.name: tuple(index.fields)
        for index in CareRecord._meta.indexes
    }

    assert indexes == {
        "ix_care_record_subscription": (
            "subscription",
            "-completed_at",
        ),
        "ix_care_record_schedule": (
            "status_code",
            "scheduled_on",
        ),
        "ix_care_record_visit_result": (
            "visit_result_public_id",
        ),
    }
