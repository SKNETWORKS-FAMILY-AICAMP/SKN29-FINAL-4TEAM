"""Topic 검색 결과를 현재 문의의 세부 scenario 근거로 축소한다."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from ...schemas import StructuredSymptom
from ..models.retrieved_chunk import RetrievedChunk
from .evidence_applicability_gate import EvidenceApplicability


@dataclass(frozen=True, slots=True)
class ScenarioSelectionResult:
    chunks: tuple[RetrievedChunk, ...]
    reasons: tuple[str, ...]


class ScenarioEvidenceSelector:
    """문장 분해와 제한된 결정 규칙으로 무관한 하위 scenario를 제거한다."""

    _APPLICABILITY_MARKERS = {
        EvidenceApplicability.ABSENCE_WITHIN_10_DAYS: ("10일 이내", "통수"),
        EvidenceApplicability.ABSENCE_OVER_10_DAYS: ("10일 이상", "상담", "점검"),
        EvidenceApplicability.LONG_UNUSED: ("장시간 미사용", "오랫동안 사용"),
        EvidenceApplicability.UNSUITABLE_INSTALLATION: ("설치 장소", "부적합", "필터"),
    }
    _HOT_LUKEWARM_MARKERS = (
        "미지근",
        "뜨겁지",
        "두 번째 잔",
        "두번째 잔",
        "10초",
        "재연결",
    )
    _HOT_UNRELATED_MARKERS = ("스팀", "lcd", "모듈 오류", "미출수", "나오지 않", "잠금")
    _HOT_REQUIRED_SAFETY = ("음용하지", "화상", "사용을 중지", "전원 플러그")

    def select_chunks(
        self,
        chunks: Iterable[RetrievedChunk],
        *,
        structured_symptom: StructuredSymptom | None,
        raw_symptom: str,
        applicability: EvidenceApplicability | None,
    ) -> ScenarioSelectionResult:
        candidates = list(chunks)
        if not candidates:
            return ScenarioSelectionResult((), ())

        selected: list[RetrievedChunk] = []
        reasons: list[str] = []
        context = self._normalize(
            " ".join(
                [
                    raw_symptom,
                    structured_symptom.occurrence_condition or ""
                    if structured_symptom is not None
                    else "",
                ]
            )
        )
        hot_lukewarm = bool(
            structured_symptom is not None
            and structured_symptom.symptom_type == "온도 이상"
            and structured_symptom.target_water_type == "온수"
            and any(marker in context for marker in ("미지근", "뜨겁지", "온도가 낮"))
        )

        for chunk in candidates:
            content = chunk.content
            reason = "TOPIC_ONLY"
            if applicability in self._APPLICABILITY_MARKERS:
                content = self._select_segments(
                    content,
                    include=self._APPLICABILITY_MARKERS[applicability],
                    preserve=("상담", "점검", "사용 중지", "필터"),
                )
                reason = f"APPLICABILITY_{applicability.value}"
            elif hot_lukewarm:
                content = self._select_segments(
                    content,
                    include=self._HOT_LUKEWARM_MARKERS,
                    preserve=self._HOT_REQUIRED_SAFETY,
                    exclude=self._HOT_UNRELATED_MARKERS,
                )
                reason = "HOT_WATER_LUKEWARM"
            else:
                narrowed = self._select_by_context(
                    content,
                    structured_symptom=structured_symptom,
                )
                if narrowed != content:
                    content = narrowed
                    reason = "STRUCTURED_CONTEXT_OVERLAP"

            selected.append(chunk.model_copy(update={"content": content}))
            reasons.append(f"{chunk.chunk_id}:{reason}")
        return ScenarioSelectionResult(tuple(selected), tuple(reasons))

    def _select_by_context(
        self,
        content: str,
        *,
        structured_symptom: StructuredSymptom | None,
    ) -> str:
        segments = self._segments(content)
        if structured_symptom is None or len(segments) < 3:
            return content
        context_values = [
            structured_symptom.symptom_type,
            structured_symptom.target_water_type or "",
            structured_symptom.occurrence_condition or "",
            *structured_symptom.actions_taken,
            *structured_symptom.accompanying_symptoms,
        ]
        terms = {
            token
            for value in context_values
            for token in re.findall(r"[0-9a-z가-힣]{2,}", self._normalize(value))
            if token not in {"이상", "증상", "발생", "확인"}
        }
        matched = [
            segment
            for segment in segments
            if any(term in self._normalize(segment) for term in terms)
            or any(
                marker in self._normalize(segment)
                for marker in ("사용 중지", "금지", "주의", "상담", "점검", "플러그", "밸브")
            )
        ]
        return " ".join(matched) if matched else content

    def _select_segments(
        self,
        content: str,
        *,
        include: tuple[str, ...],
        preserve: tuple[str, ...],
        exclude: tuple[str, ...] = (),
    ) -> str:
        selected: list[str] = []
        for segment in self._segments(content):
            normalized = self._normalize(segment)
            relevant = any(marker in normalized for marker in include)
            safety = any(marker in normalized for marker in preserve)
            unrelated = any(marker in normalized for marker in exclude)
            if (relevant or safety) and not (unrelated and not relevant):
                selected.append(segment)
        return " ".join(selected) if selected else content

    @staticmethod
    def _segments(content: str) -> list[str]:
        return [
            segment.strip(" -•\t")
            for segment in re.split(r"(?:\r?\n)+|(?<=[.!?。])\s+", content)
            if segment.strip(" -•\t")
        ]

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().split())


__all__ = ["ScenarioEvidenceSelector", "ScenarioSelectionResult"]
