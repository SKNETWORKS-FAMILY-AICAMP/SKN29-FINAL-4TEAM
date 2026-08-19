"""Backend 공식 Readonly View에서 3모델 50 Case를 검증한다."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import yaml

from ai.app.integrations.embedding.embedding_client import BgeM3EmbeddingClient
from ai.app.integrations.vector_store.vector_store import PgVectorStore
from ai.app.retrieval.filters.product_filter import ProductFilter
from ai.app.retrieval.indexing import IndexManifest, load_rag_handoff_profile
from ai.app.retrieval.models.retrieval_query import RetrievalQuery
from ai.app.retrieval.search.vector_search import VectorSearchService
from ai.evaluation.three_model_rag import (
    TOP_K,
    build_candidate_answerability_gate,
    diversify_evidence_groups,
    evaluate_three_model_cases,
    load_three_model_evaluation_inputs,
    product_generation_by_model,
)
from ai.scripts.export_three_model_canonical_identity import IDENTITY_PATH


EXPECTED_TABLE = "backend_ai_rag_chunks_v1"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _required_environment(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required for the readonly Runtime check")
    return value


def _prepared_product_filter() -> ProductFilter:
    policy = yaml.safe_load(
        (REPOSITORY_ROOT / "ai/configs/retrieval_policy.yaml").read_text(
            encoding="utf-8"
        )
    )["prepared_runtime_profiles"]["three_model"]
    if policy["activation_status"] != "PREPARED_NOT_ACTIVE":
        raise RuntimeError("Unexpected three-model preparation policy status")
    metadata = policy["metadata_filters"]
    return ProductFilter(
        allowed_generations=metadata["allowed_generations"],
        excluded_models=metadata["excluded_models"],
        target_models=metadata["target_models"],
    )


def _load_identity_and_manifest() -> tuple[dict, IndexManifest]:
    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
    manifest_path = REPOSITORY_ROOT / identity["required_index_manifest"]
    manifest = IndexManifest.load_manifest(str(manifest_path))
    if manifest is None:
        raise RuntimeError("The actual three-model index manifest is not available")
    if manifest.chunk_count != identity["chunk_count"]:
        raise RuntimeError("Identity and index manifest chunk counts differ")
    if manifest.chunk_set_sha256.upper() != identity["chunk_set_sha256"]:
        raise RuntimeError("Identity and index manifest chunk-set hashes differ")
    if manifest.index_version != identity["index_version"]:
        raise RuntimeError("Identity and index manifest versions differ")
    return identity, manifest


def _verify_runtime() -> None:
    table_name = _required_environment("AI_VECTOR_TABLE_NAME")
    if table_name != EXPECTED_TABLE:
        raise RuntimeError(f"AI_VECTOR_TABLE_NAME must be {EXPECTED_TABLE}")
    dsn = _required_environment("AI_VECTOR_DSN")
    model_revision = _required_environment("AI_EMBEDDING_REVISION")

    identity, manifest = _load_identity_and_manifest()
    if model_revision != manifest.model_revision:
        raise RuntimeError("Configured embedding revision differs from the index manifest")

    profile = load_rag_handoff_profile("rag-expansion")
    cases, groups, chunks = load_three_model_evaluation_inputs(profile)
    expected_ids = [chunk.chunk_id for chunk in chunks]
    if set(expected_ids) != {item["chunk_id"] for item in identity["chunks"]}:
        raise RuntimeError("Canonical identity and evaluation Child sets differ")

    generations = product_generation_by_model(chunks)
    model_candidate_counts = {
        model_code: sum(chunk.model_code == model_code for chunk in chunks)
        for model_code in generations
    }
    embedding = BgeM3EmbeddingClient(model_revision=model_revision)
    store = PgVectorStore(dsn, table_name=table_name)
    if store.count(expected_ids) != len(expected_ids):
        raise RuntimeError("The readonly View does not expose all 53 canonical Child rows")
    service = VectorSearchService(
        embedding,
        store,
        index_manifest=manifest,
        answerability_gate=build_candidate_answerability_gate(chunks),
        product_filter=_prepared_product_filter(),
    )

    def search(query: str, exact_sales_code: str, top_k: int):
        candidates = service.search(
            RetrievalQuery(
                query_text=query,
                model_code=exact_sales_code,
                product_generation=generations.get(exact_sales_code, "D"),
                top_k=model_candidate_counts.get(exact_sales_code, top_k),
                require_official_verified=True,
            )
        )
        return diversify_evidence_groups(candidates, top_k=top_k)

    results = evaluate_three_model_cases(cases, groups, search, top_k=TOP_K)
    summary = {
        "case_count": len(results),
        "passed_count": sum(result["passed"] for result in results),
        "positive_group_hit_count": sum(
            result["case_type"] == "POSITIVE" and result["expected_group_hit_at_5"]
            for result in results
        ),
        "negative_no_evidence_count": sum(
            result["case_type"] == "NEGATIVE" and result["no_evidence"]
            for result in results
        ),
        "cross_model_hit_count": sum(result["cross_model_hit_count"] for result in results),
        "direct_parent_hit_count": sum(result["direct_parent_hit_count"] for result in results),
        "unverified_evidence_hit_count": sum(
            result["unverified_evidence_hit_count"] for result in results
        ),
    }
    passed = summary == {
        "case_count": 50,
        "passed_count": 50,
        "positive_group_hit_count": 43,
        "negative_no_evidence_count": 7,
        "cross_model_hit_count": 0,
        "direct_parent_hit_count": 0,
        "unverified_evidence_hit_count": 0,
    }
    print(
        json.dumps(
            {
                "status": "PASS" if passed else "FAIL",
                "runtime_activation": "READY_FOR_JOINT_E2E" if passed else "HOLD",
                **summary,
            },
            ensure_ascii=False,
        )
    )
    if not passed:
        raise RuntimeError("The official readonly three-model Runtime gate failed")


def main() -> int:
    try:
        _verify_runtime()
    except Exception:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "runtime_activation": "HOLD",
                    "reason_code": "THREE_MODEL_READONLY_RUNTIME_REQUIREMENTS_NOT_MET",
                },
                ensure_ascii=False,
            )
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
