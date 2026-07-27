"""업무 규칙 예외."""

from typing import Any

from common.exceptions.base import BackendError


class BusinessError(BackendError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Any | None = None,
        status_code: int = 409,
    ) -> None:
        super().__init__(
            code,
            message,
            details=details,
            status_code=status_code,
        )
