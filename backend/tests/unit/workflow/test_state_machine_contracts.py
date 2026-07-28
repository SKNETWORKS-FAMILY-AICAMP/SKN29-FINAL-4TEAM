from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest

from apps.workflow.contracts import state_machine_loader as loader_module
from apps.workflow.contracts import (
    StateMachineContractLoadError,
    StateMachineContractValidationError,
    collect_contract_errors,
    load_contract_documents,
    load_state_machine_contract,
    load_yaml_mapping,
    validate_contract_documents,
)


FIXTURE_DIR = Path(__file__).with_name("fixtures")
VALID_CONTRACT_DIR = FIXTURE_DIR / "valid-state-machine"


def valid_documents():
    return load_contract_documents(VALID_CONTRACT_DIR)


def test_load_and_validate_rich_contract_directory():
    documents = valid_documents()

    loaded = load_state_machine_contract(VALID_CONTRACT_DIR)

    assert loaded == documents
    assert collect_contract_errors(loaded) == ()


@pytest.mark.parametrize(
    "contents",
    (
        "",
        "[]\n",
        "{}\n",
        "states: [STATE_A\n",
        "states:\n  - STATE_A\nstates:\n  - STATE_B\n",
    ),
)
def test_yaml_loader_fails_closed_for_invalid_documents(contents):
    path = Mock()
    path.read_text.return_value = contents

    with pytest.raises(StateMachineContractLoadError):
        load_yaml_mapping(path)


def test_contract_loader_requires_directory_and_every_file(monkeypatch):
    missing_directory = FIXTURE_DIR / "__missing__"
    with pytest.raises(StateMachineContractLoadError):
        load_contract_documents(missing_directory)

    monkeypatch.setattr(
        loader_module,
        "CONTRACT_FILES",
        {
            **loader_module.CONTRACT_FILES,
            "missing": "__missing__.yaml",
        },
    )
    with pytest.raises(StateMachineContractLoadError):
        load_contract_documents(VALID_CONTRACT_DIR)


def test_duplicate_rich_schema_identifiers_are_rejected():
    documents = valid_documents()
    documents["states"]["states"].append(
        deepcopy(documents["states"]["states"][0])
    )
    documents["events"]["events"].append(
        deepcopy(documents["events"]["events"][0])
    )
    documents["transitions"]["transitions"].append(
        deepcopy(documents["transitions"]["transitions"][0])
    )
    documents["guards"]["guards"].append(
        deepcopy(documents["guards"]["guards"][0])
    )
    documents["allowed_actions"]["action_catalog"].append(
        deepcopy(documents["allowed_actions"]["action_catalog"][0])
    )
    documents["role_permissions"]["roles"].append(
        deepcopy(documents["role_permissions"]["roles"][0])
    )

    errors = collect_contract_errors(documents)

    for identifier_path in (
        "states.states: code 'STATE_A'가 중복",
        "events.events: code 'EVENT_A'가 중복",
        "transitions.transitions: id 'TR-001'가 중복",
        "guards.guards: id 'G-STATE-VERSION'가 중복",
        "allowed_actions.action_catalog: code 'EVENT_A'가 중복",
        "role_permissions.roles: code 'CUSTOMER'가 중복",
    ):
        assert any(identifier_path in error for error in errors)


def test_unknown_transition_and_guard_references_are_rejected():
    documents = valid_documents()
    transition = documents["transitions"]["transitions"][0]
    transition["event"] = "UNKNOWN_EVENT"
    transition["from_inquiry_state"] = "UNKNOWN_STATE"
    transition["to_inquiry_state"] = "UNKNOWN_TARGET"
    transition["guard_refs"] = ["UNKNOWN_GUARD"]

    errors = collect_contract_errors(documents)

    assert any("등록되지 않은 event 'UNKNOWN_EVENT'" in error for error in errors)
    assert any("등록되지 않은 state 'UNKNOWN_STATE'" in error for error in errors)
    assert any("등록되지 않은 state 'UNKNOWN_TARGET'" in error for error in errors)
    assert any("등록되지 않은 guard 'UNKNOWN_GUARD'" in error for error in errors)


def test_idempotency_required_event_requires_idempotency_guard():
    documents = valid_documents()
    transition = documents["transitions"]["transitions"][0]
    transition["guard_refs"].remove("G-IDEMPOTENCY-KEY")

    errors = collect_contract_errors(documents)

    assert any(
        (
            "requires_idempotency_key=true인 이벤트는 "
            "G-IDEMPOTENCY-KEY를 포함해야 합니다."
        )
        in error
        for error in errors
    )


