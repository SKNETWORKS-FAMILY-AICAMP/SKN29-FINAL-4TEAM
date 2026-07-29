"""CANCEL_INQUIRY 최소 Action API와 PM State Machine 계약 정합성."""

from pathlib import Path
from typing import Any

import yaml


BACKEND_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BACKEND_DIR.parent
API_DIR = REPOSITORY_ROOT / "contracts" / "api"
STATE_MACHINE_DIR = REPOSITORY_ROOT / "contracts" / "state-machine"
WORKFLOW_PATH = API_DIR / "paths" / "workflow.yaml"
OPENAPI_PATH = API_DIR / "openapi.yaml"
CANCEL_PATH = "/inquiries/{id}/cancel"


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def iter_values(node: Any, key: str):
    if isinstance(node, dict):
        for current_key, value in node.items():
            if current_key == key:
                yield value
            yield from iter_values(value, key)
    elif isinstance(node, list):
        for value in node:
            yield from iter_values(value, key)


def resolve_json_pointer(document: Any, fragment: str) -> Any:
    current = document
    pointer = fragment.removeprefix("/")
    if not pointer:
        return current
    for token in pointer.split("/"):
        decoded = token.replace("~1", "/").replace("~0", "~")
        current = current[decoded]
    return current


def assert_external_references_exist(
    path: Path,
    *,
    visited: set[Path] | None = None,
) -> None:
    resolved_path = path.resolve()
    visited = set() if visited is None else visited
    if resolved_path in visited:
        return
    visited.add(resolved_path)

    document = load_yaml(resolved_path)
    for reference in iter_values(document, "$ref"):
        assert isinstance(reference, str)
        external_path, separator, fragment = reference.partition("#")
        if not external_path:
            if separator:
                resolve_json_pointer(document, fragment)
            continue

        target = (resolved_path.parent / external_path).resolve()
        assert target.is_file(), f"없는 OpenAPI 참조: {resolved_path} -> {target}"
        target_document = load_yaml(target)
        if separator:
            resolve_json_pointer(target_document, fragment)
        assert_external_references_exist(target, visited=visited)

    for external_value in iter_values(document, "externalValue"):
        assert isinstance(external_value, str)
        target = (resolved_path.parent / external_value).resolve()
        assert target.is_file(), (
            f"없는 OpenAPI example 참조: {resolved_path} -> {target}"
        )


def test_openapi_registers_cancel_inquiry_action():
    openapi = load_yaml(OPENAPI_PATH)
    workflow = load_yaml(WORKFLOW_PATH)

    assert openapi["paths"][CANCEL_PATH] == {
        "$ref": "./paths/workflow.yaml#/~1inquiries~1{id}~1cancel"
    }
    assert CANCEL_PATH in workflow

    path_item = workflow[CANCEL_PATH]
    path_parameter = path_item["parameters"][0]
    assert path_parameter["name"] == "id"
    assert path_parameter["in"] == "path"
    assert path_parameter["required"] is True
    assert path_parameter["schema"] == {
        "type": "string",
        "format": "uuid",
    }


def test_cancel_inquiry_requires_auth_idempotency_and_expected_responses():
    operation = load_yaml(WORKFLOW_PATH)[CANCEL_PATH]["post"]

    assert operation["operationId"] == "cancelInquiry"
    assert operation["x-contract-status"] == "CONFIRMED"
    assert operation["security"] == [{"BearerAuth": []}]
    assert operation["parameters"] == [
        {
            "$ref": "../components/parameters/IdempotencyKey.yaml",
        }
    ]
    assert operation["requestBody"]["required"] is True
    assert operation["requestBody"]["content"]["application/json"][
        "schema"
    ] == {
        "$ref": (
            "../components/schemas/workflow/"
            "CancelInquiryRequest.yaml"
        )
    }
    assert set(operation["responses"]) == {
        "200",
        "400",
        "401",
        "403",
        "404",
        "409",
        "422",
    }
    assert operation["responses"]["409"] == {
        "$ref": "../components/responses/WorkflowConflict.yaml"
    }


