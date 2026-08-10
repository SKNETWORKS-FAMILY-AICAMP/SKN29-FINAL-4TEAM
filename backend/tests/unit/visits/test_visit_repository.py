"""Visit repository row-lock scope regression tests."""

from uuid import uuid4

import pytest
from django.db.models.query import QuerySet

from apps.visits.repositories.visit_repository import VisitRepository


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("repository_call", "arguments"),
    [
        (VisitRepository.lock_latest, {"inquiry": 1}),
        (
            VisitRepository.lock_by_public_id,
            {"inquiry": 1, "visit_public_id": uuid4()},
        ),
    ],
)
def test_visit_locks_target_only_self_across_supported_backends(
    monkeypatch,
    repository_call,
    arguments,
):
    """Keep nullable technician joins outside PostgreSQL's FOR UPDATE list."""

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

    assert repository_call(**arguments) is None
    assert calls == [((), {"of": ("self",)})]