def test_transition_uniqueness_includes_visit_conditions():
    documents = valid_documents()
    second = deepcopy(documents["transitions"]["transitions"][0])
    second["id"] = "TR-002"
    second["visit"] = {
        "mode": "PRESERVE_REQUIRE_STATUS",
        "required_status": "READY",
    }
    documents["transitions"]["transitions"].append(second)

    assert not any(
        "Visit 조건 조합이 중복" in error
        for error in collect_contract_errors(documents)
    )

    duplicate = deepcopy(second)
    duplicate["id"] = "TR-003"
    documents["transitions"]["transitions"].append(duplicate)

    assert any(
        "Visit 조건 조합이 중복" in error
        for error in collect_contract_errors(documents)
    )


def test_state_and_visit_changes_require_history():
    documents = valid_documents()
    transition = documents["transitions"]["transitions"][0]
    transition["history"]["record_inquiry_state_history"] = False
    transition["visit"] = {
        "mode": "PRESERVE_REQUIRE_STATUS",
        "required_status": "READY",
    }

    errors = collect_contract_errors(documents)

    assert any(
        "record_inquiry_state_history" in error for error in errors
    )
    assert not any("record_visit_state_history" in error for error in errors)

    transition["visit"] = {
        "mode": "CREATE",
        "from_status": None,
        "to_status": "READY",
    }
    documents["transitions"]["rule_semantics"]["visit_modes"]["CREATE"] = (
        "Create a visit."
    )

    errors = collect_contract_errors(documents)

    assert any("record_visit_state_history" in error for error in errors)


def test_terminal_state_cannot_have_an_outgoing_transition():
    documents = valid_documents()
    documents["transitions"]["transitions"][0][
        "from_inquiry_state"
    ] = "STATE_B"
    documents["allowed_actions"]["state_role_actions"]["STATE_A"] = {}

    errors = collect_contract_errors(documents)

    assert any("terminal state 'STATE_B'" in error for error in errors)


def test_guard_accepts_list_or_combiner_mapping_and_rejects_empty_items():
    documents = valid_documents()
    guard = documents["guards"]["guards"][0]
    guard["conditions"] = {
        "combiner": "ANY",
        "items": ["condition_a", "condition_b"],
    }

    assert collect_contract_errors(documents) == ()

    guard["conditions"]["items"] = []
    errors = collect_contract_errors(documents)

    assert any("conditions.items: 하나 이상의 값" in error for error in errors)


def test_allowed_action_cross_references_are_fail_closed():
    documents = valid_documents()
    action = documents["allowed_actions"]["action_catalog"][0]
    action["operation_id"] = "wrongOperation"
    state_action = documents["allowed_actions"]["state_role_actions"][
        "STATE_A"
    ]["CUSTOMER"][0]
    state_action["transition_rule_ids"] = ["UNKNOWN_RULE"]

    errors = collect_contract_errors(documents)

    assert any("operation_id" in error for error in errors)
    assert any("등록되지 않은 transition rule" in error for error in errors)


def test_role_permissions_must_match_event_actor_roles_both_ways():
    documents = valid_documents()
    documents["role_permissions"]["roles"][0]["allowed_events"] = []

    errors = collect_contract_errors(documents)

    assert any(
        "event 'EVENT_A'의 actor role 'CUSTOMER'" in error
        for error in errors
    )


def test_terminal_actions_and_internal_event_mapping_are_validated():
    documents = valid_documents()
    documents["allowed_actions"]["state_role_actions"]["STATE_B"] = {
        "CUSTOMER": [
            {
                "action": "EVENT_A",
                "transition_rule_ids": ["TR-001"],
            }
        ]
    }
    documents["allowed_actions"]["internal_events_by_state"]["STATE_A"] = [
        "EVENT_A"
    ]

    errors = collect_contract_errors(documents)

    assert any("terminal state의 외부 행동" in error for error in errors)
    assert any("'EVENT_A'는 SYSTEM_EVENT가 아닙니다" in error for error in errors)


@pytest.mark.parametrize(
    ("document_name", "key"),
    (
        ("states", "states"),
        ("events", "events"),
        ("transitions", "transitions"),
        ("guards", "guards"),
        ("allowed_actions", "action_catalog"),
        ("role_permissions", "roles"),
    ),
)
def test_empty_runtime_contract_sections_fail_closed(document_name, key):
    documents = valid_documents()
    documents[document_name][key] = []

    with pytest.raises(StateMachineContractValidationError):
        validate_contract_documents(documents)


def test_current_repository_contract_is_valid():
    repository_root = Path(__file__).resolve().parents[4]
    documents = load_state_machine_contract(
        repository_root / "contracts" / "state-machine"
    )

    assert collect_contract_errors(documents) == ()
    assert len(documents["states"]["states"]) == 13
    assert len(documents["events"]["events"]) == 30
    assert len(documents["transitions"]["transitions"]) == 34
    assert len(documents["guards"]["guards"]) == 39
    assert len(documents["allowed_actions"]["action_catalog"]) == 23
    assert len(documents["role_permissions"]["roles"]) == 5


def test_validation_does_not_mutate_input():
    documents = valid_documents()
    before = deepcopy(documents)

    validate_contract_documents(documents)

    assert documents == before
