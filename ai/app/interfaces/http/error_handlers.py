"""FastAPI 공통 오류 핸들러 등록 모듈."""

from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ...schemas import AiStage
from .errors import AiServiceError
from .response_models import ApiErrorDetail, ApiErrorResponse


def _request_ids(body: Any) -> dict[str, Any]:
    """검증 실패 Body에서 안전한 추적 식별자만 추출한다."""
    if not isinstance(body, dict):
        return {}
    values = {
        key: body.get(key)
        for key in ("inquiry_id", "correlation_id", "ai_request_id", "state_version")
        if body.get(key) is not None
    }
    if "inquiry_id" in values:
        try:
            values["inquiry_id"] = UUID(str(values["inquiry_id"]))
        except (TypeError, ValueError):
            values.pop("inquiry_id")
    return values


def _response(payload: ApiErrorResponse, http_status: int) -> JSONResponse:
    response = JSONResponse(status_code=http_status, content=payload.model_dump(mode="json"))
    if payload.correlation_id:
        response.headers["X-Correlation-ID"] = payload.correlation_id
    return response


def register_error_handlers(app: FastAPI) -> None:
    """FastAPI 예외 처리 핸들러 일괄 등록."""

    @app.exception_handler(AiServiceError)
    async def ai_service_error_handler(request: Request, exc: AiServiceError):
        detail = ApiErrorDetail(
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
            failure_stage=exc.failure_stage,
            retry_count=exc.retry_count,
        )
        return _response(
            ApiErrorResponse(
                inquiry_id=exc.inquiry_id,
                correlation_id=exc.correlation_id,
                ai_request_id=exc.ai_request_id,
                state_version=exc.state_version,
                error=detail,
            ),
            exc.http_status,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        ids = _request_ids(exc.body)
        safe_errors = [
            {"location": list(error["loc"]), "type": error["type"], "message": error["msg"]}
            for error in exc.errors()
        ]
        detail = ApiErrorDetail(
            code="AI-VALIDATION-01",
            message="AI 분석 요청 스키마 검증에 실패했습니다.",
            details={"errors": safe_errors},
            retryable=False,
            failure_stage=AiStage.STRUCTURING,
            retry_count=0,
        )
        return _response(ApiErrorResponse(**ids, error=detail), status.HTTP_422_UNPROCESSABLE_CONTENT)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        detail = ApiErrorDetail(
            code="AI-FAILED-01",
            message=exc.detail if isinstance(exc.detail, str) else "AI 요청 처리 중 오류가 발생했습니다.",
            retryable=exc.status_code >= 500,
            failure_stage=AiStage.FAILED,
            retry_count=0,
        )
        return _response(ApiErrorResponse(error=detail), exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        detail = ApiErrorDetail(
            code="AI-FAILED-01",
            message="AI 분석을 완료하지 못했습니다.",
            retryable=True,
            failure_stage=AiStage.FAILED,
            retry_count=0,
        )
        return _response(ApiErrorResponse(error=detail), status.HTTP_503_SERVICE_UNAVAILABLE)
