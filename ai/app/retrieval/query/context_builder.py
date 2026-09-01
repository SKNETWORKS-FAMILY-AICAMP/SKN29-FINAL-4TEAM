"""검증된 구조화 증상을 PII-safe 검색 문맥으로 조립한다."""

from __future__ import annotations

import re

from ...schemas import StructuredSymptom


class RetrievalContextBuilder:
    """고객 원문을 보존하면서 검증된 구조화 필드만 검색 질의에 덧붙인다."""

    _PRIVATE_PATTERNS = (
        re.compile(r"(?<!\d)(?:\+?82[-\s]?)?0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"),
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        re.compile(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)"),
        re.compile(r"https?://\S+", flags=re.IGNORECASE),
        re.compile(r"주소\s+[^,|\r\n]{1,100}"),
        re.compile(r"(?<!\d)\d{8,}(?!\d)"),
    )

    def build(
        self,
        *,
        raw_symptom: str,
        structured_symptom: StructuredSymptom | None,
        max_length: int = 3000,
    ) -> str:
        values: list[str] = [raw_symptom]
        if structured_symptom is not None:
            values.extend(
                value
                for value in (
                    structured_symptom.symptom_type,
                    structured_symptom.target_water_type,
                    structured_symptom.occurrence_time,
                    structured_symptom.occurrence_condition,
                    structured_symptom.error_code,
                )
                if value
            )
            values.extend(structured_symptom.accompanying_symptoms)
            values.extend(structured_symptom.actions_taken)

        sanitized: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = self._redact(str(value)).strip()
            normalized = " ".join(item.split()).casefold()
            if not item or normalized in seen:
                continue
            seen.add(normalized)
            sanitized.append(item)
        return " | ".join(sanitized)[:max_length]

    @classmethod
    def _redact(cls, value: str) -> str:
        sanitized = value
        for pattern in cls._PRIVATE_PATTERNS:
            sanitized = pattern.sub("[REDACTED]", sanitized)
        return sanitized


__all__ = ["RetrievalContextBuilder"]
