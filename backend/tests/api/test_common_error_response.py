"""DRF 공통 예외 응답 검증."""

from django.test import override_settings
from django.urls import path
from rest_framework.exceptions import (
    APIException,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    ValidationError,
)
from rest_framework.views import APIView

from common.exceptions.business import BusinessError
from common.exceptions.handler import api_exception_handler


class NotFoundTestView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        raise NotFound()


urlpatterns = [
    path("api/v1/_test/not-found", NotFoundTestView.as_view()),
]


class ServiceUnavailable(APIException):
    status_code = 503
    default_code = "service_unavailable"


def test_business_error_is_wrapped():
    response = api_exception_handler(
        BusinessError(
            "INVALID_STATE_TRANSITION",
            "현재 상태에서 요청한 작업을 수행할 수 없습니다.",
            details={"current_state": "SUBMITTED"},
        ),
        {},
    )

    assert response.status_code == 409
    assert response.data == {
        "success": False,
        "data": None,
        "error": {
            "code": "INVALID_STATE_TRANSITION",
            "message": "현재 상태에서 요청한 작업을 수행할 수 없습니다.",
            "details": {"current_state": "SUBMITTED"},
        },
    }


def test_validation_error_is_wrapped_without_internal_details():
    response = api_exception_handler(
        ValidationError({"field": ["필수 항목입니다."]}),
        {},
    )

    assert response.status_code == 422
    assert response.data["success"] is False
    assert response.data["data"] is None
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert response.data["error"]["details"] == {
        "field": ["필수 항목입니다."]
    }


def test_not_found_error_uses_public_business_code():
    response = api_exception_handler(NotFound(), {})

    assert response.status_code == 404
    assert response.data["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert response.data["error"]["message"] == (
        "요청한 대상을 찾을 수 없습니다."
    )


def test_bad_request_uses_public_business_code():
    response = api_exception_handler(ParseError(), {})

    assert response.status_code == 400
    assert response.data["error"]["code"] == "INVALID_REQUEST"


def test_unauthorized_uses_public_business_code():
    response = api_exception_handler(NotAuthenticated(), {})

    assert response.status_code == 401
    assert response.data["error"]["code"] == "AUTH_REQUIRED"


def test_forbidden_uses_public_business_code():
    response = api_exception_handler(PermissionDenied(), {})

    assert response.status_code == 403
    assert response.data["error"]["code"] == "FORBIDDEN"


@override_settings(ROOT_URLCONF=__name__)
def test_not_found_error_is_wrapped_through_http(client):
    response = client.get("/api/v1/_test/not-found")

    assert response.status_code == 404
    payload = response.json()
    assert payload["metadata"]["correlation_id"] == response[
        "X-Correlation-ID"
    ]
    assert {
        key: value
        for key, value in payload.items()
        if key != "metadata"
    } == {
        "success": False,
        "data": None,
        "error": {
            "code": "RESOURCE_NOT_FOUND",
            "message": "요청한 대상을 찾을 수 없습니다.",
            "details": {},
        },
    }


def test_unregistered_api_path_uses_common_error_wrapper(client):
    response = client.get("/api/v1/not-a-real-route")

    assert response.status_code == 404
    payload = response.json()
    assert payload["metadata"]["correlation_id"] == response[
        "X-Correlation-ID"
    ]
    assert {
        key: value
        for key, value in payload.items()
        if key != "metadata"
    } == {
        "success": False,
        "data": None,
        "error": {
            "code": "RESOURCE_NOT_FOUND",
            "message": "요청한 대상을 찾을 수 없습니다.",
            "details": {},
        },
    }


def test_drf_server_error_does_not_expose_original_detail():
    response = api_exception_handler(
        ServiceUnavailable("database-host-must-not-be-exposed"),
        {},
    )

    assert response.status_code == 503
    assert response.data["error"]["code"] == "INTERNAL_ERROR"
    assert response.data["error"]["details"] == {}
    assert "database-host-must-not-be-exposed" not in str(response.data)


def test_unhandled_error_does_not_expose_exception_message():
    response = api_exception_handler(
        RuntimeError("secret-value-must-not-be-exposed"),
        {},
    )

    assert response.status_code == 500
    assert "secret-value-must-not-be-exposed" not in str(response.data)
