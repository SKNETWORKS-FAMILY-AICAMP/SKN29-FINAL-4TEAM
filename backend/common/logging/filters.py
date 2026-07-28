"""요청 Context를 로그 Record에 추가한다."""

import logging

from common.middleware.request_context import get_correlation_id


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        return True
