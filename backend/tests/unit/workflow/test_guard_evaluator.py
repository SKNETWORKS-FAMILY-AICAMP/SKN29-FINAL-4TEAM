from __future__ import annotations

from dataclasses import replace

import pytest

from apps.workflow.domain import WorkflowSnapshot
from apps.workflow.engine import (
    GuardContext,
    GuardEvaluator,
    StateMachine,
)


@pytest.fixture(scope="module")
def state_machine() -> StateMachine:
    return StateMachine()


@pytest.fixture(scope="module")
def guard_evaluator() -> GuardEvaluator:
    return GuardEvaluator()


def test_start_inquiry_passes_with_explicit_domain_guard_result(
    state_machine: StateMachine,
    guard_evaluator: GuardEvaluator,
):
    snapshot = WorkflowSnapshot(
        inquiry_state=None,
        state_version=None,
    )
    transition = state_machine.resolve(
        snapshot=snapshot,
        event_code="START_INQUIRY",
    )

    result = guard_evaluator.evaluate(
        transition=transition,
        snapshot=snapshot,
        context=GuardContext(
            actor_role="CUSTOMER",
            is_authenticated=True,
            correlation_id="corr-start-001",
            idempotency_key="idem-start-001",
            requested_state_version=None,
            domain_results={"G-CUSTOMER-PRODUCT-OWNERSHIP": True},
        ),
    )

    assert result.allowed is True
    assert result.failure is None


def test_missing_domain_guard_result_fails_closed(
    state_machine: StateMachine,
    guard_evaluator: GuardEvaluator,
):
    snapshot = WorkflowSnapshot(
        inquiry_state=None,
        state_version=None,
    )
    transition = state_machine.resolve(
        snapshot=snapshot,
        event_code="START_INQUIRY",
    )

    result = guard_evaluator.evaluate(
        transition=transition,
        snapshot=snapshot,
        context=GuardContext(
            actor_role="CUSTOMER",
            is_authenticated=True,
            correlation_id="corr-start-002",
            idempotency_key="idem-start-002",
            requested_state_version=None,
        ),
    )

    assert result.allowed is False
    assert result.failure is not None
    assert result.failure.guard_id == "G-CUSTOMER-PRODUCT-OWNERSHIP"
    assert result.failure.reason == "DOMAIN_RESULT_MISSING"


def test_ai_timeout_requires_trusted_system_and_audited_timeout_result(
    state_machine: StateMachine,
    guard_evaluator: GuardEvaluator,
):
    snapshot = WorkflowSnapshot(
        inquiry_state="QUESTIONNAIRE_IN_PROGRESS",
        state_version=2,
    )
    transition = state_machine.resolve(
        snapshot=snapshot,
        event_code="AI_PROCESSING_TIMEOUT",
    )
    context = GuardContext(
        actor_role="SYSTEM",
        is_authenticated=False,
        correlation_id="corr-timeout-001",
        idempotency_key=None,
        requested_state_version=2,
        trusted_internal_actor=True,
        domain_results={"G-AI-PROCESSING-TIMEOUT-VALID": True},
    )

    assert guard_evaluator.evaluate(
        transition=transition,
        snapshot=snapshot,
        context=context,
    ).allowed is True

    rejected = guard_evaluator.evaluate(
        transition=transition,
        snapshot=snapshot,
        context=replace(
            context,
            domain_results={"G-AI-PROCESSING-TIMEOUT-VALID": False},
        ),
    )
    assert rejected.allowed is False
    assert rejected.failure is not None
    assert rejected.failure.guard_id == "G-AI-PROCESSING-TIMEOUT-VALID"
    assert rejected.failure.error_code == (
        "AI_PROCESSING_TIMEOUT_PRECONDITION_FAILED"
    )


