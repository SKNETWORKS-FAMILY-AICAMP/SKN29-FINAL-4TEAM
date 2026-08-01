"""Consultation model identifier, role, and lifecycle constraints."""

from datetime import date, datetime
from uuid import UUID, uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from apps.accounts.models import CustomerProfile, User
from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db


def create_inquiry(sequence: int = 1) -> Inquiry:
    customer_user = User.objects.create_user(
        username=f"CONSULT-MODEL-CUSTOMER-{sequence:03d}",
        password=None,
        full_name=f"Consultation customer {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    customer = CustomerProfile.objects.create(
        user=customer_user,
        customer_no=f"CONSULT-MODEL-CUS-{sequence:03d}",
        customer_name=f"Consultation customer {sequence}",
    )
    product = ProductModel.objects.create(
        model_code=f"CONSULT-MODEL-PMD-{sequence:03d}",
        model_name=f"Consultation product {sequence}",
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"CONSULT-MODEL-SUB-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"CONSULT-MODEL-SERIAL-{sequence:03d}",
        started_on=date(2026, 7, 1),
    )
    return Inquiry.objects.create(
        subscription=subscription,
        initiated_by=customer_user,
        channel_code=Inquiry.Channel.WEB,
        raw_text="A consultation is required.",
    )


def create_consultant(sequence: int = 1) -> User:
    return User.objects.create_user(
        username=f"CONSULT-MODEL-STAFF-{sequence:03d}",
        password=None,
        full_name=f"Consultant {sequence}",
        role_code=User.Role.CONSULTANT,
        employee_no=f"CONS-EMP-{sequence:03d}",
    )


def consultation_values(sequence: int = 1) -> dict:
    return {
        "public_id": uuid4(),
        "consultation_code": f"CON-SYN-{sequence:04d}-1",
        "inquiry": create_inquiry(sequence),
        "sequence": 1,
        "consultant": None,
        "status": Consultation.Status.WAITING,
        "outcome": Consultation.Outcome.PENDING,
        "summary": "Synthetic consultation summary",
        "state_version": 1,
        "idempotency_key": f"idem-consultation-{sequence:04d}-1",
        "correlation_id": uuid4(),
        "created_at": datetime.fromisoformat(
            "2026-07-02T10:00:00+09:00"
        ),
        "started_at": None,
        "completed_at": None,
        "data_classification": (
            Consultation.DataClassification.SYNTHETIC
        ),
    }


def test_consultation_preserves_fixture_fields_and_identifiers():
    values = consultation_values()
    consultation = Consultation.objects.create(**values)

    assert isinstance(consultation.pk, int)
    assert isinstance(consultation.public_id, UUID)
    assert consultation.consultation_code == "CON-SYN-0001-1"
    assert consultation.created_at == values["created_at"]
    assert consultation.data_classification == "synthetic"
    assert consultation._meta.db_table == "support_consultation"
    assert "source_fixture_id" not in {
        field.name for field in Consultation._meta.fields
    }
    assert set(Consultation.Status.values) == {
        "WAITING",
        "ASSIGNED",
        "IN_PROGRESS",
        "COMPLETED",
        "CANCELLED",
    }
    assert set(Consultation.Outcome.values) == {
        "PENDING",
        "COMPLETED_NO_VISIT",
        "VISIT_REQUIRED",
        "REOPENED_FOLLOWUP",
    }


def test_consultation_rejects_duplicate_inquiry_sequence():
    values = consultation_values()
    Consultation.objects.create(**values)

    with pytest.raises(IntegrityError), transaction.atomic():
        Consultation.objects.create(
            **{
                **values,
                "public_id": uuid4(),
                "consultation_code": "CON-SYN-0001-2",
                "idempotency_key": "idem-consultation-0001-2",
            }
        )


def test_consultation_database_enforces_lifecycle_and_version():
    invalid_version = consultation_values(sequence=2)
    invalid_version["state_version"] = 0
    with pytest.raises(IntegrityError), transaction.atomic():
        Consultation.objects.create(**invalid_version)

    invalid_progress = consultation_values(sequence=3)
    invalid_progress.update(
        status=Consultation.Status.IN_PROGRESS,
        consultant=create_consultant(sequence=3),
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Consultation.objects.create(**invalid_progress)

    invalid_completion = consultation_values(sequence=4)
    invalid_completion.update(
        status=Consultation.Status.COMPLETED,
        consultant=create_consultant(sequence=4),
        outcome=Consultation.Outcome.VISIT_REQUIRED,
        started_at=datetime.fromisoformat(
            "2026-07-02T12:00:00+09:00"
        ),
        completed_at=datetime.fromisoformat(
            "2026-07-02T11:00:00+09:00"
        ),
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Consultation.objects.create(**invalid_completion)


def test_consultation_role_validation_and_protected_inquiry():
    values = consultation_values(sequence=5)
    customer = values["inquiry"].initiated_by
    values.update(
        status=Consultation.Status.ASSIGNED,
        consultant=customer,
    )
    consultation = Consultation(**values)

    with pytest.raises(ValidationError) as error:
        consultation.full_clean()

    assert "consultant" in error.value.message_dict

    valid_values = consultation_values(sequence=6)
    saved = Consultation.objects.create(**valid_values)
    with pytest.raises(ProtectedError):
        saved.inquiry.delete()


def test_completed_consultation_accepts_fixture_lifecycle():
    values = consultation_values(sequence=7)
    values.update(
        consultant=create_consultant(sequence=7),
        status=Consultation.Status.COMPLETED,
        outcome=Consultation.Outcome.VISIT_REQUIRED,
        started_at=datetime.fromisoformat(
            "2026-07-02T10:30:00+09:00"
        ),
        completed_at=datetime.fromisoformat(
            "2026-07-02T11:00:00+09:00"
        ),
    )

    consultation = Consultation.objects.create(**values)

    assert consultation.status == Consultation.Status.COMPLETED
    assert consultation.completed_at >= consultation.started_at
