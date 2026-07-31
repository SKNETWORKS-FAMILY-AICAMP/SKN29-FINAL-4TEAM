"""T-005 Wave 1A 사전 문진 세션 Model·제약 검증."""

import importlib
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.questionnaires.models import QuestionnaireSession
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db


def create_subscription(sequence: int = 1) -> CustomerSubscription:
    user = User.objects.create_user(
        username=f"QSN-CUSTOMER-{sequence:03d}",
        password=None,
        full_name=f"Questionnaire customer {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    customer = CustomerProfile.objects.create(
        user=user,
        customer_no=f"QSN-CUSTOMER-NO-{sequence:03d}",
        customer_name=f"Questionnaire customer {sequence}",
    )
    product = ProductModel.objects.create(
        model_code=f"QSN-PMD-{sequence:03d}",
        model_name=f"Questionnaire product {sequence}",
    )
    return CustomerSubscription.objects.create(
        contract_no=f"QSN-SUB-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"QSN-SERIAL-{sequence:03d}",
        started_on=date(2026, 7, 1),
    )


def create_inquiry(
    subscription: CustomerSubscription,
    *,
    raw_text: str = "Questionnaire requires an inquiry.",
) -> Inquiry:
    return Inquiry.objects.create(
        subscription=subscription,
        initiated_by=subscription.customer.user,
        channel_code=Inquiry.Channel.WEB,
        raw_text=raw_text,
    )


def create_session(
    sequence: int = 1,
    *,
    subscription: CustomerSubscription | None = None,
    **overrides,
) -> QuestionnaireSession:
    values = {
        "session_no": f"QSN-SESSION-{sequence:03d}",
        "subscription": subscription or create_subscription(sequence),
        "questionnaire_version": "CARE_PRECHECK-v1",
        "creation_idempotency_key": f"qsn-create-{sequence:03d}",
    }
    values.update(overrides)
    return QuestionnaireSession.objects.create(**values)


def test_questionnaire_session_uses_target_identifier_policy_and_defaults():
    session = create_session()

    assert isinstance(session.pk, int)
    assert isinstance(session.public_id, UUID)
    assert session._meta.db_table == "support_questionnaire_session"
    assert (
        session.questionnaire_type_code
        == QuestionnaireSession.QuestionnaireType.CARE_PRECHECK
    )
    assert session.status_code == QuestionnaireSession.Status.UNANSWERED
    assert session.answers_payload == {}
    assert session.state_version == 1


def test_questionnaire_session_model_is_runtime_registered():
    assert QuestionnaireSession._meta.app_label == "questionnaires"
    assert QuestionnaireSession._meta.managed is True


