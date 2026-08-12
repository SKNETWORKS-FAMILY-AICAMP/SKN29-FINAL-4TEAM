"""T-005 status-history table alignment and bridge migration tests."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AuditEvent
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.questionnaires.models import QuestionnaireSession
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import TransitionHistory


pytestmark = pytest.mark.django_db
INQUIRY_LATEST = ("inquiries", "0013_inquiry_priority_code")
LATEST_SCHEMA = [
    ("workflow", "0005_status_history_contract_names_indexes"),
    INQUIRY_LATEST,
]


def restore_latest_schema() -> None:
    MigrationExecutor(connection).migrate(LATEST_SCHEMA)


def create_subscription(sequence: int) -> CustomerSubscription:
    user = User.objects.create_user(
        username=f"STATUS-HISTORY-{sequence:03d}",
        full_name=f"Status history user {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    customer = CustomerProfile.objects.create(
        user=user,
        customer_no=f"STATUS-HISTORY-CUS-{sequence:03d}",
        customer_name=f"Status history customer {sequence}",
    )
    product = ProductModel.objects.create(
        model_code=f"STATUS-HISTORY-PMD-{sequence:03d}",
        model_name=f"Status history product {sequence}",
    )
    return CustomerSubscription.objects.create(
        contract_no=f"STATUS-HISTORY-SUB-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"STATUS-HISTORY-SERIAL-{sequence:03d}",
        started_on=date(2026, 7, 1),
    )


def create_inquiry(
    sequence: int,
    *,
    subscription: CustomerSubscription | None = None,
) -> Inquiry:
    assigned_subscription = subscription or create_subscription(sequence)
    return Inquiry.objects.create(
        subscription=assigned_subscription,
        initiated_by=assigned_subscription.customer.user,
        channel_code=Inquiry.Channel.WEB,
        raw_text=f"Status history inquiry {sequence}.",
    )


def transition_audit_fk_definition() -> str:
    """Return the physical AuditEvent FK target definition."""

    with connection.cursor() as cursor:
        if connection.vendor == "sqlite":
            cursor.execute("PRAGMA foreign_key_list('audit_event')")
            rows = cursor.fetchall()
            matching = [
                row
                for row in rows
                if row[3] == "transition_history_id"
            ]
            assert len(matching) == 1
            return (
                "FOREIGN KEY (transition_history_id) "
                f"REFERENCES {matching[0][2]}(id)"
            )

        if connection.vendor == "postgresql":
            cursor.execute(
                """
                SELECT pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = 'audit_event'::regclass
                  AND contype = 'f'
                """
            )
            definitions = [
                row[0] for row in cursor.fetchall()
            ]
            matching = [
                definition
                for definition in definitions
                if "FOREIGN KEY (transition_history_id)"
                in definition
            ]
            assert len(matching) == 1
            return matching[0]

    raise AssertionError(
        f"Unsupported database vendor: {connection.vendor}"
    )


def status_history_index_definitions() -> dict[str, str]:
    """Return physical Index DDL for predicate and uniqueness checks."""

    with connection.cursor() as cursor:
        if connection.vendor == "sqlite":
            cursor.execute(
                """
                SELECT name, sql
                FROM sqlite_master
                WHERE type = 'index'
                  AND tbl_name = 'support_inquiry_status_history'
                  AND sql IS NOT NULL
                """
            )
            return dict(cursor.fetchall())

        if connection.vendor == "postgresql":
            cursor.execute(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = current_schema()
                  AND tablename = 'support_inquiry_status_history'
                """
            )
            return dict(cursor.fetchall())

    raise AssertionError(
        f"Unsupported database vendor: {connection.vendor}"
    )


