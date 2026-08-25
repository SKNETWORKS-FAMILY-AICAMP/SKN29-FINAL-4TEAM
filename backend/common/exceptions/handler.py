"""DRF 예외를 공통 오류 Wrapper로 변환한다."""

import logging

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler as drf_exception_handler

from common.api.response import error_response
from common.exceptions.base import BackendError
from common.exceptions.error_codes import (
    AUTH_REQUIRED,
    FORBIDDEN,
    INTERNAL_ERROR,
    INVALID_REQUEST,
    RESOURCE_NOT_FOUND,
    VALIDATION_ERROR,
)


logger = logging.getLogger("watercare.exception")

ERROR_BY_STATUS = {
    status.HTTP_400_BAD_REQUEST: (
        INVALID_REQUEST,
        "요청 형식을 확인해 주세요.",
    ),
    status.HTTP_401_UNAUTHORIZED: (
        AUTH_REQUIRED,
        "인증이 필요합니다.",
    ),
    status.HTTP_403_FORBIDDEN: (
        FORBIDDEN,
        "요청한 작업을 수행할 권한이 없습니다.",
    ),
    status.HTTP_404_NOT_FOUND: (
        RESOURCE_NOT_FOUND,
        "요청한 대상을 찾을 수 없습니다.",
    ),
}


def api_exception_handler(exc, context):
    if isinstance(exc, BackendError):
        return error_response(
            exc.code,
            exc.message,
            details=exc.details,
            status_code=exc.status_code,
            headers=exc.headers,
        )

    response = drf_exception_handler(exc, context)

    if isinstance(exc, ValidationError):
        return error_response(
            VALIDATION_ERROR,
            "입력값을 확인해 주세요.",
            details=response.data if response is not None else {},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    if response is not None:
        if response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            code = INTERNAL_ERROR
            message = "요청 처리 중 오류가 발생했습니다."
        else:
            code, message = ERROR_BY_STATUS.get(
                response.status_code,
                (INVALID_REQUEST, "요청을 처리할 수 없습니다."),
            )
        return error_response(
            code,
            message,
            details={},
            status_code=response.status_code,
            headers=response.headers,
        )

    logger.error(
        "unhandled_exception",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return error_response(
        INTERNAL_ERROR,
        "요청 처리 중 오류가 발생했습니다.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
