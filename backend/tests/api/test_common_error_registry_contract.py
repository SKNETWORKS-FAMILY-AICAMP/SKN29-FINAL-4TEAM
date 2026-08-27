"""Runtime 공통 오류 코드와 Registry의 가산 정합성을 검증한다."""

from pathlib import Path

import yaml
from rest_framework.exceptions import (
    APIException,
    MethodNotAllowed,
    NotFound,
    ParseError,
    ValidationError,
)

from common.exceptions.error_codes import (
    AI_GUIDANCE_NOT_READY,
    AUTH_REQUIRED,
    CONSULTATION_RESULT_NOT_READY,
    DUPLICATE_EVENT,
    FORBIDDEN,
    INTERNAL_ERROR,
    INVALID_REQUEST,
    RESOURCE_NOT_FOUND,
    STATE_CONFLICT,
    VALIDATION_ERROR,
)
from common.exceptions.handler import ERROR_BY_STATUS, api_exception_handler


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_DIR = REPOSITORY_ROOT / "contracts" / "error-codes"


class ServiceUnavailable(APIException):
    status_code = 503
    default_code = "service_unavailable"


def api_error_with_status(status_code: int) -> APIException:
    exception = APIException("hidden")
    exception.status_code = status_code
    return exception


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def registry_by_code():
    registry = load_yaml(REGISTRY_DIR / "error-codes.yaml")
    codes = [item["code"] for item in registry["errors"]]
    assert len(codes) == len(set(codes))
    return {item["code"]: item for item in registry["errors"]}


def test_all_runtime_common_codes_exist_in_registry():
    registered = registry_by_code()

    assert {
        INVALID_REQUEST,
        AUTH_REQUIRED,
        FORBIDDEN,
        RESOURCE_NOT_FOUND,
        VALIDATION_ERROR,
        INTERNAL_ERROR,
        STATE_CONFLICT,
        DUPLICATE_EVENT,
        AI_GUIDANCE_NOT_READY,
        CONSULTATION_RESULT_NOT_READY,
    } <= set(registered)


def test_new_runtime_common_error_metadata_is_exact():
    registered = registry_by_code()

    assert registered[INVALID_REQUEST] == {
        "code": INVALID_REQUEST,
        "category": "validation",
        "http_status": 400,
        "retryable": False,
        "user_message": "요청 형식을 확인해 주세요.",
        "recommended_action": "CORRECT_REQUEST",
    }
    assert registered[RESOURCE_NOT_FOUND] == {
        "code": RESOURCE_NOT_FOUND,
        "category": "persistence",
        "http_status": 404,
        "retryable": False,
        "user_message": "요청한 대상을 찾을 수 없습니다.",
        "recommended_action": "RETURN_TO_LIST",
    }
    assert registered[VALIDATION_ERROR] == {
        "code": VALIDATION_ERROR,
        "category": "validation",
        "http_status": 422,
        "retryable": False,
        "user_message": "입력값을 확인해 주세요.",
        "recommended_action": "CORRECT_INPUT",
    }
    assert registered[INTERNAL_ERROR] == {
        "code": INTERNAL_ERROR,
        "category": "system",
        "http_status": 500,
        "retryable": False,
        "user_message": "요청 처리 중 오류가 발생했습니다.",
        "recommended_action": "REPORT_WITH_CORRELATION_ID",
    }
    assert registered[AI_GUIDANCE_NOT_READY] == {
        "code": AI_GUIDANCE_NOT_READY,
        "category": "ai",
        "http_status": 409,
        "retryable": True,
        "user_message": (
            "AI 안내가 아직 준비되지 않았습니다. 상담 검토가 필요합니다."
        ),
        "recommended_action": "REFRESH_OR_REQUEST_CONSULTATION",
    }
    assert registered[CONSULTATION_RESULT_NOT_READY] == {
        "code": CONSULTATION_RESULT_NOT_READY,
        "category": "workflow",
        "http_status": 409,
        "retryable": True,
        "user_message": "상담 처리 결과가 아직 준비되지 않았습니다.",
        "recommended_action": "REFRESH_RESULT",
    }


