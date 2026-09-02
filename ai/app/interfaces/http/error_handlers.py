"""FastAPI 공통 오류 핸들러 등록 모듈."""

import time
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ...schemas import AiStage
from .errors import AiServiceError
from .response_models import ApiErrorDetail, ApiErrorResponse
from .structured_logging import log_analysis_event


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
    if "correlation_id" in values:
        try:
            values["correlation_id"] = UUID(str(values["correlation_id"]))
        except (TypeError, ValueError):
            values.pop("correlation_id")
    ai_request_id = values.get("ai_request_id")
    if not isinstance(ai_request_id, str) or not 1 <= len(ai_request_id) <= 100:
        values.pop("ai_request_id", None)
    state_version = values.get("state_version")
    if not isinstance(state_version, int) or isinstance(state_version, bool) or state_version < 1:
        values.pop("state_version", None)
    return values


def _error_ids(request: Request, supplied: dict[str, Any] | None = None) -> dict[str, Any]:
    values = dict(supplied or {})
    for key in ("inquiry_id", "correlation_id", "ai_request_id", "state_version"):
        if key not in values:
            value = getattr(request.state, key, None)
            if value is not None:
                values[key] = value
    if "correlation_id" not in values:
        header_id = request.headers.get("X-Correlation-ID")
        if header_id:
            try:
                values["correlation_id"] = UUID(header_id)
            except ValueError:
                pass
    return values


def _log_failure(
    request: Request,
    ids: dict[str, Any],
    *,
    code: str,
    stage: AiStage,
    retry_count: int = 0,
) -> None:
    started_at = getattr(request.state, "analysis_started_at", None)
    latency_ms = round((time.perf_counter() - started_at) * 1000, 2) if started_at else 0.0
    log_analysis_event(
        "analysis_failed",
        correlation_id=ids.get("correlation_id"),
        inquiry_id=ids.get("inquiry_id"),
        ai_request_id=ids.get("ai_request_id"),
        state_version=ids.get("state_version"),
        stage=stage.value,
        status="FAILED",
        retry_count=retry_count,
        latency_ms=latency_ms,
        error_code=code,
    )


def _error_response(ids: dict[str, Any], detail: ApiErrorDetail) -> ApiErrorResponse:
    return ApiErrorResponse(
        success=False,
        inquiry_id=ids.get("inquiry_id"),
        correlation_id=ids.get("correlation_id"),
        ai_request_id=ids.get("ai_request_id"),
        state_version=ids.get("state_version"),
        error=detail,
    )


def _response(payload: ApiErrorResponse, http_status: int) -> JSONResponse:
    response = JSONResponse(status_code=http_status, content=payload.model_dump(mode="json"))
    if payload.correlation_id:
        response.headers["X-Correlation-ID"] = str(payload.correlation_id)
    return response


def register_error_handlers(app: FastAPI) -> None:
    """FastAPI 예외 처리 핸들러 일괄 등록."""

    @app.exception_handler(AiServiceError)
    async def ai_service_error_handler(request: Request, exc: AiServiceError):
        ids = _error_ids(request, {
            key: value for key, value in {
                "inquiry_id": exc.inquiry_id,
                "correlation_id": exc.correlation_id,
                "ai_request_id": exc.ai_request_id,
                "state_version": exc.state_version,
            }.items() if value is not None
        })
        _log_failure(
            request,
            ids,
            code=exc.code,
            stage=exc.failure_stage,
            retry_count=exc.retry_count,
        )
        detail = ApiErrorDetail(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            retryable=exc.retryable,
            failure_stage=exc.failure_stage,
            retry_count=exc.retry_count,
        )
        return _response(
            _error_response(ids, detail),
            exc.http_status,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        ids = _request_ids(exc.body)
        ids = _error_ids(request, ids)
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
        _log_failure(request, ids, code="AI-VALIDATION-01", stage=AiStage.STRUCTURING)
        return _response(_error_response(ids, detail), status.HTTP_422_UNPROCESSABLE_CONTENT)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        ids = _error_ids(request)
        detail = ApiErrorDetail(
            code="AI-FAILED-01",
            message=exc.detail if isinstance(exc.detail, str) else "AI 요청 처리 중 오류가 발생했습니다.",
            details=None,
            retryable=exc.status_code >= 500,
            failure_stage=AiStage.FAILED,
            retry_count=0,
        )
        _log_failure(request, ids, code="AI-FAILED-01", stage=AiStage.FAILED)
        return _response(_error_response(ids, detail), exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        ids = _error_ids(request)
        detail = ApiErrorDetail(
            code="AI-FAILED-01",
            message="AI 분석을 완료하지 못했습니다.",
            details=None,
            retryable=True,
            failure_stage=AiStage.FAILED,
            retry_count=0,
        )
        _log_failure(request, ids, code="AI-FAILED-01", stage=AiStage.FAILED)
        return _response(_error_response(ids, detail), status.HTTP_503_SERVICE_UNAVAILABLE)