def test_cancel_request_and_success_result_are_minimal_and_explicit():
    request_schema = load_yaml(
        API_DIR
        / "components"
        / "schemas"
        / "workflow"
        / "CancelInquiryRequest.yaml"
    )
    result_schema = load_yaml(
        API_DIR
        / "components"
        / "schemas"
        / "workflow"
        / "CancelInquiryResult.yaml"
    )
    operation = load_yaml(WORKFLOW_PATH)[CANCEL_PATH]["post"]
    success_schema = operation["responses"]["200"]["content"][
        "application/json"
    ]["schema"]

    assert request_schema["additionalProperties"] is False
    assert set(request_schema["required"]) == {
        "state_version",
        "reason_code",
    }
    assert request_schema["properties"]["state_version"] == {
        "type": "integer",
        "minimum": 1,
        "description": "클라이언트가 마지막으로 확인한 문의 상태 버전",
    }
    assert request_schema["properties"]["reason_detail"]["maxLength"] == 500

    assert result_schema["additionalProperties"] is False
    assert set(result_schema["required"]) == {
        "inquiry_id",
        "state",
        "state_version",
        "idempotent_replay",
    }
    assert result_schema["properties"]["inquiry_id"]["format"] == "uuid"
    assert result_schema["properties"]["state"]["const"] == "CANCELLED"
    assert result_schema["properties"]["state_version"]["minimum"] == 2
    assert (
        result_schema["properties"]["idempotent_replay"]["type"]
        == "boolean"
    )
    assert success_schema["allOf"][1]["properties"]["data"] == {
        "$ref": (
            "../components/schemas/workflow/"
            "CancelInquiryResult.yaml"
        )
    }


def test_cancel_action_matches_read_only_pm_state_machine_contract():
    event_contract = load_yaml(STATE_MACHINE_DIR / "inquiry-events.yaml")
    transition_contract = load_yaml(
        STATE_MACHINE_DIR / "transition-rules.yaml"
    )
    action_contract = load_yaml(STATE_MACHINE_DIR / "allowed-actions.yaml")
    state_contract = load_yaml(STATE_MACHINE_DIR / "inquiry-states.yaml")
    operation = load_yaml(WORKFLOW_PATH)[CANCEL_PATH]["post"]

    event = next(
        item
        for item in event_contract["events"]
        if item["code"] == "CANCEL_INQUIRY"
    )
    transition = next(
        item
        for item in transition_contract["transitions"]
        if item["id"] == "TR-INQ-004"
    )
    draft_customer_actions = action_contract["state_role_actions"][
        "DRAFT"
    ]["CUSTOMER"]
    cancel_action = next(
        item
        for item in draft_customer_actions
        if item["action"] == "CANCEL_INQUIRY"
    )
    cancelled_state = next(
        item
        for item in state_contract["states"]
        if item["code"] == "CANCELLED"
    )

    assert "CUSTOMER" in event["actor_roles"]
    assert event["requires_idempotency_key"] is True
    assert event["requires_state_version"] is True
    assert event["external_action"] == {
        "exposed": True,
        "operation_id": "cancelInquiry",
    }
    assert transition["event"] == "CANCEL_INQUIRY"
    assert transition["from_inquiry_state"] == "DRAFT"
    assert transition["to_inquiry_state"] == "CANCELLED"
    assert {
        "G-STATE-VERSION",
        "G-IDEMPOTENCY-KEY",
        "G-CANCELLATION-REASON",
    }.issubset(transition["guard_refs"])
    assert cancel_action["transition_rule_ids"] == ["TR-INQ-004"]
    assert cancelled_state["terminal"] is True
    assert operation["x-state-machine"] == {
        "event": "CANCEL_INQUIRY",
        "transition_rule": "TR-INQ-004",
        "from_state": "DRAFT",
        "to_state": "CANCELLED",
        "actor_role": "CUSTOMER",
    }


def test_cancel_contract_external_references_are_resolvable():
    assert_external_references_exist(WORKFLOW_PATH)
