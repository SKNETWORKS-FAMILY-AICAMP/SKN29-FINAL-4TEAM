"""구조화 증상과 공식 근거 주제의 결정적 선별 경계."""

from __future__ import annotations

from functools import lru_cache
import re
from typing import Iterable

from ..indexing.chunk_loader import ChunkLoader
from ..models.retrieved_chunk import RetrievedChunk
from .canonical_topics import canonical_v2_topic


@lru_cache(maxsize=1)
def _canonical_topic_by_chunk_id() -> dict[str, str]:
    """팀 DB View에 없는 주제 코드를 고정 Canonical 입력에서 복원한다."""

    return {
        chunk.chunk_id: chunk.topic_code
        for chunk in ChunkLoader().load_verified_chunks()
        if chunk.topic_code
    }


class EvidenceTopicFilter:
    """지원이 확정된 증상은 같은 주제의 공식 근거만 생성 경계로 보낸다."""

    _TOPIC_BY_SYMPTOM_TYPE = {
        "제품 누수": "symptom_leak",
        "출수량 저하": "symptom_low_flow",
        "물맛/냄새 이상": "symptom_taste_odor",
        "소음 이상": "symptom_noise",
    }
    _TEMPERATURE_TOPIC_BY_WATER_TYPE = {
        "냉수": "symptom_cold_temperature",
        "온수": "symptom_hot_water_safety",
    }
    _TOPIC_ALIASES = {
        "leak": "symptom_leak", "low_flow": "symptom_low_flow", "no_water": "symptom_no_water",
        "taste_odor": "symptom_taste_odor", "noise_normal": "symptom_noise",
        "noise_ventilation": "symptom_noise", "defrost_noise": "symptom_noise", "ice_making_noise": "symptom_noise",
        "cold_temperature_normal": "symptom_cold_temperature", "cold_temperature_fault": "symptom_cold_temperature",
        "hot_steam": "symptom_hot_water_safety", "hot_water_interruption": "symptom_hot_water_safety",
        "hot_water_stopped": "symptom_hot_water_safety", "no_hot_water": "symptom_hot_water_safety",
    }

    def filter_chunks(
        self,
        chunks: Iterable[RetrievedChunk],
        *,
        symptom_type: str | None,
        target_water_type: str | None = None,
        raw_symptom: str = "",
        selected_symptoms: Iterable[str] = (),
    ) -> list[RetrievedChunk]:
        candidates = list(chunks)
        expected_topic = self._expected_topic(
            symptom_type=symptom_type,
            target_water_type=target_water_type,
        )
        if expected_topic is None:
            return candidates

        expected_topics = {expected_topic}
        if symptom_type == "출수량 저하":
            text = re.sub(r"(?:안\s*나오는\s*(?:건|게|것은)|무출수는)\s*아니[가-힣]*", " ", raw_symptom)
            if re.search(r"(?:전혀|아예)\s*안\s*나|(?:물|온수|냉수|정수)(?:이|가|는|도)?\s*(?:안\s*나|나오지\s*않)|무출수|미출수", text):
                expected_topics = {"symptom_no_water"}
            elif re.search(r"졸졸|쫄쫄|찔끔|조금|적게|약하게|수압|출수량", text):
                expected_topics = {"symptom_low_flow"}
            elif "NO_WATER" in selected_symptoms:
                expected_topics = {"symptom_no_water"}
            else:
                expected_topics = {"symptom_no_water", "symptom_low_flow"}
            if target_water_type == "온수":
                expected_topics.add("symptom_hot_water_safety")
        return [
            chunk
            for chunk in candidates
            if self.canonical_topic(chunk) in expected_topics
        ]

    @classmethod
    def canonical_topic(cls, chunk: RetrievedChunk) -> str | None:
        value = canonical_v2_topic(chunk) if chunk.index_version == "2.0.0" else (
            chunk.topic_code or _canonical_topic_by_chunk_id().get(chunk.chunk_id)
        )
        return cls._TOPIC_ALIASES.get(value, value)

    @classmethod
    def _expected_topic(
        cls,
        *,
        symptom_type: str | None,
        target_water_type: str | None,
    ) -> str | None:
        if symptom_type == "온도 이상":
            return cls._TEMPERATURE_TOPIC_BY_WATER_TYPE.get(
                target_water_type or ""
            )
        return cls._TOPIC_BY_SYMPTOM_TYPE.get(symptom_type or "")
