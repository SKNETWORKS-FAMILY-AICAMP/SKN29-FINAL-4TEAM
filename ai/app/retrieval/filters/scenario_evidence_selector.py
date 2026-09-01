"""Select scenario spans from verified source text, never from evaluation cases."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from ...schemas import StructuredSymptom
from ...safety.signal_detector import has_asserted_keyword
from ..models.retrieved_chunk import RetrievedChunk
from .evidence_applicability_gate import EvidenceApplicability
from .evidence_topic_filter import EvidenceTopicFilter


@dataclass(frozen=True, slots=True)
class ScenarioSelectionResult:
    chunks: tuple[RetrievedChunk, ...]
    reasons: tuple[str, ...]


class ScenarioEvidenceSelector:
    _APPLICABILITY_MARKERS = {
        EvidenceApplicability.ABSENCE_WITHIN_10_DAYS: ("10일 이내",),
        EvidenceApplicability.ABSENCE_OVER_10_DAYS: ("10일 이상",),
        EvidenceApplicability.LONG_UNUSED: ("장시간 미사용", "장시간 사용하지", "오랫동안 사용"),
        EvidenceApplicability.UNSUITABLE_INSTALLATION: ("부적합",),
    }
    _HOT_CUES = (
        ("HOT_MODULE_ALERT", r"lcd.{0,30}(?:점검|오류)|모듈.{0,12}(?:문구|표시)"),
        ("HOT_HEATER_FAULT", r"히터.{0,12}(?:고장|이상)"),
        ("HOT_STEAM", r"스팀|증기"),
        ("HOT_INTERRUPTION", r"끊김|끊겨|끊기|기포"),
        ("HOT_STOPPED", r"출수 중.{0,8}중단|사용 중.{0,12}나오지 않게|나오다.{0,8}멈|나오다가.{0,8}중단"),
        ("HOT_LUKEWARM", r"미지근|뜨겁지|안 뜨겁|덜 뜨거|온도가 낮"),
        ("HOT_NO_OUTPUT", r"온수.{0,8}(?:안 나|나오지 않|미출수|잠금)|온수 잠금"),
    )

    @classmethod
    def _hot_scenario(cls, text: str, *, asserted_only: bool = False) -> str | None:
        text = cls._normalize(text)
        # A source explicitly saying this is not a fault is not a fault heading.
        for name, pattern in cls._HOT_CUES:
            if name == "HOT_HEATER_FAULT" and re.search(r"고장(?:이)? (?:아님|아닌)", text):
                continue
            if any(not asserted_only or has_asserted_keyword(
                text, match.group(0), negated_predicate=name == "HOT_NO_OUTPUT")
                   for match in re.finditer(pattern, text)):
                return name
        return None

    def select_chunks(self, chunks: Iterable[RetrievedChunk], *,
                      structured_symptom: StructuredSymptom | None,
                      raw_symptom: str, applicability: EvidenceApplicability | None) -> ScenarioSelectionResult:
        selected, reasons = [], []
        hot_request = bool(structured_symptom and structured_symptom.target_water_type == "온수")
        hot_scenario = self._hot_scenario(raw_symptom, asserted_only=True) if hot_request else None
        for chunk in chunks:
            content, reason = chunk.content, "TOPIC_ONLY"
            if applicability in self._APPLICABILITY_MARKERS:
                content = self._select_applicability(content, applicability)
                reason = f"APPLICABILITY_{applicability.value}"
            elif hot_request:
                low_flow = bool(
                    hot_scenario is None and structured_symptom.symptom_type == "출수량 저하"
                    and re.search(r"졸졸|쫄쫄|찔끔|조금|적게|약하게|수압|출수량", raw_symptom)
                )
                if low_flow and EvidenceTopicFilter.canonical_topic(chunk) == "symptom_low_flow":
                    reason = "HOT_LOW_FLOW"
                else:
                    content = self._select_hot(content, hot_scenario)
                    reason = hot_scenario or "HOT_CONDITION_UNCONFIRMED"
            if not content:
                reasons.append(f"{chunk.chunk_id}:NO_SCENARIO_MATCH:{reason}")
                continue
            selected.append(chunk.model_copy(update={"content": content}))
            reasons.append(f"{chunk.chunk_id}:{reason}")
        return ScenarioSelectionResult(tuple(selected), tuple(reasons))

    def _select_hot(self, content, wanted):
        if wanted is None:
            return ""
        selected = []
        matched, active, other = False, False, False
        current_scenario = None
        for segment in self._segments(content):
            scenario = self._hot_scenario(segment)
            # A cause/explanation mentioning another symptom is not a heading.
            # For example a stopped-hot-water paragraph can explain low-pressure
            # interruptions without becoming an interruption scenario itself.
            heading = re.match(r"(?:온수|스팀|증기|lcd|순간\s*온수|히터|(?:참\s*고\s*)?상기)", self._normalize(segment))
            if scenario is not None and (current_scenario is None or heading):
                current_scenario = scenario
                active = scenario == wanted
                other = not active
                if active:
                    matched = True
                    selected.append(segment)
            elif active:
                selected.append(segment)
            elif not other and re.search(r"음용하지|화상|사용을 중지", segment):
                selected.append(segment)
        return " ".join(selected) if matched else ""

    def _select_applicability(self, content, applicability):
        include = self._APPLICABILITY_MARKERS[applicability]
        exclude = tuple(marker for key, markers in self._APPLICABILITY_MARKERS.items()
                        if key != applicability for marker in markers)
        selected = []
        matched, active, other = False, False, False
        for segment in self._segments(content):
            if any(marker in segment for marker in include):
                matched, active, other = True, True, False
                selected.append(segment)
            elif any(marker in segment for marker in exclude):
                active, other = False, True
            elif re.search(r"경우|때는|때에|후에는|[가-힣]+면(?= |[,.;!?]|$)", segment):
                active, other = False, True
            elif active or (not other and re.search(r"음용하지|화상|사용을 중지", segment)):
                selected.append(segment)
        return " ".join(selected) if matched else ""

    @staticmethod
    def _segments(content):
        return [segment.strip(" -•\t") for segment in re.split(r"(?:\r?\n)+|(?<=[.!?。])\s+|(?<=[.!?。][)）])\s+", content)
                if segment.strip(" -•\t")]

    @staticmethod
    def _normalize(value):
        return " ".join(value.casefold().split())


__all__ = ["ScenarioEvidenceSelector", "ScenarioSelectionResult"]
