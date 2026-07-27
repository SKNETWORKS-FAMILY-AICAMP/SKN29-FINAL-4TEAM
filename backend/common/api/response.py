"""success·data·error 공통 Wrapper."""

from typing import Any

from rest_framework.response import Response

from common.api.metadata import build_response_metadata


def build_success_payload(
    data: Any,
    *,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "success": True,
        "data": data,
        "error": None,
    }
    metadata = build_response_metadata(correlation_id)
    if metadata is not None:
        payload["metadata"] = metadata
    return payload


def build_error_payload(
    code: str,
    message: str,
    details: Any | None = None,
    *,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "success": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "details": {} if details is None else details,
        },
    }
    metadata = build_response_metadata(correlation_id)
    if metadata is not None:
        payload["metadata"] = metadata
    return payload


def success_response(
    data: Any,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> Response:
    return Response(
        build_success_payload(data),
        status=status_code,
        headers=headers,
    )


def error_response(
    code: str,
    message: str,
    *,
    details: Any | None = None,
    status_code: int = 400,
    headers: dict[str, str] | None = None,
) -> Response:
    return Response(
        build_error_payload(code, message, details),
        status=status_code,
        headers=headers,
    )