def test_state_version_mismatch_returns_contract_409(
    state_machine: StateMachine,
    guard_evaluator: GuardEvaluator,
):
    snapshot = WorkflowSnapshot(
        inquiry_state="DRAFT",
        state_version=3,
    )
    transition = state_machine.resolve(
        snapshot=snapshot,
        event_code="CANCEL_INQUIRY",
    )

    result = guard_evaluator.evaluate(
        transition=transition,
        snapshot=snapshot,
        context=GuardContext(
            actor_role="CUSTOMER",
            is_authenticated=True,
            correlation_id="corr-cancel-001",
            idempotency_key="idem-cancel-001",
            requested_state_version=2,
            domain_results={
                "G-CANCEL-ACTOR-AUTHORIZED": True,
                "G-CANCELLATION-REASON": True,
            },
        ),
    )

    assert result.allowed is False
    assert result.failure is not None
    assert result.failure.guard_id == "G-STATE-VERSION"
    assert result.failure.http_status == 409
    assert result.failure.error_code == "STATE_VERSION_CONFLICT"


def test_missing_correlation_id_is_rejected_before_domain_guards(
    state_machine: StateMachine,
    guard_evaluator: GuardEvaluator,
):
    snapshot = WorkflowSnapshot(
        inquiry_state=None,
        state_version=None,
    )
    transition = state_machine.resolve(
        snapshot=snapshot,
        event_code="START_INQUIRY",
    )

    result = guard_evaluator.evaluate(
        transition=transition,
        snapshot=snapshot,
        context=GuardContext(
            actor_role="CUSTOMER",
            is_authenticated=True,
            correlation_id=None,
            idempotency_key="idem-start-003",
            requested_state_version=None,
            domain_results={"G-CUSTOMER-PRODUCT-OWNERSHIP": True},
        ),
    )

    assert result.allowed is False
    assert result.failure is not None
    assert result.failure.reason == "MISSING_CORRELATION_ID"


def test_event_actor_role_mismatch_is_rejected_first(
    state_machine: StateMachine,
    guard_evaluator: GuardEvaluator,
):
    snapshot = WorkflowSnapshot(
        inquiry_state=None,
        state_version=None,
    )
    transition = state_machine.resolve(
        snapshot=snapshot,
        event_code="START_INQUIRY",
    )

    result = guard_evaluator.evaluate(
        transition=transition,
        snapshot=snapshot,
        context=GuardContext(
            actor_role="CONSULTANT",
            is_authenticated=True,
            correlation_id="corr-start-004",
            idempotency_key="idem-start-004",
            requested_state_version=None,
            domain_results={"G-CUSTOMER-PRODUCT-OWNERSHIP": True},
        ),
    )

    assert result.allowed is False
    assert result.failure is not None
    assert result.failure.reason == "EVENT_ROLE_MISMATCH"
    assert result.failure.error_code == "CUSTOMER_ROLE_REQUIRED"


def test_idempotency_key_is_required_and_bounded(
    state_machine: StateMachine,
    guard_evaluator: GuardEvaluator,
):
    snapshot = WorkflowSnapshot(
        inquiry_state=None,
        state_version=None,
    )
    transition = state_machine.resolve(
        snapshot=snapshot,
        event_code="START_INQUIRY",
    )

    result = guard_evaluator.evaluate(
        transition=transition,
        snapshot=snapshot,
        context=GuardContext(
            actor_role="CUSTOMER",
            is_authenticated=True,
            correlation_id="corr-start-005",
            idempotency_key="x" * 129,
            requested_state_version=None,
            domain_results={"G-CUSTOMER-PRODUCT-OWNERSHIP": True},
        ),
    )

    assert result.allowed is False
    assert result.failure is not None
    assert result.failure.guard_id == "G-IDEMPOTENCY-KEY"
    assert result.failure.reason == "MISSING_OR_INVALID_IDEMPOTENCY_KEY"
    assert result.failure.http_status == 422
    assert result.failure.error_code == "VALIDATION_ERROR"


