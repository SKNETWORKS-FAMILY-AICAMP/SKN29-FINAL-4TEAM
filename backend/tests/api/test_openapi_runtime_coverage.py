"""OpenAPI operation과 실제 Django Runtime route의 지원 상태를 검증한다."""

from pathlib import Path
from typing import Any

import yaml
from django.urls import resolve


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_PATH = REPOSITORY_ROOT / "contracts" / "api" / "openapi.yaml"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
INQUIRY_ID = "00000000-0000-4000-8000-000000000001"

EXPECTED_OPERATIONS = {
    ("/health", "get"): {
        "operation_id": "getProvisionalHealth",
        "contract_status": "IN_PROGRESS",
        "runtime_path": "/health",
        "url_name": "health",
        "view_name": "health",
    },
    ("/auth/demo-login", "post"): {
        "operation_id": "demoLogin",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/auth/demo-login",
        "url_name": "demo-login",
        "view_name": "DemoLoginView",
    },
    ("/auth/refresh", "post"): {
        "operation_id": "refreshAuthToken",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/auth/refresh",
        "url_name": "token-refresh",
        "view_name": "TokenRefreshView",
    },
    ("/auth/logout", "post"): {
        "operation_id": "logout",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/auth/logout",
        "url_name": "logout",
        "view_name": "LogoutView",
    },
    ("/me", "get"): {
        "operation_id": "getCurrentUser",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/me",
        "url_name": "me",
        "view_name": "MeView",
    },
    ("/inquiries", "post"): {
        "operation_id": "startInquiry",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/inquiries",
        "url_name": "inquiry-create",
        "view_name": "CreateInquiryView",
    },
    ("/inquiries/{id}/cancel", "post"): {
        "operation_id": "cancelInquiry",
        "contract_status": "CONFIRMED",
        "runtime_path": f"/api/v1/inquiries/{INQUIRY_ID}/cancel",
        "url_name": "inquiry-cancel",
        "view_name": "CancelInquiryView",
    },
    ("/inquiries/{id}/submit", "post"): {
        "operation_id": "submitSymptom",
        "contract_status": "CONFIRMED",
        "runtime_path": f"/api/v1/inquiries/{INQUIRY_ID}/submit",
        "url_name": "inquiry-submit",
        "view_name": "SubmitSymptomView",
    },
    ("/inquiries/{id}/questionnaire", "patch"): {
        "operation_id": "accumulateInquiryQuestionnaire",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/inquiries/{INQUIRY_ID}/questionnaire"
        ),
        "url_name": None,
        "view_name": None,
    },
    ("/inquiries/{id}/action-results", "post"): {
        "operation_id": "createInquiryActionResult",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/inquiries/{INQUIRY_ID}/action-results"
        ),
        "url_name": None,
        "view_name": None,
    },
}


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def resolve_json_pointer(document: Any, fragment: str) -> Any:
    current = document
    pointer = fragment.removeprefix("/")
    if not pointer:
        return current
    for token in pointer.split("/"):
        decoded = token.replace("~1", "/").replace("~0", "~")
        current = current[decoded]
    return current


def load_path_item(path_item: dict[str, Any]) -> dict[str, Any]:
    reference = path_item.get("$ref")
    if reference is None:
        return path_item

    external_path, _, fragment = reference.partition("#")
    target_path = (OPENAPI_PATH.parent / external_path).resolve()
    target_document = load_yaml(target_path)
    return resolve_json_pointer(target_document, fragment)


def collect_operations() -> dict[tuple[str, str], dict[str, Any]]:
    specification = load_yaml(OPENAPI_PATH)
    operations = {}
    for api_path, raw_path_item in specification["paths"].items():
        path_item = load_path_item(raw_path_item)
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                operations[(api_path, method)] = operation
    return operations


def runtime_view_name(match) -> str:
    view_class = getattr(match.func, "view_class", None)
    if view_class is not None:
        return view_class.__name__
    return match.func.__name__


def test_openapi_operation_inventory_is_exactly_ten():
    operations = collect_operations()

    assert set(operations) == set(EXPECTED_OPERATIONS)
    assert len(operations) == 10
    assert {
        operation["operationId"] for operation in operations.values()
    } == {
        expected["operation_id"]
        for expected in EXPECTED_OPERATIONS.values()
    }

    for key, expected in EXPECTED_OPERATIONS.items():
        operation = operations[key]
        assert operation["operationId"] == expected["operation_id"]
        assert operation["x-contract-status"] == (
            expected["contract_status"]
        )


def test_eight_operations_resolve_to_expected_runtime_views():
    implemented = [
        expected
        for expected in EXPECTED_OPERATIONS.values()
        if expected["url_name"] is not None
    ]

    assert len(implemented) == 8
    for expected in implemented:
        match = resolve(expected["runtime_path"])
        assert match.url_name == expected["url_name"]
        assert runtime_view_name(match) == expected["view_name"]


def test_two_openapi_only_operations_resolve_to_api_not_found():
    openapi_only = [
        expected
        for expected in EXPECTED_OPERATIONS.values()
        if expected["url_name"] is None
    ]

    assert len(openapi_only) == 2
    for expected in openapi_only:
        match = resolve(expected["runtime_path"])
        assert match.url_name == "api-not-found"
        assert runtime_view_name(match) == "api_not_found"
