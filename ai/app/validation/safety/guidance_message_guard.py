"""LLM 고객 안내 문구가 결정적 Safety 판단을 뒤집지 않는지 검증한다."""

from __future__ import annotations

import re
from ...schemas import UsageGuidanceStatus


class GuidanceMessageGuard:
    """자유 문구가 Runtime의 Safety·Evidence 결정을 뒤집지 못하게 한다."""

    _REPAIR_PATTERN = re.compile(
        r"(?:분해|뜯(?:어|고|으)|나사|전선|기판|모터|커버.{0,8}열|"
        r"뒷면.{0,8}열|직접\s*수리|피복|내부.{0,8}(?:열|점검|확인))"
    )
    _UNVERIFIED_SAFETY_CLAIM_PATTERN = re.compile(
        r"(?:마셔도.{0,8}(?:됩니다|돼요|괜찮)|"
        r"음용\s*(?:가능|해도|하여도)|"
        r"수질.{0,8}(?:안전|문제\s*없)|"
        r"인체에.{0,8}(?:무해|안전)|"
        r"완전히\s*안전|안심하고.{0,8}(?:마셔|사용))"
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
        re.compile(r"(?:제한|중지|확인|점검|조치).{0,12}(?:필요\s*없|하지\s*않아도|생략)"),
        re.compile(r"정상적으로.{0,12}계속.{0,12}사용"),
    )

    def validate_grounding(
        self,
        message: str,
        *,
        grounding_texts: list[str],
    ) -> None:
        """Exact copy 없이도 근거와 최소 의미 표면을 공유하는지 확인한다."""

        message_units = self._semantic_units(message)
        if not message_units or not grounding_texts:
            raise ValueError("고객 안내 문구를 뒷받침할 공식 근거가 없습니다.")
        best_overlap = 0.0
        for grounding in grounding_texts:
            grounding_units = self._semantic_units(grounding)
            if not grounding_units:
                continue
            overlap = len(message_units & grounding_units) / min(
                len(message_units),
                len(grounding_units),
            )
            best_overlap = max(best_overlap, overlap)
        if best_overlap < 0.2:
            raise ValueError("고객 안내 문구가 공식 근거 의미 범위를 벗어났습니다.")

    @staticmethod
    def _semantic_units(value: str) -> set[str]:
        normalized = re.sub(r"[^0-9a-z가-힣]+", "", value.casefold())
        if len(normalized) < 2:
            return {normalized} if normalized else set()
        return {
            normalized[index : index + 2]
            for index in range(len(normalized) - 1)
        }

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
