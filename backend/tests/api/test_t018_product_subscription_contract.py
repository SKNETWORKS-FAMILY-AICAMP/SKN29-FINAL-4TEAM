"""T-018 R1 제품·구독 목록·상세 기계 계약과 Runtime Gate를 검증한다."""

from datetime import date
import json
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

import yaml
from django.urls import resolve


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
API_DIR = REPOSITORY_ROOT / "contracts" / "api"
OPENAPI_PATH = API_DIR / "openapi.yaml"
PRODUCT_PATHS = API_DIR / "paths" / "products.yaml"
SCHEMA_DIR = API_DIR / "components" / "schemas" / "product"
EXAMPLE_DIR = API_DIR / "examples" / "subscriptions"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}

SUBSCRIPTION_ID = "20000000-0000-4000-8000-000000000001"
T018_OPERATIONS = {
    ("/me/subscriptions", "get"): "listMySubscriptions",
    (
        "/me/subscriptions/{subscription_id}",
        "get",
    ): "getMySubscription",
}
SENSITIVE_KEYS = {
    "id",
    "customer_id",
    "product_model_id_internal",
    "contract_no",
    "serial_no",
    "installation_address",
    "source_customer_product_public_id",
    "features",
    "customer_name",
    "customer_phone",
    "customer_address",
    "allowed_actions",
    "inquiry_eligible",
    "is_supported_mvp",
    "is_active",
}


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_json_pointer(document: Any, fragment: str) -> Any:
    current = document
    pointer = fragment.removeprefix("/")
    if not pointer:
        return current
    for token in pointer.split("/"):
        decoded = token.replace("~1", "/").replace("~0", "~")
        current = current[decoded]
    return current


def resolve_reference(source_path: Path, reference: str):
    external_path, _, fragment = reference.partition("#")
    target_path = (
        source_path
        if not external_path
        else (source_path.parent / external_path).resolve()
    )
    assert target_path.is_file(), (
        f"{source_path.relative_to(REPOSITORY_ROOT)}: "
        f"missing $ref target {reference}"
    )
    document = load_yaml(target_path)
    return target_path, fragment, resolve_json_pointer(document, fragment)


def load_path_item(raw_path_item: dict[str, Any]) -> dict[str, Any]:
    reference = raw_path_item.get("$ref")
    if reference is None:
        return raw_path_item
    _, _, path_item = resolve_reference(OPENAPI_PATH, reference)
    return path_item


def collect_operations() -> dict[tuple[str, str], dict[str, Any]]:
    specification = load_yaml(OPENAPI_PATH)
    operations = {}
    for api_path, raw_path_item in specification["paths"].items():
        path_item = load_path_item(raw_path_item)
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                operations[(api_path, method)] = operation
    return operations


def walk_references(
    source_path: Path,
    node: Any,
    visited: set[tuple[Path, str]],
) -> None:
    if isinstance(node, dict):
        reference = node.get("$ref")
        if reference is not None:
            target_path, fragment, target = resolve_reference(
                source_path, reference
            )
            identity = (target_path, fragment)
            if identity not in visited:
                visited.add(identity)
                walk_references(target_path, target, visited)
        for key, value in node.items():
            if key != "$ref":
                walk_references(source_path, value, visited)
    elif isinstance(node, list):
        for value in node:
            walk_references(source_path, value, visited)


