"""요청 Context를 로그 Record에 추가한다."""

import logging
from uuid import UUID

from common.middleware.request_context import get_correlation_id


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        explicit = self._canonical_uuid(
            getattr(record, "correlation_id", None)
        )
        contextual = self._canonical_uuid(get_correlation_id())
        record.correlation_id = explicit or contextual
        return True

    @staticmethod
    def _canonical_uuid(value: object) -> str | None:
        if value is None:
            return None
        try:
            return str(UUID(str(value)))
        except (TypeError, ValueError, AttributeError):
            return None
