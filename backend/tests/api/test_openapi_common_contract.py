"""확정된 공통 API Wrapper와 OpenAPI Schema의 정합성을 검증한다."""

from pathlib import Path

import yaml

from common.api.pagination import (
    MAX_PAGE_SIZE,
    MIN_PAGE,
    MIN_PAGE_SIZE,
    MIN_TOTAL,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_DIR = REPOSITORY_ROOT / "contracts" / "api"
COMMON_SCHEMA_DIR = OPENAPI_DIR / "components" / "schemas" / "common"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_openapi_root_references_confirmed_common_schemas():
    specification = load_yaml(OPENAPI_DIR / "openapi.yaml")

    assert specification["components"]["schemas"] == {
        "ApiResponse": {
            "$ref": "./components/schemas/common/ApiResponse.yaml"
        },
        "ApiError": {
            "$ref": "./components/schemas/common/ApiError.yaml"
        },
        "PageInfo": {
            "$ref": "./components/schemas/common/PageInfo.yaml"
        },
        "TraceContext": {
            "$ref": "./components/schemas/common/TraceContext.yaml"
        },
    }
    trace_header = specification["components"]["headers"][
        "X-Correlation-ID"
    ]
    assert trace_header == {
        "$ref": "./components/headers/CorrelationId.yaml"
    }
    header_schema = load_yaml(
        OPENAPI_DIR / "components" / "headers" / "CorrelationId.yaml"
    )
    assert header_schema["schema"] == {
        "type": "string",
        "format": "uuid",
    }


def test_openapi_records_provisional_health_without_freezing_open_contract():
    specification = load_yaml(OPENAPI_DIR / "openapi.yaml")
    path_item = specification["paths"]["/health"]
    operation = path_item["get"]
    response = operation["responses"]["200"]
    http_methods = {
        method
        for method in path_item
        if method
        in {
            "get",
            "put",
            "post",
            "delete",
            "options",
            "head",
            "patch",
            "trace",
        }
    }

    assert http_methods == {"get"}
    assert operation["x-contract-status"] == "IN_PROGRESS"
    assert operation["servers"] == [
        {
            "url": "/",
            "description": "/api/v1 외부의 provisional health 경로",
        }
    ]
    assert set(operation["responses"]) == {"200"}
    assert "content" not in response
    assert response["headers"]["X-Correlation-ID"] == {
        "$ref": "#/components/headers/X-Correlation-ID"
    }
    assert "HealthDTO" in operation["description"]
    assert "Wrapper" in operation["description"]
    assert "correlation" in operation["description"].lower()
    assert "OPEN" in operation["description"]


def test_common_response_schema_matches_runtime_wrapper():
    response_schema = load_yaml(COMMON_SCHEMA_DIR / "ApiResponse.yaml")
    error_schema = load_yaml(COMMON_SCHEMA_DIR / "ApiError.yaml")
    page_schema = load_yaml(COMMON_SCHEMA_DIR / "PageInfo.yaml")

    assert set(response_schema["required"]) == {
        "success",
        "data",
        "error",
        "metadata",
    }
    assert set(response_schema["properties"]) == {
        "success",
        "data",
        "error",
        "metadata",
    }
    trace_schema = load_yaml(COMMON_SCHEMA_DIR / "TraceContext.yaml")
    assert trace_schema["required"] == ["correlation_id"]
    assert trace_schema["properties"]["correlation_id"] == {
        "type": "string",
        "format": "uuid",
        "description": "요청·응답·구조화 로그를 연결하는 추적 ID",
    }
    assert set(error_schema["required"]) == {"code", "message", "details"}
    assert set(error_schema["properties"]) == {
        "code",
        "message",
        "details",
    }
    assert set(page_schema["required"]) == {"page", "size", "total"}
    assert set(page_schema["properties"]) == {"page", "size", "total"}
    assert page_schema["properties"]["page"]["minimum"] == MIN_PAGE
    assert page_schema["properties"]["size"]["minimum"] == MIN_PAGE_SIZE
    assert page_schema["properties"]["size"]["maximum"] == MAX_PAGE_SIZE
    assert page_schema["properties"]["total"]["minimum"] == MIN_TOTAL


def test_common_error_responses_expose_trace_header():
    response_dir = OPENAPI_DIR / "components" / "responses"

    for name in (
        "BadRequest.yaml",
        "Conflict.yaml",
        "Forbidden.yaml",
        "InternalServerError.yaml",
        "NotFound.yaml",
        "Unauthorized.yaml",
        "UnprocessableEntity.yaml",
    ):
        response = load_yaml(response_dir / name)
        assert response["headers"]["X-Correlation-ID"] == {
            "$ref": "../headers/CorrelationId.yaml"
        }
