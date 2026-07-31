"""Audit event persistence and database constraint tests."""

from datetime import date
from uuid import UUID, uuid4

import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AuditEvent
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.visits.models import Visit
from apps.workflow.models import TransitionHistory


pytestmark = pytest.mark.django_db


def create_inquiry(sequence: int) -> Inquiry:
    """Create the minimum protected aggregate graph for one audit event."""

    user = User.objects.create_user(
        username=f"AUDIT-CUSTOMER-{sequence:03d}",
        password=None,
        full_name=f"Audit customer {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    customer = CustomerProfile.objects.create(
        user=user,
        customer_no=f"AUDIT-CUS-{sequence:03d}",
        customer_name=f"Audit customer {sequence}",
    )
    product = ProductModel.objects.create(
        model_code=f"AUDIT-PMD-{sequence:03d}",
        model_name=f"Audit product {sequence}",
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"AUDIT-SUB-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"AUDIT-SERIAL-{sequence:03d}",
        started_on=date(2026, 7, 1),
    )
    return Inquiry.objects.create(
        subscription=subscription,
        initiated_by=user,
        channel_code=Inquiry.Channel.WEB,
        raw_text="Synthetic audit test inquiry.",
    )


def create_transition(sequence: int) -> TransitionHistory:
    inquiry = create_inquiry(sequence)
    return TransitionHistory.objects.create(
        inquiry=inquiry,
        actor=inquiry.initiated_by,
        event_code="START_INQUIRY",
        from_state=None,
        to_state=Inquiry.Status.DRAFT,
        state_version=1,
        correlation_id=uuid4(),
        idempotency_key=f"audit-transition-{sequence:03d}",
    )


def create_system_transition(sequence: int) -> TransitionHistory:
    inquiry = create_inquiry(sequence)
    return TransitionHistory.objects.create(
        inquiry=inquiry,
        actor=None,
        changed_by_type_code=(
            TransitionHistory.ChangedByType.SYSTEM
        ),
        event_code="SAFE_GUIDANCE_READY",
        from_state=None,
        to_state=Inquiry.Status.DRAFT,
        state_version=1,
        correlation_id=uuid4(),
        idempotency_key=f"audit-system-transition-{sequence:03d}",
    )


def create_visit_transition(
    sequence: int,
) -> tuple[Visit, TransitionHistory]:
    inquiry = create_inquiry(sequence)
    visit = Visit.objects.create(
        visit_code=f"SYN-VIS-{sequence:03d}",
        inquiry=inquiry,
        technician=None,
        status=Visit.Status.ASSIGNING,
        requested_at=timezone.now(),
        state_version=1,
        idempotency_key=f"audit-visit-{sequence:03d}",
        correlation_id=uuid4(),
        data_classification=(
            Visit.DataClassification.SYNTHETIC
        ),
    )
    transition = TransitionHistory.objects.create(
        target_type_code=TransitionHistory.TargetType.VISIT,
        visit=visit,
        actor=None,
        changed_by_type_code=(
            TransitionHistory.ChangedByType.SYSTEM
        ),
        event_code="VISIT_NEEDED",
        from_state=None,
        to_state=Visit.Status.ASSIGNING,
        state_version=1,
        correlation_id=visit.correlation_id,
        idempotency_key=visit.idempotency_key,
    )
    return visit, transition


def audit_values(sequence: int, **overrides):
    transition = overrides.pop("transition", None)
    if transition is None:
        transition = create_transition(sequence)
    values = {
        "audit_code": f"SYN-AUDIT-INQUIRY-{sequence:03d}-001",
        "transition": transition,
        "entity_type": AuditEvent.EntityType.INQUIRY,
        "inquiry": transition.inquiry,
        "event_code": transition.event_code,
        "actor_role": AuditEvent.ActorRole.CUSTOMER,
        "actor": transition.actor,
        "state_version": transition.state_version,
        "idempotency_key": transition.idempotency_key,
        "correlation_id": transition.correlation_id,
        "occurred_at": timezone.now(),
        "data_classification": (
            AuditEvent.DataClassification.SYNTHETIC
        ),
    }
    values.update(overrides)
    return values


def test_audit_event_uses_contract_identifiers_and_transition_link():
    event = AuditEvent.objects.create(**audit_values(1))

    assert isinstance(event.pk, int)
    assert isinstance(event.public_id, UUID)
    assert event.transition.audit_event == event
    assert event.inquiry.audit_events.get() == event
    assert event.entity_type == AuditEvent.EntityType.INQUIRY
    assert event.data_classification == "synthetic"
    assert event._meta.db_table == "audit_event"


@pytest.mark.parametrize(
    ("sequence", "overrides"),
    [
        (10, {"entity_type": "VISIT"}),
        (11, {"inquiry": None}),
        (12, {"actor_role": "SYSTEM"}),
        (13, {"actor": None}),
        (14, {"state_version": 0}),
        (15, {"data_classification": "official"}),
        (16, {"entity_type": "OTHER"}),
        (17, {"actor_role": "OPERATOR"}),
    ],
)
def test_audit_database_checks_reject_contract_mismatches(
    sequence,
    overrides,
):
    with pytest.raises(IntegrityError), transaction.atomic():
        AuditEvent.objects.create(
            **audit_values(sequence, **overrides)
        )


def test_system_event_requires_a_null_actor():
    transition = create_system_transition(30)
    event = AuditEvent.objects.create(
        **audit_values(
            30,
            transition=transition,
            actor_role=AuditEvent.ActorRole.SYSTEM,
            actor=None,
        )
    )

    assert event.actor is None
    assert event.actor_role == AuditEvent.ActorRole.SYSTEM


def test_visit_event_requires_only_the_visit_target():
    visit, transition = create_visit_transition(35)
    event = AuditEvent.objects.create(
        **audit_values(
            35,
            transition=transition,
            audit_code="SYN-AUDIT-VISIT-035-001",
            entity_type=AuditEvent.EntityType.VISIT,
            inquiry=None,
            visit=visit,
            actor_role=AuditEvent.ActorRole.SYSTEM,
            actor=None,
        )
    )

    assert event.inquiry is None
    assert event.visit == visit
    assert visit.audit_events.get() == event


def test_audit_code_and_transition_are_unique_and_transition_is_protected():
    transition = create_transition(40)
    event = AuditEvent.objects.create(
        **audit_values(40, transition=transition)
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        AuditEvent.objects.create(
            **audit_values(
                41,
                audit_code=event.audit_code,
            )
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        AuditEvent.objects.create(
            **audit_values(
                42,
                transition=transition,
                inquiry=transition.inquiry,
            )
        )

    with pytest.raises(ProtectedError):
        transition.delete()