def test_status_history_uses_contract_table_columns_and_targets():
    meta = TransitionHistory._meta

    assert meta.db_table == "support_inquiry_status_history"
    assert meta.get_field("id").get_internal_type() == "BigAutoField"
    assert meta.get_field("public_id").unique is True
    assert meta.get_field("questionnaire_session").column == (
        "questionnaire_session_id"
    )
    assert meta.get_field("actor").column == "changed_by_id"
    assert meta.get_field("from_state").column == "from_status_code"
    assert meta.get_field("to_state").column == "to_status_code"
    assert meta.get_field("event_code").max_length == 60
    assert meta.get_field("event_code").choices is None
    assert meta.get_field("from_state").choices is None
    assert meta.get_field("to_state").choices is None
    assert meta.get_field("change_reason").null is True
    assert meta.get_field("idempotency_key").unique is False
    assert not hasattr(TransitionHistory, "questionnaire_session_public_id")

    constraint_names = {
        constraint.name for constraint in meta.constraints
    }
    assert constraint_names == {
        "ck_status_history_exactly_one_target",
        "ck_status_history_target_type_matches_fk",
        "ck_status_history_version_positive",
        "ck_status_history_changed_by",
        "ck_status_history_version_origin",
        "uq_status_history_questionnaire_version",
        "uq_status_history_inquiry_version",
        "uq_status_history_consultation_version",
        "uq_status_history_visit_version",
    }
    assert {index.name for index in meta.indexes} == {
        "ix_status_hist_target_event",
        "ix_status_hist_correlation",
        "ix_status_q_event_idem",
        "ix_status_inq_event_idem",
        "ix_status_cons_event_idem",
        "ix_status_visit_event_idem",
    }


def test_status_history_database_uses_contract_columns_and_indexes():
    with connection.cursor() as cursor:
        table_names = set(connection.introspection.table_names(cursor))
        description = connection.introspection.get_table_description(
            cursor,
            "support_inquiry_status_history",
        )
        constraints = connection.introspection.get_constraints(
            cursor,
            "support_inquiry_status_history",
        )

    columns = {column.name for column in description}
    assert "support_inquiry_status_history" in table_names
    assert "workflow_transition_history" not in table_names
    assert {
        "questionnaire_session_id",
        "inquiry_id",
        "consultation_id",
        "visit_id",
        "changed_by_id",
        "from_status_code",
        "to_status_code",
    }.issubset(columns)
    assert {
        "questionnaire_session_public_id",
        "actor_id",
        "from_state",
        "to_state",
    }.isdisjoint(columns)
    assert {
        "ix_status_hist_target_event",
        "ix_status_hist_correlation",
        "ix_status_q_event_idem",
        "ix_status_inq_event_idem",
        "ix_status_cons_event_idem",
        "ix_status_visit_event_idem",
        "uq_status_history_questionnaire_version",
        "uq_status_history_inquiry_version",
        "uq_status_history_consultation_version",
        "uq_status_history_visit_version",
    }.issubset(constraints)


def test_partial_index_predicates_and_uniqueness_match_physical_contract():
    definitions = status_history_index_definitions()
    target_indexes = {
        "QUESTIONNAIRE": (
            "ix_status_q_event_idem",
            "uq_status_history_questionnaire_version",
        ),
        "INQUIRY": (
            "ix_status_inq_event_idem",
            "uq_status_history_inquiry_version",
        ),
        "CONSULTATION": (
            "ix_status_cons_event_idem",
            "uq_status_history_consultation_version",
        ),
        "VISIT": (
            "ix_status_visit_event_idem",
            "uq_status_history_visit_version",
        ),
    }

    for target, (trace_name, version_name) in target_indexes.items():
        trace_definition = definitions[trace_name].upper()
        version_definition = definitions[version_name].upper()

        assert " WHERE " in trace_definition
        assert target in trace_definition
        assert "UNIQUE INDEX" not in trace_definition
        assert " WHERE " in version_definition
        assert target in version_definition
        assert "UNIQUE INDEX" in version_definition

    target_event = definitions[
        "ix_status_hist_target_event"
    ].upper()
    assert "TARGET_TYPE_CODE" in target_event
    assert "EVENT_CODE" in target_event
    assert "CHANGED_AT" in target_event
    assert "DESC" in target_event