def test_actor_last_handler_is_evaluated_as_domain_guard(
    state_machine: StateMachine,
    guard_evaluator: GuardEvaluator,
):
    snapshot = WorkflowSnapshot(
        inquiry_state="COMPLETION_PENDING",
        state_version=8,
        visit_status="COMPLETED",
    )
    transition = state_machine.resolve(
        snapshot=snapshot,
        event_code="FINALIZE_INQUIRY",
    )
    domain_results = {
        guard_id: True
        for guard_id in transition.guard_refs
        if guard_id
        not in {"G-STATE-VERSION", "G-IDEMPOTENCY-KEY"}
    }

    result = guard_evaluator.evaluate(
        transition=transition,
        snapshot=snapshot,
        context=GuardContext(
            actor_role="CONSULTANT",
            is_authenticated=True,
            correlation_id="corr-finalize-001",
            idempotency_key="idem-finalize-001",
            requested_state_version=8,
            domain_results=domain_results,
        ),
    )

    assert "G-ACTOR-LAST-HANDLER" in domain_results
    assert result.allowed is True
    assert result.failure is None


def test_unauthenticated_request_fails_before_role_membership(
    state_machine: StateMachine,
    guard_evaluator: GuardEvaluator,
):
    snapshot = WorkflowSnapshot(
        inquiry_state=None,
        state_version=None,
    )
    transition = state_machine.resolve(
        snapshot=snapshot,
        event_code="START_INQUIRY",
    )

    result = guard_evaluator.evaluate(
        transition=transition,
        snapshot=snapshot,
        context=GuardContext(
            actor_role=None,
            is_authenticated=False,
            correlation_id="corr-unauthenticated",
            idempotency_key="idem-unauthenticated",
            requested_state_version=None,
        ),
    )

    assert result.allowed is False
    assert result.failure is not None
    assert result.failure.http_status == 401
    assert result.failure.error_code == "AUTH_REQUIRED"


def test_missing_required_idempotency_guard_fails_closed(
    state_machine: StateMachine,
    guard_evaluator: GuardEvaluator,
):
    snapshot = WorkflowSnapshot(
        inquiry_state="DRAFT",
        state_version=1,
    )
    transition = state_machine.resolve(
        snapshot=snapshot,
        event_code="CANCEL_INQUIRY",
    )
    transition = replace(
        transition,
        guard_refs=tuple(
            guard_id
            for guard_id in transition.guard_refs
            if guard_id != "G-IDEMPOTENCY-KEY"
        ),
    )

    result = guard_evaluator.evaluate(
        transition=transition,
        snapshot=snapshot,
        context=GuardContext(
            actor_role="CUSTOMER",
            is_authenticated=True,
            correlation_id="corr-missing-guard",
            idempotency_key=None,
            requested_state_version=1,
            domain_results={
                "G-CANCEL-ACTOR-AUTHORIZED": True,
                "G-CANCELLATION-REASON": True,
            },
        ),
    )

    assert result.allowed is False
    assert result.failure is not None
    assert result.failure.guard_id == "G-IDEMPOTENCY-KEY"
    assert result.failure.http_status == 500
    assert result.failure.error_code == "INTERNAL_ERROR"
    assert result.failure.reason == "REQUIRED_GUARD_MISSING"


def test_payload_guard_precedes_completion_guard(
    state_machine: StateMachine,
    guard_evaluator: GuardEvaluator,
):
    snapshot = WorkflowSnapshot(
        inquiry_state="COMPLETION_PENDING",
        state_version=9,
        visit_status="COMPLETED",
    )
    transition = state_machine.resolve(
        snapshot=snapshot,
        event_code="FINALIZE_INQUIRY",
    )

    result = guard_evaluator.evaluate(
        transition=transition,
        snapshot=snapshot,
        context=GuardContext(
            actor_role="CONSULTANT",
            is_authenticated=True,
            correlation_id="corr-precedence",
            idempotency_key="idem-precedence",
            requested_state_version=9,
            domain_results={
                "G-ACTOR-LAST-HANDLER": True,
                "G-RESOLVED-CUSTOMER-FEEDBACK-EXISTS": False,
                "G-FINALIZATION-PAYLOAD-VALID": False,
            },
        ),
    )

    assert result.allowed is False
    assert result.failure is not None
    assert result.failure.guard_id == "G-FINALIZATION-PAYLOAD-VALID"
