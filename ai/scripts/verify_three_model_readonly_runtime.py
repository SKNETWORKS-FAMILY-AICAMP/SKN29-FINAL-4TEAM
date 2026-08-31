"""Backend 공식 Readonly View에서 3모델 50 Case를 검증한다."""

from __future__ import annotations

import json
from hashlib import sha256
import os
import sys
from pathlib import Path

from ai.app.integrations.embedding.embedding_client import BgeM3EmbeddingClient
from ai.app.integrations.vector_store.vector_store import PgVectorStore
from ai.app.retrieval.filters.product_filter import ProductFilter
from ai.app.retrieval.indexing import IndexManifest, load_rag_handoff_profile
from ai.app.retrieval.runtime_profile import (
    RagRuntimeProfile,
    load_runtime_retrieval_policy,
    resolve_rag_runtime_profile,
    validate_runtime_manifest,
)
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
from ai.scripts.verify_jac104_v2_recovery import _read_index_rows
from ai.app.retrieval.verification.index_readiness import validate_readonly_index
from ai.evaluation.release_evidence import (
    execution_blockers, execution_provenance, execution_source_changed,
    json_sha256, text_file_sha256, write_report,
)
from ai.evaluation.readonly_environment import read_database_versions


EXPECTED_TABLE = "backend_ai_rag_chunks_v1"


def _required_environment(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required for the readonly Runtime check")
    return value


def _integration_product_filter(profile: RagRuntimeProfile) -> ProductFilter:
    policy = load_runtime_retrieval_policy(profile)
    metadata = policy.metadata_filters
    return ProductFilter(
        allowed_generations=metadata["allowed_generations"],
        excluded_models=metadata["excluded_models"],
        target_models=metadata["target_models"],
    )


def _load_identity_and_manifest(
    profile: RagRuntimeProfile,
) -> tuple[dict, IndexManifest]:
    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
    manifest = IndexManifest.load_manifest(str(profile.manifest_path))
    if manifest is None:
        raise RuntimeError("The actual three-model index manifest is not available")
    validate_runtime_manifest(profile, manifest)
    if manifest.chunk_count != identity["chunk_count"]:
        raise RuntimeError("Identity and index manifest chunk counts differ")
    if manifest.chunk_set_sha256.upper() != identity["chunk_set_sha256"]:
        raise RuntimeError("Identity and index manifest chunk-set hashes differ")
    if manifest.index_version != identity["index_version"]:
        raise RuntimeError("Identity and index manifest versions differ")
    return identity, manifest


def _verify_runtime() -> dict:
    runtime_profile = resolve_rag_runtime_profile()
    if runtime_profile.name != "three_model_integration":
        raise RuntimeError(
            "AI_RAG_RUNTIME_PROFILE must be three_model_integration"
        )
    table_name = _required_environment("AI_VECTOR_TABLE_NAME")
    if table_name != EXPECTED_TABLE:
        raise RuntimeError(f"AI_VECTOR_TABLE_NAME must be {EXPECTED_TABLE}")
    dsn = _required_environment("AI_VECTOR_DSN")
    model_revision = _required_environment("AI_EMBEDDING_REVISION")

    identity, manifest = _load_identity_and_manifest(runtime_profile)
    if model_revision != manifest.model_revision:
        raise RuntimeError("Configured embedding revision differs from the index manifest")

    handoff_profile = load_rag_handoff_profile("rag-expansion")
    cases, groups, chunks = load_three_model_evaluation_inputs(handoff_profile)
    expected_ids = [chunk.chunk_id for chunk in chunks]
    if set(expected_ids) != {item["chunk_id"] for item in identity["chunks"]}:
        raise RuntimeError("Canonical identity and evaluation Child sets differ")

    generations = product_generation_by_model(chunks)
    model_candidate_counts = {
        model_code: sum(chunk.model_code == model_code for chunk in chunks)
        for model_code in generations
    }
    rows = _read_index_rows(dsn, maximum_rows=manifest.chunk_count + 1)
    index_identity = validate_readonly_index(runtime_profile, manifest, identity, rows)
    database_versions = read_database_versions(dsn)
    embedding = BgeM3EmbeddingClient(model_revision=model_revision)
    store = PgVectorStore(dsn, table_name=table_name)
    embedding.warmup()
    service = VectorSearchService(
        embedding,
        store,
        index_manifest=manifest,
        answerability_gate=build_candidate_answerability_gate(chunks),
        product_filter=_integration_product_filter(runtime_profile),
    )

    evidence_runs = []

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
        selected = diversify_evidence_groups(candidates, top_k=top_k)
        evidence_runs.append([
            {"chunk_id": chunk.chunk_id, "evidence_group_id": chunk.evidence_group_id,
             "source_hash": chunk.source_hash, "index_version": chunk.index_version,
             "chunk_set_sha256": chunk.chunk_set_sha256,
             "content_sha256": sha256(chunk.content.encode("utf-8")).hexdigest()} for chunk in selected
        ])
        return selected

    results = evaluate_three_model_cases(cases, groups, search, top_k=TOP_K)
    for result, evidence in zip(results, evidence_runs, strict=True):
        result["evidence"] = evidence
        result["result_sha256"] = json_sha256(result)
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
    return {
        "status": "PASS" if passed else "FAIL",
        "activation_scope": "INTEGRATION_VERIFICATION_ONLY",
        "public_runtime_activation": "HOLD", "backend_writes": 0,
        "runtime_profile": runtime_profile.name,
        "embedding_model": manifest.model_name, "embedding_revision": model_revision,
        "database_versions": database_versions,
        "generation_model": None, "prompt_version": None,
        "evaluation_file_sha256": text_file_sha256(handoff_profile.evaluation_path),
        "index_identity": index_identity, "case_results": results, **summary,
    }


def main(output_path: Path | None = None, expected_sha: str | None = None) -> int:
    provenance = execution_provenance()
    blockers = execution_blockers(provenance, expected_sha)
    try:
        if expected_sha and blockers:
            raise RuntimeError("Final execution provenance requirements not met")
        report = _verify_runtime()
        after = execution_provenance()
        report["end_provenance"] = after
        report["end_final_sha_blockers"] = execution_blockers(after, expected_sha)
        source_changed = execution_source_changed(provenance, after)
        if source_changed or (expected_sha and report["end_final_sha_blockers"]):
            report.update(status="HOLD", reason_code="EXECUTION_SOURCE_CHANGED")
    except Exception:
        report = {
            "status": "HOLD", "case_count": 50, "executed_case_count": None,
            "activation_scope": "INTEGRATION_VERIFICATION_ONLY",
            "public_runtime_activation": "HOLD", "backend_writes": 0,
            "reason_code": "THREE_MODEL_READONLY_RUNTIME_REQUIREMENTS_NOT_MET",
        }
    report.update(provenance=provenance, final_sha_blockers=blockers)
    report["final_sha_eligible"] = (
        report["status"] == "PASS" and not blockers
        and not report.get("end_final_sha_blockers", ["EXECUTION_NOT_COMPLETED"])
    )
    if output_path is not None:
        write_report(output_path, report)
    print(json.dumps({key: value for key, value in report.items()
                      if key not in {"case_results", "provenance", "end_provenance"}}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expected-sha")
    args = parser.parse_args()
    sys.exit(main(args.output, args.expected_sha))
