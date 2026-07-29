from __future__ import annotations

import pytest

from apps.workflow.domain import WorkflowSnapshot
from apps.workflow.engine import InvalidStateTransition, StateMachine


@pytest.fixture(scope="module")
def state_machine() -> StateMachine:
    return StateMachine()


def test_start_inquiry_initializes_state_and_version(
    state_machine: StateMachine,
):
    transition = state_machine.resolve(
        snapshot=WorkflowSnapshot(
            inquiry_state=None,
            state_version=None,
        ),
        event_code="START_INQUIRY",
    )

    assert transition.rule_id == "TR-INQ-001"
    assert transition.inquiry_state_after == "DRAFT"
    assert transition.visit_status_after is None
    assert transition.state_version_after == 1
    assert transition.version_action == "INITIALIZE_1"


@pytest.mark.parametrize("terminal_state", ["RESOLVED", "CANCELLED"])
def test_terminal_states_deny_every_event(
    state_machine: StateMachine,
    terminal_state: str,
):
    with pytest.raises(InvalidStateTransition) as exc_info:
        state_machine.resolve(
            snapshot=WorkflowSnapshot(
                inquiry_state=terminal_state,
                state_version=4,
            ),
            event_code="CANCEL_INQUIRY",
        )

    assert exc_info.value.code == "INVALID_STATE_TRANSITION"
    assert exc_info.value.reason == "TERMINAL_STATE"


def test_unlisted_state_event_pair_fails_closed(
    state_machine: StateMachine,
):
    with pytest.raises(InvalidStateTransition) as exc_info:
        state_machine.resolve(
            snapshot=WorkflowSnapshot(
                inquiry_state="DRAFT",
                state_version=1,
            ),
            event_code="FINALIZE_INQUIRY",
        )

    assert exc_info.value.reason == "UNLISTED_TRANSITION"


@pytest.mark.parametrize(
    ("visit_status", "rule_id", "next_status"),
    [
        ("ASSIGNING", "TR-INQ-020", "SCHEDULING"),
        ("SCHEDULING", "TR-INQ-021", "SCHEDULING"),
    ],
)
def test_visit_status_selects_one_deterministic_transition(
    state_machine: StateMachine,
    visit_status: str,
    rule_id: str,
    next_status: str,
):
    transition = state_machine.resolve(
        snapshot=WorkflowSnapshot(
            inquiry_state="VISIT_SCHEDULING",
            state_version=3,
            visit_status=visit_status,
        ),
        event_code="UPDATE_VISIT_SCHEDULE",
    )

    assert transition.rule_id == rule_id
    assert transition.visit_status_after == next_status
    assert transition.state_version_after == 4


def test_required_visit_status_mismatch_fails_closed(
    state_machine: StateMachine,
):
    with pytest.raises(InvalidStateTransition) as exc_info:
        state_machine.resolve(
            snapshot=WorkflowSnapshot(
                inquiry_state="VISIT_SCHEDULED",
                state_version=5,
                visit_status="IN_PROGRESS",
            ),
            event_code="UPDATE_PREVISIT_REPORT",
        )

    assert exc_info.value.reason == "VISIT_STATE_MISMATCH"


def test_inquiry_state_rejects_visit_status_outside_state_contract(
    state_machine: StateMachine,
):
    with pytest.raises(InvalidStateTransition) as exc_info:
        state_machine.resolve(
            snapshot=WorkflowSnapshot(
                inquiry_state="COMPLETION_PENDING",
                state_version=8,
                visit_status="IN_PROGRESS",
            ),
            event_code="FINALIZE_INQUIRY",
        )

    assert exc_info.value.reason == "VISIT_STATUS_NOT_ALLOWED"


def test_snapshot_rejects_inconsistent_state_version():
    with pytest.raises(ValueError):
        WorkflowSnapshot(inquiry_state="DRAFT", state_version=None)

    with pytest.raises(ValueError):
        WorkflowSnapshot(inquiry_state=None, state_version=1)

    with pytest.raises(ValueError):
        WorkflowSnapshot(inquiry_state=42, state_version=1)

    with pytest.raises(ValueError):
        WorkflowSnapshot(inquiry_state="DRAFT", state_version=True)
