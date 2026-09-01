"""공개 MVP 7청크에서 증상·Top-K·후처리 결과를 재현한다."""

from __future__ import annotations

import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ai.app.integrations.embedding.embedding_client import BgeM3EmbeddingClient
from ai.app.retrieval import EvidenceApplicabilityGate, EvidenceTopicFilter
from ai.app.retrieval.filters.scenario_evidence_selector import (
    ScenarioEvidenceSelector,
)
from ai.app.retrieval.indexing.chunk_loader import ChunkLoader
from ai.app.retrieval.models.retrieval_query import RetrievalQuery
from ai.app.retrieval.query.context_builder import RetrievalContextBuilder
from ai.app.retrieval.search.vector_search import VectorSearchService
from ai.app.structuring import ProductSymptomDomainGuard, SymptomStructurer


MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
SCORE_THRESHOLD = 0.4
CASES = (
    ("물이 약해요", "냉수"),
    ("물이 약해요", "온수"),
    ("물이 약해요", "정수"),
    ("물이 약해요", "전체"),
    ("정수된 물에 미세한 입자가 발생해요", None),
    ("물에 이물질이 둥둥 떠다녀요", None),
    ("어제 시킨 치킨이 아직 안 왔어요", None),
)


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def main() -> None:
    chunks = ChunkLoader().load_verified_chunks()
    embedding = BgeM3EmbeddingClient(model_revision=MODEL_REVISION)
    chunk_vectors = embedding.embed_documents(chunk.content for chunk in chunks)
    expander = VectorSearchService(object(), object())
    rows = []

    for raw_symptom, target_water_type in CASES:
        previous_answers = (
            [
                {
                    "question_id": "followup-target-water-type",
                    "answer_text": target_water_type,
                }
            ]
            if target_water_type
            else []
        )
        selected = ["LOW_FLOW"] if target_water_type else ["OTHER"]
        symptom = SymptomStructurer().structure(
            raw_symptom,
            selected,
            previous_answers,
        )
        domain = ProductSymptomDomainGuard().evaluate(
            raw_symptom=raw_symptom,
            selected_symptoms=selected,
            structured_symptom=symptom,
        )
        query_text = RetrievalContextBuilder().build(
            raw_symptom=raw_symptom,
            structured_symptom=symptom,
        )

        ranked = []
        if domain.relevance != "OFF_DOMAIN":
            expanded = expander.expand_query(
                RetrievalQuery(
                    query_text=query_text,
                    model_code="WPUJAC104DWH",
                )
            ).expanded_query
            query_vector = embedding.embed_query(expanded)
            ranked = sorted(
                (
                    chunk.model_copy(
                        update={"similarity_score": _dot(query_vector, vector)}
                    )
                    for chunk, vector in zip(chunks, chunk_vectors)
                ),
                key=lambda chunk: (-chunk.similarity_score, chunk.chunk_id),
            )
            ranked = [
                chunk
                for chunk in ranked
                if chunk.similarity_score >= SCORE_THRESHOLD
            ][:5]

        topic_filtered = EvidenceTopicFilter().filter_chunks(
            ranked,
            symptom_type=symptom.symptom_type,
            target_water_type=symptom.target_water_type,
        )
        applicability_gate = EvidenceApplicabilityGate()
        applicability = applicability_gate.classify_for_symptom(
            symptom_type=symptom.symptom_type,
            previous_answers=previous_answers,
        )
        applicable = applicability_gate.filter_chunks(
            topic_filtered,
            symptom_type=symptom.symptom_type,
            applicability=applicability,
        )
        selected_chunks = list(
            ScenarioEvidenceSelector()
            .select_chunks(
                applicable,
                structured_symptom=symptom,
                raw_symptom=raw_symptom,
                applicability=applicability,
            )
            .chunks
        )
        action = (
            "OFF_DOMAIN"
            if domain.relevance == "OFF_DOMAIN"
            else "SELF_CARE"
            if selected_chunks
            else "CONSULTATION"
        )
        rows.append(
            {
                "input": raw_symptom,
                "normalized_symptom": symptom.symptom_type,
                "target_water_type": symptom.target_water_type,
                "domain_relevance": domain.relevance,
                "retrieval_query": query_text,
                "top_5": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "score": round(chunk.similarity_score, 6),
                    }
                    for chunk in ranked
                ],
                "post_topic_filter": [chunk.chunk_id for chunk in topic_filtered],
                "post_applicability_filter": [chunk.chunk_id for chunk in applicable],
                "final_evidence": [chunk.chunk_id for chunk in selected_chunks],
                "retrieval_outcome": "AVAILABLE" if selected_chunks else "NO_MATCH",
                "final_action": action,
            }
        )

    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