def test_runtime_http_mapping_records_handler_precedence():
    registry = load_yaml(REGISTRY_DIR / "error-codes.yaml")

    assert registry["runtime_http_mapping"] == {
        "precedence": [
            "backend_error_passthrough",
            "exception_overrides",
            "server_error_family_fallback",
            "status_overrides",
            "client_error_family_fallback",
            "unhandled_exception",
        ],
        "exception_overrides": [
            {
                "exception": "rest_framework.exceptions.ValidationError",
                "code": VALIDATION_ERROR,
                "http_status": 422,
            }
        ],
        "status_overrides": {
            400: INVALID_REQUEST,
            401: AUTH_REQUIRED,
            403: FORBIDDEN,
            404: RESOURCE_NOT_FOUND,
        },
        "family_fallbacks": [
            {
                "minimum": 500,
                "maximum": 599,
                "code": INTERNAL_ERROR,
            },
            {
                "minimum": 400,
                "maximum": 499,
                "code": INVALID_REQUEST,
            },
        ],
        "unhandled_exception": {
            "code": INTERNAL_ERROR,
            "http_status": 500,
        },
    }


def test_new_category_files_match_top_level_registry():
    registered = registry_by_code()
    expected_by_category = {
        "validation": {INVALID_REQUEST, VALIDATION_ERROR},
        "persistence": {RESOURCE_NOT_FOUND},
        "system": {INTERNAL_ERROR},
    }

    for category, expected_codes in expected_by_category.items():
        category_data = load_yaml(
            REGISTRY_DIR / "categories" / f"{category}.yaml"
        )
        category_entries = {
            item["code"]: item for item in category_data["errors"]
        }
        assert category_data["category"] == category
        assert set(category_entries) == expected_codes
        assert category_entries == {
            code: registered[code] for code in expected_codes
        }


def test_registry_covers_observed_runtime_http_statuses():
    cases = (
        (ParseError(), INVALID_REQUEST, 400),
        (MethodNotAllowed("get"), INVALID_REQUEST, 405),
        (api_error_with_status(415), INVALID_REQUEST, 415),
        (api_error_with_status(422), INVALID_REQUEST, 422),
        (api_error_with_status(429), INVALID_REQUEST, 429),
        (NotFound(), RESOURCE_NOT_FOUND, 404),
        (ValidationError({"field": ["required"]}), VALIDATION_ERROR, 422),
        (RuntimeError("hidden"), INTERNAL_ERROR, 500),
        (api_error_with_status(502), INTERNAL_ERROR, 502),
        (ServiceUnavailable("hidden"), INTERNAL_ERROR, 503),
    )

    for exception, expected_code, expected_status in cases:
        response = api_exception_handler(exception, {})

        assert response.status_code == expected_status
        assert response.data["error"]["code"] == expected_code


def test_registry_mapping_covers_entire_drf_error_status_range():
    mapping = load_yaml(REGISTRY_DIR / "error-codes.yaml")[
        "runtime_http_mapping"
    ]
    exact_codes = mapping["status_overrides"]
    server_range, client_range = mapping["family_fallbacks"]

    assert {
        status_code: code
        for status_code, (code, _message) in ERROR_BY_STATUS.items()
    } == exact_codes

    for status_code in range(400, 600):
        if (
            server_range["minimum"]
            <= status_code
            <= server_range["maximum"]
        ):
            expected_code = server_range["code"]
        elif status_code in exact_codes:
            expected_code = exact_codes[status_code]
        elif (
            client_range["minimum"]
            <= status_code
            <= client_range["maximum"]
        ):
            expected_code = client_range["code"]
        else:
            raise AssertionError(f"unmapped status: {status_code}")

        response = api_exception_handler(
            api_error_with_status(status_code),
            {},
        )
        assert response.status_code == status_code
        assert response.data["error"]["code"] == expected_code


def test_preexisting_auth_permission_and_workflow_entries_are_unchanged():
    registered = registry_by_code()

    assert registered[AUTH_REQUIRED]["http_status"] == 401
    assert registered[FORBIDDEN]["http_status"] == 403
    assert registered[STATE_CONFLICT]["http_status"] == 409
    assert registered[DUPLICATE_EVENT]["http_status"] == 409
