"""구조화 증상과 공식 근거 주제의 결정적 선별 경계."""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable

from ..indexing.chunk_loader import ChunkLoader
from ..models.retrieved_chunk import RetrievedChunk


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

    def filter_chunks(
        self,
        chunks: Iterable[RetrievedChunk],
        *,
        symptom_type: str | None,
        target_water_type: str | None = None,
    ) -> list[RetrievedChunk]:
        candidates = list(chunks)
        expected_topic = self._expected_topic(
            symptom_type=symptom_type,
            target_water_type=target_water_type,
        )
        if expected_topic is None:
            return candidates

        canonical_topics = _canonical_topic_by_chunk_id()
        return [
            chunk
            for chunk in candidates
            if (chunk.topic_code or canonical_topics.get(chunk.chunk_id))
            == expected_topic
        ]

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