def iter_mapping_keys(node: Any) -> Iterable[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from iter_mapping_keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_mapping_keys(value)


def iter_string_values(node: Any) -> Iterable[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from iter_string_values(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_string_values(value)


def assert_success_wrapper(payload: dict[str, Any]) -> None:
    assert set(payload) == {"success", "data", "error", "metadata"}
    assert payload["success"] is True
    assert payload["data"] is not None
    assert payload["error"] is None
    UUID(payload["metadata"]["correlation_id"])


def test_t018_pm_decision_and_contract_runtime_gates_are_exact():
    contract = load_yaml(PRODUCT_PATHS)
    policy = contract["x-t018-r1-policy"]

    assert policy == {
        "decision_id": "T018-D07",
        "decision_status": "FINAL_APPROVED",
        "customer_scope": "OWNER_ONLY",
        "product_model_codes": [
            "WPUJAC104DWH",
            "WPUIAC425SNW",
            "WPUIAC606SNW",
        ],
        "product_model_active_required": True,
        "product_model_supported_required": True,
        "subscription_status_scope": "ACTIVE_ONLY",
        "business_timezone": "Asia/Seoul",
        "last_care_on": {
            "eligible_status": "COMPLETED",
            "primary_date": "performed_on",
            "fallback_date": "completed_at_ASIA_SEOUL_DATE",
            "aggregate": "MAX_PER_SUBSCRIPTION",
            "empty_result": None,
        },
        "inquiry_eligibility_owner": "T022_GUARD",
        "allowed_actions_owner": "T023_STATE_MACHINE",
        "allowed_actions_in_t018": False,
        "hidden_fields": [
            "internal_database_ids",
            "contract_no",
            "serial_no",
            "installation_address",
            "source_customer_product_public_id",
            "product_features",
            "customer_personal_information",
        ],
        "runtime_implementation_start_allowed": True,
        "migration_change_allowed": False,
        "database_change_allowed": False,
    }


def test_t018_openapi_operations_are_confirmed_and_implemented():
    operations = collect_operations()

    for key, operation_id in T018_OPERATIONS.items():
        operation = operations[key]
        assert operation["operationId"] == operation_id
        assert operation["x-contract-status"] == "CONFIRMED"
        assert operation["x-runtime-status"] == "IMPLEMENTED"
        assert operation["security"] == [{"BearerAuth": []}]
        assert "requestBody" not in operation
        assert "409" not in operation["responses"]
        assert "Idempotency-Key" not in set(
            iter_string_values(operation)
        )
        assert "state_version" not in set(iter_mapping_keys(operation))

    list_operation = operations[("/me/subscriptions", "get")]
    detail_operation = operations[
        ("/me/subscriptions/{subscription_id}", "get")
    ]
    assert set(list_operation["responses"]) == {
        "200",
        "401",
        "403",
        "422",
        "500",
    }
    assert set(detail_operation["responses"]) == {
        "200",
        "401",
        "403",
        "404",
        "422",
        "500",
    }
    assert list_operation["x-unknown-query-policy"] == "REJECT_422"
    assert detail_operation["x-unknown-query-policy"] == "REJECT_422"


def test_t018_list_query_is_active_only_and_correlation_header_is_optional():
    operation = collect_operations()[("/me/subscriptions", "get")]
    refs = {
        item["$ref"]
        for item in operation["parameters"]
        if "$ref" in item
    }
    inline = [
        item for item in operation["parameters"] if "$ref" not in item
    ]

    assert refs == {
        "../components/parameters/Page.yaml",
        "../components/parameters/Size.yaml",
    }
    assert inline == [
        {
            "name": "X-Correlation-ID",
            "in": "header",
            "required": False,
            "description": (
                "요청·응답·구조화 로그를 연결하는 선택적 UUID. "
                "없으면 서버가 생성한다."
            ),
            "schema": {"type": "string", "format": "uuid"},
        }
    ]
    assert "status_code" not in {
        item.get("name") for item in operation["parameters"]
    }
    assert operation["x-subscription-filter"] == "status_code=ACTIVE"
    assert operation["x-product-filter"] == (
        "model_code IN (WPUJAC104DWH,WPUIAC425SNW,WPUIAC606SNW) "
        "AND product_model.is_active=true "
        "AND product_model.is_supported_mvp=true"
    )
    assert operation["x-sort"] == [
        "started_on DESC",
        "public_id ASC",
    ]


def test_t018_references_resolve_and_public_schemas_use_exact_allowlists():
    specification = load_yaml(OPENAPI_PATH)
    visited: set[tuple[Path, str]] = set()
    for api_path, _ in T018_OPERATIONS:
        walk_references(
            OPENAPI_PATH,
            specification["paths"][api_path],
            visited,
        )
    assert visited

    product = load_yaml(SCHEMA_DIR / "ProductSummary.yaml")
    summary = load_yaml(SCHEMA_DIR / "SubscriptionSummary.yaml")
    detail = load_yaml(SCHEMA_DIR / "SubscriptionDetail.yaml")
    list_data = load_yaml(SCHEMA_DIR / "SubscriptionListData.yaml")

    assert set(product["required"]) == {
        "product_model_id",
        "model_code",
        "model_name",
        "generation_code",
        "manufacturer",
    }
    assert set(product["properties"]) == set(product["required"])
    assert product["properties"]["model_code"]["enum"] == [
        "WPUJAC104DWH",
        "WPUIAC425SNW",
        "WPUIAC606SNW",
    ]

    common_fields = {
        "subscription_id",
        "status_code",
        "management_type_code",
        "started_on",
        "last_care_on",
        "next_care_on",
        "product",
    }
    assert set(summary["required"]) == common_fields
    assert set(summary["properties"]) == common_fields
    assert set(detail["required"]) == common_fields | {"ended_on"}
    assert set(detail["properties"]) == common_fields | {"ended_on"}
    assert summary["properties"]["status_code"]["const"] == "ACTIVE"
    assert detail["properties"]["status_code"]["const"] == "ACTIVE"
    assert set(list_data["properties"]) == {
        "items",
        "page",
        "size",
        "total",
    }

    public_contract = [product, summary, detail, list_data]
    public_keys = set(iter_mapping_keys(public_contract))
    assert public_keys.isdisjoint(SENSITIVE_KEYS)


def test_t018_examples_match_wrapper_scope_privacy_and_date_contract():
    list_payload = load_json(EXAMPLE_DIR / "list-active-success.json")
    empty_payload = load_json(EXAMPLE_DIR / "list-empty-success.json")
    detail_payload = load_json(EXAMPLE_DIR / "detail-active-success.json")
    error_payload = load_json(EXAMPLE_DIR / "query-validation-error.json")

    for payload in (list_payload, empty_payload, detail_payload):
        assert_success_wrapper(payload)

    item = list_payload["data"]["items"][0]
    detail = detail_payload["data"]
    assert set(item) == {
        "subscription_id",
        "status_code",
        "management_type_code",
        "started_on",
        "last_care_on",
        "next_care_on",
        "product",
    }
    assert set(detail) == set(item) | {"ended_on"}
    assert item["status_code"] == detail["status_code"] == "ACTIVE"
    assert item["product"]["model_code"] == "WPUJAC104DWH"
    assert detail["product"]["model_code"] == "WPUJAC104DWH"
    UUID(item["subscription_id"])
    UUID(item["product"]["product_model_id"])
    for field in ("started_on", "last_care_on", "next_care_on"):
        if item[field] is not None:
            date.fromisoformat(item[field])
    assert detail["ended_on"] is None

    assert empty_payload["data"] == {
        "items": [],
        "page": 1,
        "size": 20,
        "total": 0,
    }
    assert error_payload["success"] is False
    assert error_payload["data"] is None
    assert error_payload["error"]["code"] == "VALIDATION_ERROR"
    UUID(error_payload["metadata"]["correlation_id"])

    example_keys = set(
        iter_mapping_keys(
            [list_payload, empty_payload, detail_payload, error_payload]
        )
    )
    assert example_keys.isdisjoint(SENSITIVE_KEYS)


def test_t018_routes_resolve_to_owner_only_runtime_views():
    runtime_paths = {
        "/api/v1/me/subscriptions": "my-subscription-list",
        (
            f"/api/v1/me/subscriptions/{SUBSCRIPTION_ID}"
        ): "my-subscription-detail",
    }
    for runtime_path, expected_name in runtime_paths.items():
        match = resolve(runtime_path)
        assert match.url_name == expected_name
        assert match.func.view_class.__module__ == (
            "apps.subscriptions.api.views"
        )

    api_urls = (
        REPOSITORY_ROOT / "backend" / "config" / "api_urls.py"
    ).read_text(encoding="utf-8")
    assert "apps.subscriptions.api.urls" in api_urls


def test_t018_runtime_has_no_migration_or_database_contract_side_effects():
    contract = load_yaml(PRODUCT_PATHS)
    policy = contract["x-t018-r1-policy"]
    assert policy["runtime_implementation_start_allowed"] is True
    assert policy["migration_change_allowed"] is False
    assert policy["database_change_allowed"] is False

    runtime_sources = {
        "backend/apps/subscriptions/repositories/subscription_repository.py": (
            "class SubscriptionRepository"
        ),
        "backend/apps/subscriptions/services/subscription_service.py": (
            "class SubscriptionService"
        ),
        "backend/apps/subscriptions/permissions.py": "class IsCustomer",
        "backend/apps/subscriptions/api/serializers.py": (
            "class SubscriptionListQuerySerializer"
        ),
        "backend/apps/subscriptions/api/views.py": (
            "class MySubscriptionListView"
        ),
        "backend/apps/subscriptions/api/urls.py": "urlpatterns =",
    }
    for relative_path, required_fragment in runtime_sources.items():
        source = (REPOSITORY_ROOT / relative_path).read_text(
            encoding="utf-8"
        )
        assert source.count("\n") > 10
        assert required_fragment in source
