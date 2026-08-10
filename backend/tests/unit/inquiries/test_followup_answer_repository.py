"""Follow-up answer repository row-lock scope regression tests."""

from uuid import uuid4

import pytest
from django.db.models.query import QuerySet

from apps.inquiries.repositories.inquiry_repository import InquiryRepository


pytestmark = pytest.mark.django_db


def test_unanswered_question_lock_targets_only_question_rows(monkeypatch):
    """Keep the nullable customer_answer join outside PostgreSQL's lock."""

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

    assert InquiryRepository.lock_unanswered_questions(
        inquiry=1,
        question_public_ids=[uuid4()],
    ) == []
    assert calls == [((), {"of": ("self",)})]
