"""Backend 기본 예외."""

from typing import Any


class BackendError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Any | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = {} if details is None else details
        self.status_code = status_code
