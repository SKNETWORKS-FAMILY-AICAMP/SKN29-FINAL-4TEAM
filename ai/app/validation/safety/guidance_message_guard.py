"""LLM 고객 안내 문구가 결정적 Safety 판단을 뒤집지 않는지 검증한다."""

from __future__ import annotations

import re
import unicodedata
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
        """승인 문장 선택·조합 및 닫힌 존댓말 변환만 허용한다."""
        message_units = self._sentences(message)
        groups = [self._sentences(text) for text in grounding_texts]
        if not message_units or not any(groups):
            raise ValueError("고객 안내 문구를 뒷받침할 공식 근거가 없습니다.")
        output = [self._canonical_sentence(unit) for unit in message_units]
        canonical_groups = [[self._canonical_sentence(unit) for unit in group] for group in groups]
        approved = {unit for group in canonical_groups for unit in group}
        if any(unit not in approved for unit in output):
            raise ValueError("고객 안내에 근거 없는 주장·행동·조건이 있습니다.")
        output_set = set(output)
        if len(output) != len(output_set):
            raise ValueError("동일 근거 조치를 반복했습니다.")
        for original, canonical in zip(groups, canonical_groups):
            if not output_set.intersection(canonical):
                continue
            required = {unit for source, unit in zip(original, canonical)
                        if re.search(r"하지\s*(?:않|마)|금지|주의|위험|화상|감전|중지|중단|차단|상담|문의|연락|전문|그\s*후|이\s*후|이\s*때|그래도|경우|(?:으)?면\b|때(?:는|에)?\b|이내|이상|이하|미만|초과", source)}
            if not required.issubset(output_set):
                raise ValueError("근거의 조건·경고·상담 안내를 누락했습니다.")
            positions = [canonical.index(unit) for unit in output if unit in canonical]
            if positions != sorted(positions):
                raise ValueError("승인된 조치 순서를 변경했습니다.")

    @staticmethod
    def _sentences(value):
        return [unit.strip() for unit in re.split(r"(?<=[.!?。])\s+|[\r\n]+", value) if unit.strip()]

    @staticmethod
    def _canonical_sentence(value):
        value = " ".join(unicodedata.normalize("NFC", value).split())
        value = value.removesuffix(".").removesuffix("。").removeprefix("먼저 ")
        value = re.sub(r"(?:출수된|해당) 물(?=[은을이])", "출수된 물", value)
        value = re.sub(r"하지\s*(?:않습니다|마세요|마십시오|말아\s*주세요)$", "하지 않음", value)
        return re.sub(r"(확인|점검|청소|교체|사용|문의|연락|출수|해제|중지|중단|차단|주의|요청)(?:합니다|하세요|하십시오|해\s*주세요)$", r"\1함", value)

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
