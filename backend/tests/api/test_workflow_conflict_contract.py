"""Workflow Idempotency 요청 Parameter와 409 공개 계약 정합성."""

import json
from pathlib import Path

import yaml

from common.exceptions.error_codes import WORKFLOW_PUBLIC_CODE_BY_INTERNAL


BACKEND_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BACKEND_DIR.parent


def load_yaml(relative_path: str):
    return yaml.safe_load(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
    )


def load_json(relative_path: str):
    return json.loads(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
    )


def test_idempotency_key_is_registered_as_required_request_header():
    parameter = load_yaml(
        "contracts/api/components/parameters/IdempotencyKey.yaml"
    )
    openapi = load_yaml("contracts/api/openapi.yaml")

    assert parameter["name"] == "Idempotency-Key"
    assert parameter["in"] == "header"
    assert parameter["required"] is True
    assert parameter["schema"] == {
        "type": "string",
        "minLength": 1,
        "maxLength": 128,
    }
    assert openapi["components"]["parameters"]["Idempotency-Key"] == {
        "$ref": "./components/parameters/IdempotencyKey.yaml"
    }


def test_workflow_409_registry_and_runtime_mapping_are_aligned():
    registry = load_yaml("contracts/error-codes/error-codes.yaml")
    category = load_yaml(
        "contracts/error-codes/categories/workflow.yaml"
    )
    registry_errors = {
        item["code"]: item
        for item in registry["errors"]
        if item["category"] == "workflow"
    }
    category_errors = {
        item["code"]: item for item in category["errors"]
    }

    assert category_errors == registry_errors
    assert set(registry_errors) == {
        "STATE-CONFLICT-01",
        "DUPLICATE-EVENT-01",
        "CONSULTATION_RESULT_NOT_READY",
    }
    assert {
        item["http_status"] for item in registry_errors.values()
    } == {409}
    assert WORKFLOW_PUBLIC_CODE_BY_INTERNAL == {
        "STATE_VERSION_CONFLICT": "STATE-CONFLICT-01",
        "IDEMPOTENCY_KEY_REUSE_CONFLICT": "DUPLICATE-EVENT-01",
    }


def test_workflow_409_schema_and_examples_use_public_codes():
    openapi = load_yaml("contracts/api/openapi.yaml")
    response = load_yaml(
        "contracts/api/components/responses/WorkflowConflict.yaml"
    )
    schema = load_yaml(
        "contracts/api/components/schemas/workflow/"
        "WorkflowConflictResponse.yaml"
    )
    details = load_yaml(
        "contracts/api/components/schemas/workflow/"
        "WorkflowConflictDetails.yaml"
    )
    state_example = load_json(
        "contracts/api/examples/workflow/state-version-conflict.json"
    )
    duplicate_example = load_json(
        "contracts/api/examples/workflow/"
        "idempotency-key-reuse-conflict.json"
    )

    assert openapi["components"]["responses"]["WorkflowConflict"] == {
        "$ref": "./components/responses/WorkflowConflict.yaml"
    }
    assert response["content"]["application/json"]["schema"] == {
        "$ref": "../schemas/workflow/WorkflowConflictResponse.yaml"
    }
    assert set(schema["properties"]["error"]["properties"]["code"]["enum"]) == {
        "STATE-CONFLICT-01",
        "DUPLICATE-EVENT-01",
    }
    assert set(details["properties"]) == {
        "current_status",
        "current_state_version",
        "current_visit_status",
        "current_visit_state_version",
        "allowed_actions",
    }
    assert state_example["error"]["code"] == "STATE-CONFLICT-01"
    assert state_example["error"]["details"]["current_state_version"] == 1
    assert duplicate_example["error"]["code"] == "DUPLICATE-EVENT-01"
    assert duplicate_example["error"]["details"] == {}
