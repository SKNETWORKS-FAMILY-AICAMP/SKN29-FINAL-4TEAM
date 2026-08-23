"""LLM 고객 안내 문구의 안전 의미와 공식 근거 범위를 보수적으로 검증한다."""

from __future__ import annotations

import re
from collections.abc import Iterable

from ...schemas import UsageGuidanceStatus


class GuidanceMessageGuard:
    """자유 문구가 Runtime의 Safety·Evidence 결정을 뒤집지 못하게 한다."""

    _REPAIR_PATTERN = re.compile(
        r"(?:분해|뜯(?:어|고|으)|나사|전선|기판|모터|커버.{0,8}열|"
        r"뒷면.{0,8}열|직접\s*수리|피복|내부.{0,8}(?:열|점검|확인))"
    )
    _UNVERIFIED_SAFETY_CLAIM_PATTERN = re.compile(
        r"(?:세균|미생물|유해\s*물질|수질\s*(?:검사|안전)|"
        r"마셔도|음용|인체에|무해|완전히\s*안전|안심)"
    )
    _INTERNAL_METADATA_PATTERN = re.compile(
        r"\b(?:chunk_id|document_id|evidence_id|similarity_score|"
        r"retrieval_score|distance_score|source_path|prompt)\s*[:=]",
        re.IGNORECASE,
    )
    _PARTIAL_STOP_CONFLICT_PATTERNS = (
        re.compile(
            r"(?:모든|전체).{0,16}(?:정상|계속\s*사용|사용\s*(?:가능|해도))"
        ),
        re.compile(r"(?:제한|중지).{0,12}(?:필요\s*없|하지\s*않아도)"),
        re.compile(r"정상적으로.{0,12}계속.{0,12}사용"),
    )
    def validate_safety_semantics(
        self,
        message: str,
        guidance_status: UsageGuidanceStatus,
    ) -> None:
        """직접 수리·근거 없는 안전 주장·상태 모순을 차단한다."""

        if self._REPAIR_PATTERN.search(message):
            raise ValueError("LLM 안내 문구가 직접 수리·내부 점검을 유도합니다.")
        if self._UNVERIFIED_SAFETY_CLAIM_PATTERN.search(message):
            raise ValueError("LLM 안내 문구가 검증되지 않은 수질·안전 주장을 포함합니다.")
        if self._INTERNAL_METADATA_PATTERN.search(message):
            raise ValueError("LLM 안내 문구가 내부 검색 메타데이터를 포함합니다.")
        if guidance_status == UsageGuidanceStatus.PARTIAL_STOP and any(
            pattern.search(message)
            for pattern in self._PARTIAL_STOP_CONFLICT_PATTERNS
        ):
            raise ValueError("LLM 안내 문구가 PARTIAL_STOP 상태와 충돌합니다.")

    def validate_grounding(
        self,
        message: str,
        *,
        grounding_texts: Iterable[str],
    ) -> None:
        """승인 Evidence 한 항목과 완전히 같은 추출형 문구만 허용한다."""

        normalized_message = " ".join(message.split())
        approved_messages = {
            " ".join(text.split())
            for text in grounding_texts
            if text and text.strip()
        }
        if normalized_message not in approved_messages:
            raise ValueError("LLM 안내 문구가 승인 Evidence 문장과 일치하지 않습니다.")
