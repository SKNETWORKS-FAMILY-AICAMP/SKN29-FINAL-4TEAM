"""T-019 Care OpenAPI, schema, example, route contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import yaml
from django.urls import resolve


ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "contracts" / "api"
PATHS = API / "paths" / "care.yaml"
SCHEMAS = API / "components" / "schemas" / "care"
EXAMPLES = API / "examples" / "care"
SUBSCRIPTION_ID = "20000000-0000-4000-8000-000000000001"
CARE_RECORD_ID = "60000000-0000-4000-8000-000000000001"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_care_operations_are_confirmed_implemented_and_owner_scoped():
    paths = load_yaml(PATHS)
    collection = paths[
        "/me/subscriptions/{subscription_id}/care-records"
    ]
    detail = paths[
        "/me/subscriptions/{subscription_id}/care-records/{care_record_id}"
    ]["get"]

    expected = {
        collection["get"]["operationId"]: "listMyCareRecords",
        collection["post"]["operationId"]: "createMyCareRecord",
        detail["operationId"]: "getMyCareRecord",
    }
    assert expected == {
        "listMyCareRecords": "listMyCareRecords",
        "createMyCareRecord": "createMyCareRecord",
        "getMyCareRecord": "getMyCareRecord",
    }
    for operation in (collection["get"], collection["post"], detail):
        assert operation["x-contract-status"] == "CONFIRMED"
        assert operation["x-runtime-status"] == "IMPLEMENTED"
        assert operation["security"] == [{"BearerAuth": []}]
        assert operation["x-owner-scope"] == (
            "CUSTOMER_SELF_ACTIVE_SUPPORTED_SUBSCRIPTION"
        )

    refs = {
        item["$ref"]
        for item in collection["post"]["parameters"]
        if "$ref" in item
    }
    assert "../components/parameters/IdempotencyKey.yaml" in refs


def test_care_schemas_are_minimal_safe_and_closed():
    item = load_yaml(SCHEMAS / "CareHistoryItem.yaml")
    create = load_yaml(SCHEMAS / "CareHistoryCreateRequest.yaml")
    list_data = load_yaml(SCHEMAS / "CareHistoryListData.yaml")
    mutation = load_yaml(SCHEMAS / "CareHistoryMutationResult.yaml")

    assert item["additionalProperties"] is False
    assert set(item["required"]) == {
        "care_record_id",
        "subscription_id",
        "care_type_code",
        "status_code",
        "performed_on",
        "result_code",
        "source_code",
    }
    assert "summary" not in item["properties"]
    assert item["properties"]["status_code"]["const"] == "COMPLETED"
    assert create["additionalProperties"] is False
    assert create["properties"]["care_type_code"]["enum"] == [
        "FILTER_REPLACEMENT",
        "CLEANING",
    ]
    assert set(create["required"]) == {
        "care_type_code",
        "performed_on",
    }
    assert list_data["properties"]["size"]["maximum"] == 100
    assert mutation["allOf"][1]["properties"] == {
        "idempotent_replay": {"type": "boolean"}
    }


def test_care_examples_fix_visibility_idempotency_and_errors():
    listing = load_json(EXAMPLES / "list-success.json")
    detail = load_json(EXAMPLES / "detail-success.json")
    created = load_json(EXAMPLES / "create-success.json")
    replay = load_json(EXAMPLES / "create-replay.json")
    conflict = load_json(EXAMPLES / "idempotency-conflict.json")
    validation = load_json(EXAMPLES / "validation-error.json")

    assert listing["data"]["total"] == 1
    assert detail["data"]["status_code"] == "COMPLETED"
    assert created["data"]["idempotent_replay"] is False
    assert replay["data"]["idempotent_replay"] is True
    assert conflict["error"]["code"] == "DUPLICATE-EVENT-01"
    assert validation["error"]["code"] == "VALIDATION_ERROR"
    for payload in (listing, detail, created, replay):
        UUID(payload["metadata"]["correlation_id"])
        assert "summary" not in str(payload["data"])


def test_care_routes_resolve_to_customer_views():
    collection = resolve(
        f"/api/v1/me/subscriptions/{SUBSCRIPTION_ID}/care-records"
    )
    detail = resolve(
        "/api/v1/me/subscriptions/"
        f"{SUBSCRIPTION_ID}/care-records/{CARE_RECORD_ID}"
    )
    assert collection.url_name == "my-care-record-list-create"
    assert detail.url_name == "my-care-record-detail"
    assert callable(getattr(collection.func.view_class, "get"))
    assert callable(getattr(collection.func.view_class, "post"))
    assert callable(getattr(detail.func.view_class, "get"))
