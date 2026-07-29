"""FastAPI 공통 오류 핸들러 등록 모듈."""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from ai.app.interfaces.http.response_models import ApiErrorDetail, ApiErrorResponse


def register_error_handlers(app: FastAPI) -> None:
    """FastAPI 예외 처리 핸들러 일괄 등록"""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Pydantic / 입력 파라미터 검증 오류 (422)"""
        error_detail = ApiErrorDetail(
            code="INVALID_INPUT_FORMAT",
            message="요청 데이터 형식이 올바르지 않거나 필수 필드가 누락되었습니다.",
            details={"errors": exc.errors()},
            retryable=False
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ApiErrorResponse(error=error_detail).model_dump(mode="json")
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """HTTP 표준 예외"""
        error_detail = ApiErrorDetail(
            code=f"HTTP_{exc.status_code}",
            message=exc.detail if isinstance(exc.detail, str) else "요청 처리 중 오류가 발생했습니다.",
            details=exc.detail if isinstance(exc.detail, dict) else None,
            retryable=exc.status_code >= 500
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiErrorResponse(error=error_detail).model_dump(mode="json")
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """예상하지 못한 서버 내부 오류 (500) - 스택 트레이스 은닉"""
        error_detail = ApiErrorDetail(
            code="AI_INTERNAL_SERVER_ERROR",
            message="AI 서비스 내부에서 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            details=None,
            retryable=True
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ApiErrorResponse(error=error_detail).model_dump(mode="json")
        )
