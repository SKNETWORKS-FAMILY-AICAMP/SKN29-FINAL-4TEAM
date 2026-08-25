"""Consultation handoff row-lock scope regression tests."""

from uuid import uuid4

import pytest
from django.db.models.query import QuerySet

from apps.consultations.services import ConsultationHandoffService
from common.exceptions.business import BusinessError


pytestmark = pytest.mark.django_db


def test_handoff_inquiry_lock_targets_only_inquiry_row(monkeypatch):
    """Keep the nullable customer-user join outside PostgreSQL's lock list."""

    calls = []
    original = QuerySet.select_for_update

    def record_select_for_update(queryset, *args, **kwargs):
        calls.append((args, kwargs))
        return original(queryset, *args, **kwargs)

    monkeypatch.setattr(
        QuerySet,
        "select_for_update",
        record_select_for_update,
    )

    with pytest.raises(BusinessError):
        ConsultationHandoffService.persist(
            inquiry_public_id=uuid4(),
            validated_data={},
            idempotency_key="missing-inquiry",
            correlation_id=uuid4(),
        )

    assert calls == [((), {"of": ("self",)})]
