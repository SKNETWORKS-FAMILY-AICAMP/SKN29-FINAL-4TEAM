"""Visit model identifier, role, and lifecycle constraints."""

from datetime import date, datetime
from uuid import UUID, uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.visits.models import Visit


pytestmark = pytest.mark.django_db


def create_inquiry(sequence: int = 1) -> Inquiry:
    customer_user = User.objects.create_user(
        username=f"VISIT-MODEL-CUSTOMER-{sequence:03d}",
        password=None,
        full_name=f"Visit customer {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    customer = CustomerProfile.objects.create(
        user=customer_user,
        customer_no=f"VISIT-MODEL-CUS-{sequence:03d}",
        customer_name=f"Visit customer {sequence}",
    )
    product = ProductModel.objects.create(
        model_code=f"VISIT-MODEL-PMD-{sequence:03d}",
        model_name=f"Visit product {sequence}",
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"VISIT-MODEL-SUB-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"VISIT-MODEL-SERIAL-{sequence:03d}",
        started_on=date(2026, 7, 1),
    )
    return Inquiry.objects.create(
        subscription=subscription,
        initiated_by=customer_user,
        channel_code=Inquiry.Channel.WEB,
        raw_text="A field visit is required.",
    )


def create_technician(sequence: int = 1) -> User:
    return User.objects.create_user(
        username=f"VISIT-MODEL-STAFF-{sequence:03d}",
        password=None,
        full_name=f"Technician {sequence}",
        role_code=User.Role.TECHNICIAN,
        employee_no=f"TECH-EMP-{sequence:03d}",
    )


def visit_values(sequence: int = 1) -> dict:
    return {
        "public_id": uuid4(),
        "visit_code": f"VIS-SYN-{sequence:04d}",
        "inquiry": create_inquiry(sequence),
        "technician": None,
        "status": Visit.Status.ASSIGNING,
        "requested_at": datetime.fromisoformat(
            "2026-07-04T23:00:00+09:00"
        ),
        "scheduled_at": None,
        "started_at": None,
        "completed_at": None,
        "confirmed_cause": None,
        "action_taken": None,
        "state_version": 1,
        "idempotency_key": f"idem-visit-{sequence:04d}",
        "correlation_id": uuid4(),
        "data_classification": Visit.DataClassification.SYNTHETIC,
    }


def test_visit_preserves_fixture_fields_and_identifiers():
    values = visit_values()
    visit = Visit.objects.create(**values)

    assert isinstance(visit.pk, int)
    assert isinstance(visit.public_id, UUID)
    assert visit.visit_code == "VIS-SYN-0001"
    assert visit.data_classification == "synthetic"
    assert visit._meta.db_table == "field_service_visit"
    assert "source_fixture_id" not in {
        field.name for field in Visit._meta.fields
    }
    assert set(Visit.Status.values) == {
        "ASSIGNING",
        "SCHEDULING",
        "CONFIRMED",
        "IN_PROGRESS",
        "COMPLETED",
        "FOLLOW_UP_REQUIRED",
        "CANCELLED",
    }


def test_visit_database_enforces_status_version_and_completion():
    invalid_version = visit_values(sequence=2)
    invalid_version["state_version"] = 0
    with pytest.raises(IntegrityError), transaction.atomic():
        Visit.objects.create(**invalid_version)

    invalid_status = visit_values(sequence=3)
    invalid_status["status"] = "UNKNOWN"
    with pytest.raises(IntegrityError), transaction.atomic():
        Visit.objects.create(**invalid_status)

    invalid_completion = visit_values(sequence=4)
    invalid_completion.update(
        technician=create_technician(sequence=4),
        status=Visit.Status.COMPLETED,
        started_at=datetime.fromisoformat(
            "2026-07-06T00:30:00+09:00"
        ),
        completed_at=datetime.fromisoformat(
            "2026-07-06T00:00:00+09:00"
        ),
        confirmed_cause="Synthetic confirmed cause",
        action_taken="Synthetic action taken",
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Visit.objects.create(**invalid_completion)


def test_visit_role_validation_and_protected_inquiry():
    values = visit_values(sequence=5)
    customer = values["inquiry"].initiated_by
    values.update(
        technician=customer,
        status=Visit.Status.SCHEDULING,
    )
    visit = Visit(**values)

    with pytest.raises(ValidationError) as error:
        visit.full_clean()

    assert "technician" in error.value.message_dict

    valid_values = visit_values(sequence=6)
    saved = Visit.objects.create(**valid_values)
    with pytest.raises(ProtectedError):
        saved.inquiry.delete()


def test_visit_allows_fixture_schedule_later_than_started_at():
    values = visit_values(sequence=7)
    values.update(
        technician=create_technician(sequence=7),
        status=Visit.Status.IN_PROGRESS,
        scheduled_at=datetime.fromisoformat(
            "2026-07-06T23:30:00+09:00"
        ),
        started_at=datetime.fromisoformat(
            "2026-07-05T00:00:00+09:00"
        ),
        state_version=4,
    )

    visit = Visit.objects.create(**values)

    assert visit.scheduled_at > visit.started_at
    assert visit.status == Visit.Status.IN_PROGRESS


def test_completed_visit_requires_and_preserves_result_fields():
    values = visit_values(sequence=8)
    values.update(
        technician=create_technician(sequence=8),
        status=Visit.Status.COMPLETED,
        scheduled_at=datetime.fromisoformat(
            "2026-07-07T23:30:00+09:00"
        ),
        started_at=datetime.fromisoformat(
            "2026-07-06T00:00:00+09:00"
        ),
        completed_at=datetime.fromisoformat(
            "2026-07-06T00:30:00+09:00"
        ),
        confirmed_cause="Synthetic confirmed cause",
        action_taken="Synthetic action taken",
        state_version=5,
    )

    visit = Visit.objects.create(**values)

    assert visit.confirmed_cause == "Synthetic confirmed cause"
    assert visit.action_taken == "Synthetic action taken"
