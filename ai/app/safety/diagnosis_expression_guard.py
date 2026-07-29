"""확정 고장 진단·안전 보증 표현 생성 차단."""

from typing import List, Tuple

from ..validation.safety.prohibited_phrase_validator import ProhibitedPhraseValidator


class DiagnosisExpressionGuard:
    """금지 표현을 탐지하고 안전한 fallback 문구로 치환한다."""

    def __init__(self, validator: ProhibitedPhraseValidator | None = None):
        self._validator = validator or ProhibitedPhraseValidator()

    def sanitize(self, text: str) -> Tuple[str, List[str]]:
        _, sanitized, detected = self._validator.validate(text)
        return sanitized, detected
