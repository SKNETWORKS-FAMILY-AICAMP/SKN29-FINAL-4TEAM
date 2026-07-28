"""CareRecord Demo seed 멱등성과 상태별 기준 데이터 검증."""

from django.core.management import call_command

import pytest

from apps.care.management.commands.seed_demo_care_records import (
    DEMO_CARE_CODES,
    DEMO_TECHNICIAN_USERNAME,
)
from apps.care.models import CareRecord


pytestmark = pytest.mark.django_db


def seed_wave2_prerequisites():
    call_command("seed_demo_accounts")
    call_command("seed_demo_products")
    call_command("seed_demo_subscriptions")


def test_demo_care_seed_preserves_ids_and_creates_three_states():
    seed_wave2_prerequisites()
    call_command("seed_demo_care_records")
    first_identities = {
        record.care_code: (record.pk, record.public_id)
        for record in CareRecord.objects.order_by("care_code")
    }

    seed_wave2_prerequisites()
    call_command("seed_demo_care_records")
    second_identities = {
        record.care_code: (record.pk, record.public_id)
        for record in CareRecord.objects.order_by("care_code")
    }

    assert CareRecord.objects.count() == 3
    assert set(second_identities) == set(DEMO_CARE_CODES)
    assert second_identities == first_identities

    scheduled = CareRecord.objects.get(care_code=DEMO_CARE_CODES[0])
    completed = CareRecord.objects.get(care_code=DEMO_CARE_CODES[1])
    cancelled = CareRecord.objects.get(care_code=DEMO_CARE_CODES[2])

    assert scheduled.status_code == CareRecord.Status.SCHEDULED
    assert scheduled.visit_result_public_id is None
    assert completed.status_code == CareRecord.Status.COMPLETED
    assert completed.performed_by.username == DEMO_TECHNICIAN_USERNAME
    assert completed.completed_at is not None
    assert cancelled.status_code == CareRecord.Status.CANCELLED
    assert cancelled.cancelled_at is not None
    assert cancelled.cancellation_reason
