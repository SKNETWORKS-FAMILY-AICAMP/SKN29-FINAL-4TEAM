"""T-018 write OpenAPI, schema, example, route, and error contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import yaml
from django.urls import resolve


ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "contracts" / "api"
PATHS = API / "paths" / "products.yaml"
SCHEMAS = API / "components" / "schemas" / "product"
EXAMPLES = API / "examples" / "subscriptions"
ERRORS = ROOT / "contracts" / "error-codes"
SUBSCRIPTION_ID = "20000000-0000-4000-8000-000000000001"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_write_operations_are_confirmed_implemented_and_idempotent():
    paths = load_yaml(PATHS)
    create = paths["/me/subscriptions"]["post"]
    update = paths["/me/subscriptions/{subscription_id}"]["patch"]

    assert create["operationId"] == "createMySubscription"
    assert update["operationId"] == "updateMySubscription"
    for operation in (create, update):
        assert operation["x-contract-status"] == "CONFIRMED"
        assert operation["x-runtime-status"] == "IMPLEMENTED"
        assert operation["security"] == [{"BearerAuth": []}]
        refs = {
            item["$ref"]
            for item in operation["parameters"]
            if "$ref" in item
        }
        assert "../components/parameters/IdempotencyKey.yaml" in refs
        assert set(operation["responses"]) >= {
            "200" if operation is update else "201",
            "401",
            "403",
            "409",
            "422",
            "500",
        }


def test_write_request_and_response_schemas_use_closed_allowlists():
    create = load_yaml(SCHEMAS / "SubscriptionCreateRequest.yaml")
    update = load_yaml(SCHEMAS / "SubscriptionUpdateRequest.yaml")
    result = load_yaml(SCHEMAS / "SubscriptionMutationResult.yaml")
    response = load_yaml(SCHEMAS / "SubscriptionMutationResponse.yaml")

    assert create["additionalProperties"] is False
    assert set(create["required"]) == {
        "model_code",
        "started_on",
        "management_type_code",
    }
    assert set(create["properties"]) == {
        "model_code",
        "started_on",
        "management_type_code",
        "last_care_on",
    }
    assert create["properties"]["model_code"]["enum"] == [
        "WPUJAC104DWH",
        "WPUIAC425SNW",
        "WPUIAC606SNW",
    ]
    assert update["additionalProperties"] is False
    assert set(update["properties"]) == {
        "started_on",
        "management_type_code",
        "last_care_on",
    }
    assert update["minProperties"] == 1
    assert result["allOf"][0]["$ref"] == "./SubscriptionDetail.yaml"
    assert result["allOf"][1]["properties"] == {
        "idempotent_replay": {"type": "boolean"}
    }
    assert response["allOf"][1]["properties"]["data"]["$ref"] == (
        "./SubscriptionMutationResult.yaml"
    )


def test_write_examples_and_product_errors_are_exact():
    create = load_json(EXAMPLES / "create-success.json")
    replay = load_json(EXAMPLES / "create-replay.json")
    update = load_json(EXAMPLES / "update-success.json")
    duplicate = load_json(EXAMPLES / "duplicate-active-error.json")
    unsupported = load_json(EXAMPLES / "unsupported-product-error.json")

    for payload in (create, replay, update):
        assert set(payload) == {"success", "data", "error", "metadata"}
        assert payload["success"] is True
        assert payload["error"] is None
        UUID(payload["data"]["subscription_id"])
        UUID(payload["metadata"]["correlation_id"])
    assert create["data"]["idempotent_replay"] is False
    assert replay["data"]["idempotent_replay"] is True
    assert update["data"]["management_type_code"] == "VISIT_CARE"
    assert duplicate["error"]["code"] == "SUBSCRIPTION_ALREADY_ACTIVE"
    assert unsupported["error"]["code"] == "PRODUCT_NOT_SUPPORTED"

    registry = {
        item["code"]: item
        for item in load_yaml(ERRORS / "error-codes.yaml")["errors"]
    }
    product_entries = load_yaml(ERRORS / "categories" / "product.yaml")[
        "errors"
    ]
    assert {item["code"] for item in product_entries} == {
        "PRODUCT_NOT_SUPPORTED",
        "SUBSCRIPTION_ALREADY_ACTIVE",
    }
    assert all(registry[item["code"]] == item for item in product_entries)


def test_write_routes_resolve_to_existing_owner_views():
    list_match = resolve("/api/v1/me/subscriptions")
    detail_match = resolve(
        f"/api/v1/me/subscriptions/{SUBSCRIPTION_ID}"
    )
    assert list_match.url_name == "my-subscription-list"
    assert detail_match.url_name == "my-subscription-detail"
    assert callable(getattr(list_match.func.view_class, "post"))
    assert callable(getattr(detail_match.func.view_class, "patch"))
