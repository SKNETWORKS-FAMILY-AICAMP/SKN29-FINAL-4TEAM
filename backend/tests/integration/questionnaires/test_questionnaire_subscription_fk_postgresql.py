"""PostgreSQL enforcement tests for the questionnaire/inquiry composite FK."""

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.questionnaires.models import QuestionnaireSession
from tests.unit.questionnaires.test_questionnaire_session_model import (
    create_inquiry,
    create_session,
    create_subscription,
)


pytestmark = pytest.mark.django_db(transaction=True)

CONSTRAINT_NAME = "fk_questionnaire_inquiry_subscription"


def assert_composite_fk_violation(exc: IntegrityError) -> None:
    """Confirm that this Wave's PostgreSQL constraint rejected the write."""

    database_error = exc.__cause__
    assert database_error is not None
    assert database_error.diag.constraint_name == CONSTRAINT_NAME


def test_postgresql_enforces_same_subscription_for_linked_inquiry():
    """Reject ORM and raw-SQL attempts to create a cross-subscription link."""

    if connection.vendor != "postgresql":
        pytest.skip("Composite FK enforcement is PostgreSQL-specific.")

    first_subscription = create_subscription(sequence=701)
    other_subscription = create_subscription(sequence=702)
    first_inquiry = create_inquiry(
        first_subscription,
        raw_text="Questionnaire link on the same subscription.",
    )
    other_inquiry = create_inquiry(
        other_subscription,
        raw_text="Questionnaire link on another subscription.",
    )
    linked_at = timezone.now()

    session = create_session(
        sequence=701,
        subscription=first_subscription,
        inquiry=first_inquiry,
        status_code=QuestionnaireSession.Status.SUBMITTED,
        started_at=linked_at,
        submitted_at=linked_at,
        linked_at=linked_at,
    )
    unlinked_session = create_session(
        sequence=702,
        subscription=other_subscription,
    )

    assert session.inquiry_id == first_inquiry.pk
    assert unlinked_session.inquiry_id is None

    with pytest.raises(IntegrityError) as update_inquiry_error:
        with transaction.atomic():
            QuestionnaireSession.objects.filter(pk=session.pk).update(
                inquiry_id=other_inquiry.pk,
            )
    assert_composite_fk_violation(update_inquiry_error.value)

    session.refresh_from_db()
    assert session.inquiry_id == first_inquiry.pk
    assert session.subscription_id == first_subscription.pk

    with pytest.raises(IntegrityError) as update_subscription_error:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE support_questionnaire_session
                SET subscription_id = %s
                WHERE id = %s
                """,
                [other_subscription.pk, session.pk],
            )
    assert_composite_fk_violation(update_subscription_error.value)

    session.refresh_from_db()
    assert session.inquiry_id == first_inquiry.pk
    assert session.subscription_id == first_subscription.pk

    with pytest.raises(IntegrityError) as update_parent_error:
        with transaction.atomic():
            type(first_inquiry).objects.filter(pk=first_inquiry.pk).update(
                subscription=other_subscription,
            )
    assert_composite_fk_violation(update_parent_error.value)

    first_inquiry.refresh_from_db()
    assert first_inquiry.subscription_id == first_subscription.pk