def test_questionnaire_history_enforces_target_and_version_integrity():
    subscription = create_subscription(1)
    session = QuestionnaireSession.objects.create(
        session_no="STATUS-HISTORY-Q-001",
        subscription=subscription,
        questionnaire_version="v1",
    )
    history = TransitionHistory.objects.create(
        target_type_code=TransitionHistory.TargetType.QUESTIONNAIRE,
        questionnaire_session=session,
        actor=None,
        changed_by_type_code=TransitionHistory.ChangedByType.SYSTEM,
        event_code="START_QUESTIONNAIRE",
        from_state=None,
        to_state="UNANSWERED",
        state_version=1,
        correlation_id=uuid4(),
        idempotency_key="status-history-questionnaire-1",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            TransitionHistory.objects.filter(pk=history.pk).update(
                questionnaire_session=None,
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            TransitionHistory.objects.create(
                target_type_code=(
                    TransitionHistory.TargetType.QUESTIONNAIRE
                ),
                questionnaire_session=session,
                actor=None,
                changed_by_type_code=(
                    TransitionHistory.ChangedByType.SYSTEM
                ),
                event_code="SAVE_CARE_PRECHECK",
                from_state=None,
                to_state="UNANSWERED",
                state_version=1,
                correlation_id=uuid4(),
                idempotency_key="status-history-questionnaire-dup",
            )

    inquiry = create_inquiry(11, subscription=subscription)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            TransitionHistory.objects.create(
                target_type_code=(
                    TransitionHistory.TargetType.QUESTIONNAIRE
                ),
                questionnaire_session=session,
                inquiry=inquiry,
                actor=None,
                changed_by_type_code=(
                    TransitionHistory.ChangedByType.SYSTEM
                ),
                event_code="LINK_INQUIRY",
                from_state="UNANSWERED",
                to_state="IN_PROGRESS",
                state_version=2,
                correlation_id=uuid4(),
                idempotency_key="status-history-two-targets",
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            TransitionHistory.objects.create(
                target_type_code=(
                    TransitionHistory.TargetType.QUESTIONNAIRE
                ),
                inquiry=inquiry,
                actor=None,
                changed_by_type_code=(
                    TransitionHistory.ChangedByType.SYSTEM
                ),
                event_code="LINK_INQUIRY",
                from_state="UNANSWERED",
                to_state="IN_PROGRESS",
                state_version=2,
                correlation_id=uuid4(),
                idempotency_key="status-history-wrong-target-type",
            )


def test_audit_event_keeps_protected_inbound_status_history_fk():
    inquiry = create_inquiry(12)
    transition = TransitionHistory.objects.create(
        target_type_code=TransitionHistory.TargetType.INQUIRY,
        inquiry=inquiry,
        actor=inquiry.initiated_by,
        changed_by_type_code=TransitionHistory.ChangedByType.USER,
        event_code="START_INQUIRY",
        from_state=None,
        to_state="DRAFT",
        state_version=1,
        correlation_id=uuid4(),
        idempotency_key="status-history-audit-inbound",
    )
    audit = AuditEvent.objects.create(
        audit_code="STATUS-HISTORY-AUDIT-INBOUND",
        transition=transition,
        entity_type=AuditEvent.EntityType.INQUIRY,
        inquiry=inquiry,
        event_code=transition.event_code,
        actor_role=AuditEvent.ActorRole.CUSTOMER,
        actor=inquiry.initiated_by,
        state_version=transition.state_version,
        idempotency_key=transition.idempotency_key,
        correlation_id=transition.correlation_id,
        occurred_at=transition.changed_at,
    )

    assert audit.transition == transition
    assert (
        "REFERENCES support_inquiry_status_history"
        in transition_audit_fk_definition()
    )
    with pytest.raises(ProtectedError):
        transition.delete()


@pytest.mark.django_db(transaction=True)
def test_status_history_migration_backfills_and_restores_uuid_bridge(
    request,
):
    restore_latest_schema()
    request.addfinalizer(restore_latest_schema)
    target_0003 = [
        ("workflow", "0003_backfill_legacy_changed_at"),
        INQUIRY_LATEST,
    ]
    target_0004 = [
        ("workflow", "0004_align_contract_status_history"),
        INQUIRY_LATEST,
    ]

    executor = MigrationExecutor(connection)
    executor.migrate(target_0003)
    history_0003 = executor.loader.project_state(
        target_0003
    ).apps.get_model("workflow", "TransitionHistory")
    subscription = create_subscription(2)
    session = QuestionnaireSession.objects.create(
        session_no="STATUS-HISTORY-Q-002",
        subscription=subscription,
        questionnaire_version="v1",
    )
    legacy = history_0003.objects.create(
        target_type_code="QUESTIONNAIRE",
        questionnaire_session_public_id=session.public_id,
        actor_id=None,
        changed_by_type_code="SYSTEM",
        event_code="START_QUESTIONNAIRE",
        from_state=None,
        to_state="UNANSWERED",
        state_version=1,
        correlation_id=uuid4(),
        idempotency_key="status-history-migration-2",
    )

    executor = MigrationExecutor(connection)
    executor.migrate(target_0004)
    history_0004 = executor.loader.project_state(
        target_0004
    ).apps.get_model("workflow", "TransitionHistory")
    migrated = history_0004.objects.get(pk=legacy.pk)
    assert migrated.questionnaire_session_id == session.pk
    assert history_0004._meta.db_table == (
        "support_inquiry_status_history"
    )

    executor = MigrationExecutor(connection)
    executor.migrate(target_0003)
    history_0003 = executor.loader.project_state(
        target_0003
    ).apps.get_model("workflow", "TransitionHistory")
    restored = history_0003.objects.get(pk=legacy.pk)
    assert restored.questionnaire_session_public_id == session.public_id

    executor = MigrationExecutor(connection)
    executor.migrate(target_0004)


@pytest.mark.django_db(transaction=True)
def test_status_history_migration_preserves_125_rows_and_audit_inbound_fk(
    request,
):
    restore_latest_schema()
    request.addfinalizer(restore_latest_schema)
    target_0003 = [
        ("workflow", "0003_backfill_legacy_changed_at"),
        INQUIRY_LATEST,
    ]
    target_0004 = [
        ("workflow", "0004_align_contract_status_history"),
        INQUIRY_LATEST,
    ]

    executor = MigrationExecutor(connection)
    executor.migrate(target_0003)
    history_0003 = executor.loader.project_state(
        target_0003
    ).apps.get_model("workflow", "TransitionHistory")
    inquiry = create_inquiry(125)
    created_rows = []
    for version in range(1, 126):
        history = history_0003.objects.create(
            target_type_code="INQUIRY",
            inquiry_id=inquiry.pk,
            actor_id=inquiry.initiated_by_id,
            changed_by_type_code="USER",
            event_code="START_INQUIRY",
            from_state=None if version == 1 else "DRAFT",
            to_state="DRAFT",
            state_version=version,
            correlation_id=uuid4(),
            idempotency_key=f"status-history-preserve-{version:03d}",
            change_reason=f"Preservation fixture {version}",
        )
        created_rows.append(
            (
                history.pk,
                history.public_id,
                history.status_history_code,
                history.state_version,
                history.idempotency_key,
            )
        )
        AuditEvent.objects.create(
            audit_code=f"STATUS-HISTORY-PRESERVE-{version:03d}",
            transition_id=history.pk,
            entity_type=AuditEvent.EntityType.INQUIRY,
            inquiry=inquiry,
            event_code=history.event_code,
            actor_role=AuditEvent.ActorRole.CUSTOMER,
            actor=inquiry.initiated_by,
            state_version=history.state_version,
            idempotency_key=history.idempotency_key,
            correlation_id=history.correlation_id,
            occurred_at=timezone.now(),
        )

    assert history_0003.objects.count() == 125
    assert AuditEvent.objects.count() == 125
    assert (
        "REFERENCES workflow_transition_history"
        in transition_audit_fk_definition()
    )

    executor = MigrationExecutor(connection)
    executor.migrate(target_0004)
    history_0004 = executor.loader.project_state(
        target_0004
    ).apps.get_model("workflow", "TransitionHistory")
    migrated_rows = list(
        history_0004.objects.order_by("pk").values_list(
            "pk",
            "public_id",
            "status_history_code",
            "state_version",
            "idempotency_key",
        )
    )
    assert migrated_rows == created_rows
    assert AuditEvent.objects.count() == 125
    assert {
        audit.transition_id
        for audit in AuditEvent.objects.select_related("transition")
    } == {row[0] for row in created_rows}
    assert (
        "REFERENCES support_inquiry_status_history"
        in transition_audit_fk_definition()
    )

    executor = MigrationExecutor(connection)
    executor.migrate(target_0003)
    history_0003 = executor.loader.project_state(
        target_0003
    ).apps.get_model("workflow", "TransitionHistory")
    restored_rows = list(
        history_0003.objects.order_by("pk").values_list(
            "pk",
            "public_id",
            "status_history_code",
            "state_version",
            "idempotency_key",
        )
    )
    assert restored_rows == created_rows
    assert AuditEvent.objects.count() == 125
    assert (
        "REFERENCES workflow_transition_history"
        in transition_audit_fk_definition()
    )

    executor = MigrationExecutor(connection)
    executor.migrate(target_0004)
    assert TransitionHistory.objects.count() == 125
    assert AuditEvent.objects.count() == 125
    assert (
        "REFERENCES support_inquiry_status_history"
        in transition_audit_fk_definition()
    )


@pytest.mark.django_db(transaction=True)
def test_status_history_contract_names_are_isolated_in_reversible_0005(
    request,
):
    restore_latest_schema()
    request.addfinalizer(restore_latest_schema)
    target_0004 = [
        ("workflow", "0004_align_contract_status_history"),
        INQUIRY_LATEST,
    ]
    target_0005 = [
        ("workflow", "0005_status_history_contract_names_indexes"),
        INQUIRY_LATEST,
    ]
    old_constraints = {
        "ck_transition_state_version_positive",
        "ck_hist_actor_matches_type",
        "ck_hist_version_origin",
    }
    new_constraints = {
        "ck_status_history_version_positive",
        "ck_status_history_changed_by",
        "ck_status_history_version_origin",
    }

    executor = MigrationExecutor(connection)
    executor.migrate(target_0004)
    history_0004 = executor.loader.project_state(
        target_0004
    ).apps.get_model("workflow", "TransitionHistory")
    constraints_0004 = {
        constraint.name
        for constraint in history_0004._meta.constraints
    }
    indexes_0004 = {
        index.name for index in history_0004._meta.indexes
    }
    assert old_constraints.issubset(constraints_0004)
    assert new_constraints.isdisjoint(constraints_0004)
    assert "ix_transition_correlation" in indexes_0004
    assert "ix_status_hist_correlation" not in indexes_0004
    assert "ix_status_hist_target_event" not in indexes_0004

    executor = MigrationExecutor(connection)
    executor.migrate(target_0005)
    history_0005 = executor.loader.project_state(
        target_0005
    ).apps.get_model("workflow", "TransitionHistory")
    constraints_0005 = {
        constraint.name
        for constraint in history_0005._meta.constraints
    }
    indexes_0005 = {
        index.name for index in history_0005._meta.indexes
    }
    assert new_constraints.issubset(constraints_0005)
    assert old_constraints.isdisjoint(constraints_0005)
    assert "ix_status_hist_correlation" in indexes_0005
    assert "ix_status_hist_target_event" in indexes_0005
    assert "ix_transition_correlation" not in indexes_0005

    executor = MigrationExecutor(connection)
    executor.migrate(target_0004)
    restored_0004 = executor.loader.project_state(
        target_0004
    ).apps.get_model("workflow", "TransitionHistory")
    assert old_constraints.issubset(
        {
            constraint.name
            for constraint in restored_0004._meta.constraints
        }
    )
    assert {
        "ix_transition_correlation",
    }.issubset(
        {index.name for index in restored_0004._meta.indexes}
    )

    executor = MigrationExecutor(connection)
    executor.migrate(target_0005)