def test_questionnaire_session_codes_and_version_are_database_constrained():
    subscription = create_subscription()
    base_values = {
        "subscription": subscription,
        "questionnaire_version": "CARE_PRECHECK-v1",
    }

    with pytest.raises(IntegrityError), transaction.atomic():
        QuestionnaireSession.objects.create(
            **base_values,
            session_no="QSN-INVALID-TYPE",
            creation_idempotency_key="qsn-invalid-type",
            questionnaire_type_code="ADHOC",
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        QuestionnaireSession.objects.create(
            **base_values,
            session_no="QSN-INVALID-STATUS",
            creation_idempotency_key="qsn-invalid-status",
            status_code="UNKNOWN",
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        QuestionnaireSession.objects.create(
            **base_values,
            session_no="QSN-INVALID-VERSION",
            creation_idempotency_key="qsn-invalid-version",
            state_version=0,
        )


def test_questionnaire_submission_and_link_lifecycle_are_constrained():
    subscription = create_subscription()
    started_at = timezone.now()

    with pytest.raises(IntegrityError), transaction.atomic():
        create_session(
            subscription=subscription,
            submitted_at=started_at,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_session(
            sequence=2,
            subscription=subscription,
            status_code=QuestionnaireSession.Status.SUBMITTED,
            submitted_at=None,
        )

    inquiry = create_inquiry(subscription)
    submitted_at = started_at + timedelta(minutes=1)
    session = create_session(
        sequence=3,
        subscription=subscription,
        inquiry=inquiry,
        status_code=QuestionnaireSession.Status.SUBMITTED,
        started_at=started_at,
        submitted_at=submitted_at,
        linked_at=submitted_at + timedelta(seconds=1),
    )

    assert session.inquiry == inquiry
    assert inquiry.questionnaire_session == session


def test_questionnaire_session_rejects_non_object_answers():
    session = QuestionnaireSession(
        session_no="QSN-OBJECT-CHECK",
        subscription=create_subscription(),
        questionnaire_version="CARE_PRECHECK-v1",
        answers_payload=["not", "an", "object"],
        creation_idempotency_key="qsn-object-check",
    )

    with pytest.raises(ValidationError) as exc_info:
        session.full_clean()

    assert "answers_payload" in exc_info.value.message_dict

    with pytest.raises(IntegrityError), transaction.atomic():
        create_session(
            sequence=4,
            answers_payload=["not", "an", "object"],
        )


def test_questionnaire_session_and_inquiry_must_share_subscription():
    first_subscription = create_subscription()
    other_subscription = create_subscription(sequence=2)
    inquiry = create_inquiry(other_subscription)
    submitted_at = timezone.now()
    session = QuestionnaireSession(
        session_no="QSN-SUBSCRIPTION-MISMATCH",
        subscription=first_subscription,
        inquiry=inquiry,
        questionnaire_version="CARE_PRECHECK-v1",
        status_code=QuestionnaireSession.Status.SUBMITTED,
        submitted_at=submitted_at,
        linked_at=submitted_at,
        creation_idempotency_key="qsn-subscription-mismatch",
    )

    with pytest.raises(ValidationError) as exc_info:
        session.full_clean()

    assert "inquiry" in exc_info.value.message_dict


def test_inquiry_exposes_composite_reference_key():
    constraints = {
        constraint.name: constraint
        for constraint in Inquiry._meta.constraints
    }

    reference_key = constraints["ux_inquiry_id_subscription"]

    assert tuple(reference_key.fields) == ("id", "subscription")


def test_postgresql_composite_fk_migration_matches_contract():
    migration_module = importlib.import_module(
        "apps.questionnaires.migrations."
        "0002_postgresql_inquiry_subscription_fk"
    )
    assert (
        "inquiries",
        "0005_inquiry_ux_inquiry_id_subscription",
    ) in migration_module.Migration.dependencies

    statements: list[str] = []
    schema_editor = SimpleNamespace(
        connection=SimpleNamespace(vendor="postgresql"),
        execute=statements.append,
    )

    migration_module.add_inquiry_subscription_fk(
        None,
        schema_editor,
    )

    normalized_sql = " ".join(statements[0].split())
    assert (
        "ADD CONSTRAINT fk_questionnaire_inquiry_subscription"
        in normalized_sql
    )
    assert (
        "FOREIGN KEY (inquiry_id, subscription_id)"
        in normalized_sql
    )
    assert (
        "REFERENCES support_inquiry (id, subscription_id)"
        in normalized_sql
    )
    assert "MATCH SIMPLE" in normalized_sql
    assert "ON DELETE RESTRICT" in normalized_sql

    reverse_statements: list[str] = []
    reverse_schema_editor = SimpleNamespace(
        connection=SimpleNamespace(vendor="postgresql"),
        execute=reverse_statements.append,
    )
    migration_module.remove_inquiry_subscription_fk(
        None,
        reverse_schema_editor,
    )
    normalized_reverse_sql = " ".join(
        reverse_statements[0].split()
    )
    assert (
        "DROP CONSTRAINT IF EXISTS "
        "fk_questionnaire_inquiry_subscription"
        in normalized_reverse_sql
    )

    sqlite_statements: list[str] = []
    sqlite_schema_editor = SimpleNamespace(
        connection=SimpleNamespace(vendor="sqlite"),
        execute=sqlite_statements.append,
    )
    migration_module.add_inquiry_subscription_fk(
        None,
        sqlite_schema_editor,
    )

    assert sqlite_statements == []


def test_questionnaire_session_unique_keys_and_fk_deletion_are_protected():
    session = create_session()

    with pytest.raises(IntegrityError), transaction.atomic():
        create_session(
            sequence=2,
            session_no=session.session_no,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_session(
            sequence=3,
            creation_idempotency_key=(
                session.creation_idempotency_key
            ),
        )

    with pytest.raises(ProtectedError):
        session.subscription.delete()


def test_questionnaire_session_index_matches_contract_access_path():
    indexes = {
        index.name: tuple(index.fields)
        for index in QuestionnaireSession._meta.indexes
    }

    assert indexes == {
        "ix_qsession_sub_status": (
            "subscription",
            "status_code",
            "-created_at",
        )
    }
