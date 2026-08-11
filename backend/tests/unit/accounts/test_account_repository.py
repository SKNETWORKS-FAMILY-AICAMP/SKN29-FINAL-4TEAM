"""Account repository row-lock scope regression tests."""

from uuid import uuid4

import pytest
from django.db.models.query import QuerySet

from apps.accounts.repositories.account_repository import AccountRepository


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("repository_call", "argument"),
    [
        (AccountRepository.lock_active_by_pk, 0),
        (AccountRepository.lock_active_by_subject, str(uuid4())),
    ],
    ids=("primary-key", "jwt-subject"),
)
def test_account_locks_target_only_self_across_supported_backends(
    monkeypatch,
    repository_call,
    argument,
):
    """Keep the optional customer-profile join outside the lock list."""

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

    assert repository_call(argument) is None
    assert calls == [((), {"of": ("self",)})]
