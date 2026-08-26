"""미검증·비공식 출처의 단독 근거 사용 요청을 차단한다."""

import re


class FaqUsageValidator:
    """명시적으로 미검증 출처만 요구하는 검색 요청을 거부한다."""

    _unverified_source = re.compile(
        r"(미검증|비공식|확인(?:이)?\s*안\s*된|검증되지\s*않은|"
        r"공식\s*확인\s*없이|공식적으로\s*확인되지\s*않은|unverified)",
        re.IGNORECASE,
    )
    _source = re.compile(r"(faq|문서|자료|출처|근거)", re.IGNORECASE)
    _exclusive = re.compile(
        r"(만\s*(?:근거|사용|참조)?|단독|오직|그대로\s*(?:따라|사용|적용)|only)",
        re.IGNORECASE,
    )

    def allows_query(self, query_text: str) -> bool:
        """미검증 출처를 단독 사용하라는 요청이면 False를 반환한다."""
        normalized = " ".join(query_text.split())
        explicitly_unverified_only = (
            self._unverified_source.search(normalized)
            and self._source.search(normalized)
            and self._exclusive.search(normalized)
        )
        return not bool(explicitly_unverified_only)
