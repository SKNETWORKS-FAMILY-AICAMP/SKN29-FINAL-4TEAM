"""PostgreSQL row-lock verification for T-020 care schedule recalculation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connection

from apps.care.models import CareRecord
from apps.care.services.care_cycle_rule_registry import (
    ApprovedCareCycleRuleRegistry,
)
from apps.care.services.care_schedule_service import CareScheduleService
from tests.unit.care.test_care_cycle_rule_registry import entry
from tests.unit.care.test_care_schedule_service import create_subscription


pytestmark = pytest.mark.django_db(transaction=True)


def test_postgresql_concurrent_registry_recalculation_writes_one_schedule():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    subscription = create_subscription(sequence=301)
    registry = ApprovedCareCycleRuleRegistry([entry()])
    start = Barrier(2)

    def recalculate():
        close_old_connections()
        try:
            start.wait(timeout=10)
            return CareScheduleService.recalculate_from_registry(
                subscription_public_id=subscription.public_id,
                care_type_code=CareRecord.CareType.FILTER_REPLACEMENT,
                registry=registry,
                change_reason="TEST_CONCURRENT_RECALCULATION",
            )
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _index: recalculate(), range(2)))

    assert sorted(outcome.changed for outcome in outcomes) == [False, True]
    assert len({outcome.schedule_record_id for outcome in outcomes}) == 1
    assert (
        CareRecord.objects.filter(
            subscription=subscription,
            status_code=CareRecord.Status.SCHEDULED,
        ).count()
        == 1
    )
