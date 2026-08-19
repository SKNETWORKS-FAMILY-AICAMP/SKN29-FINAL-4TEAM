"""rag-expansion 53 Child를 적재한 Candidate pgvector에서 50 Case를 평가한다."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from ai.app.common.candidate_vector_index import (
    RAG_EXPANSION_PROFILE,
    RAG_EXPANSION_TABLE,
    assert_rag_expansion_candidate_target,
)
from ai.app.integrations.embedding.embedding_client import BgeM3EmbeddingClient
from ai.app.integrations.vector_store.vector_store import PgVectorStore
from ai.app.retrieval.indexing import IndexManifest, load_rag_handoff_profile
from ai.app.retrieval.verification.model_capability_gate import ModelCapabilityGate
from ai.evaluation.three_model_rag import (
    TOP_K,
    acceptance_contract_blockers,
    build_candidate_answerability_gate,
    diversify_evidence_groups,
    evaluate_three_model_cases,
    load_three_model_evaluation_inputs,
    product_generation_by_model,
)
from ai.scripts.build_vector_index import _chunk_set_sha256


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def expansion_manifest_path(repository_root: Path | None = None) -> Path:
    root = repository_root or _repository_root()
    return root / ".runtime" / "rag-expansion" / "index_manifest.json"


def expansion_report_path(repository_root: Path | None = None) -> Path:
    root = repository_root or _repository_root()
    return root / ".runtime" / "rag-expansion" / "evaluation_report.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="3모델 RAG Candidate pgvector 평가")
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="DB·Embedding 없이 53/43/50 Lineage와 평가 계약만 확인",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    profile = load_rag_handoff_profile(RAG_EXPANSION_PROFILE)
    cases, groups, expected_chunks = load_three_model_evaluation_inputs(profile)
    generation_by_model = product_generation_by_model(expected_chunks)
    candidate_gate = build_candidate_answerability_gate(expected_chunks)
    model_capability_gate = ModelCapabilityGate()
    missing_capability_models = set(generation_by_model) - set(
        model_capability_gate.registered_model_codes
    )
    if missing_capability_models:
        raise RuntimeError(
            "rag-expansion 모델 Capability 설정이 누락됐습니다: "
            f"{sorted(missing_capability_models)}"
        )
    blockers = acceptance_contract_blockers(profile, groups, cases, top_k=TOP_K)
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "preflight_status": "BLOCKED" if blockers else "READY",
                    "profile": profile.name,
                    "child_count": len(expected_chunks),
                    "evidence_group_count": len(groups),
                    "evaluation_case_count": len(cases),
                    "exact_sales_code_pre_score_filter": (
                        profile.required_pre_score_filter == "exact_sales_code"
                    ),
                    "runtime_activation": "NOT_APPROVED",
                    "acceptance_contract_blockers": blockers,
                },
                ensure_ascii=False,
            )
        )
        return

    dsn = os.getenv("AI_VECTOR_DSN")
    model_revision = os.getenv("AI_EMBEDDING_REVISION")
    table_name = os.getenv("AI_VECTOR_TABLE_NAME", "")
    if not dsn or not model_revision:
        raise RuntimeError("AI_VECTOR_DSN과 AI_EMBEDDING_REVISION이 필요합니다.")
    assert_rag_expansion_candidate_target(dsn, table_name)

    manifest_path = expansion_manifest_path()
    manifest = IndexManifest.load_manifest(str(manifest_path))
    if manifest is None:
        raise RuntimeError("rag-expansion Candidate Index Manifest가 없습니다.")
    if manifest.chunk_count != len(expected_chunks):
        raise RuntimeError("rag-expansion Manifest의 Child 수가 인계 Profile과 다릅니다.")
    if manifest.chunk_set_sha256 != _chunk_set_sha256(expected_chunks):
        raise RuntimeError("rag-expansion Manifest의 Child 집합 Hash가 인계 데이터와 다릅니다.")

    embedding = BgeM3EmbeddingClient(model_revision=model_revision)
    if manifest.model_revision != embedding.model_revision:
        raise RuntimeError("Embedding Revision과 Candidate Manifest가 다릅니다.")
    store = PgVectorStore(dsn, table_name=RAG_EXPANSION_TABLE)
    if store.count([chunk.chunk_id for chunk in expected_chunks]) != len(expected_chunks):
        raise RuntimeError("rag-expansion Candidate 53건이 모두 적재되지 않았습니다.")

    model_candidate_counts = {
        model_code: sum(chunk.model_code == model_code for chunk in expected_chunks)
        for model_code in generation_by_model
    }
    trace_by_query: dict[tuple[str, str], dict[str, object]] = {}

    def raw_search(query: str, exact_sales_code: str, top_k: int):
        vector = embedding.embed_query(query)
        return store.search(
            vector,
            model_code=exact_sales_code,
            product_generation=generation_by_model.get(exact_sales_code, "D"),
            top_k=top_k,
        )

    def search(query: str, exact_sales_code: str, top_k: int):
        model_decision = model_capability_gate.evaluate(
            query_text=query,
            model_code=exact_sales_code,
        )
        if model_decision.blocked:
            trace_by_query[(query, exact_sales_code)] = {
                "execution_path": model_decision.execution_path,
                "applied_policy_id": model_decision.policy_id,
                "applied_rule_id": model_decision.rule_id,
                "block_reason": model_decision.reason_code,
                "search_executed": False,
            }
            return []
        decision = candidate_gate.evaluate(
            query_text=query,
            model_code=exact_sales_code,
            product_generation=generation_by_model.get(exact_sales_code, "D"),
        )
        if decision.blocked:
            trace_by_query[(query, exact_sales_code)] = {
                "execution_path": decision.execution_path,
                "applied_policy_id": decision.policy_id,
                "applied_rule_id": decision.rule_id,
                "block_reason": decision.category,
                "search_executed": False,
            }
            return []
        trace_by_query[(query, exact_sales_code)] = {
            "execution_path": "PGVECTOR_QUERY",
            "applied_policy_id": None,
            "applied_rule_id": None,
            "block_reason": None,
            "search_executed": True,
        }
        dense_candidates = raw_search(
            query,
            exact_sales_code,
            model_candidate_counts.get(exact_sales_code, top_k),
        )
        return diversify_evidence_groups(dense_candidates, top_k=top_k)

    results = evaluate_three_model_cases(cases, groups, search, top_k=TOP_K)
    for case, result in zip(cases, results, strict=True):
        result.update(trace_by_query[(case["query"], case["exact_sales_code"])])
    failed_positive_diagnostics = []
    result_by_case_id = {result["case_id"]: result for result in results}
    for case in cases:
        result = result_by_case_id[case["case_id"]]
        if case["case_type"] != "POSITIVE" or result["passed"]:
            continue
        diagnostic_chunks = list(
            raw_search(
                case["query"],
                case["exact_sales_code"],
                model_candidate_counts[case["exact_sales_code"]],
            )
        )
        expected_groups = set(case["expected_evidence_group_ids"])
        expected_rank = next(
            (
                rank
                for rank, chunk in enumerate(diagnostic_chunks, start=1)
                if chunk.evidence_group_id in expected_groups
            ),
            None,
        )
        seen_groups: set[str] = set()
        expected_unique_group_rank = None
        for chunk in diagnostic_chunks:
            group_id = chunk.evidence_group_id
            if not group_id or group_id in seen_groups:
                continue
            seen_groups.add(group_id)
            if group_id in expected_groups:
                expected_unique_group_rank = len(seen_groups)
                break
        expected_score = next(
            (
                round(chunk.similarity_score, 6)
                for chunk in diagnostic_chunks
                if chunk.evidence_group_id in expected_groups
            ),
            None,
        )
        failed_positive_diagnostics.append(
            {
                "case_id": case["case_id"],
                "model_code": case["exact_sales_code"],
                "expected_group_rank": expected_rank,
                "expected_unique_group_rank": expected_unique_group_rank,
                "expected_group_score": expected_score,
                "candidate_count_above_threshold": len(diagnostic_chunks),
            }
        )
    all_case_passed = all(result["passed"] for result in results)
    if blockers:
        status = "BLOCKED_ACCEPTANCE_CONTRACT"
    else:
        status = "PASS" if all_case_passed else "FAIL"
    report = {
        "verification_status": status,
        "profile": profile.name,
        "runtime_activation": "NOT_APPROVED",
        "candidate_table": RAG_EXPANSION_TABLE,
        "exact_sales_code_pre_score_filter": True,
        "top_k": TOP_K,
        "acceptance_contract_blockers": blockers,
        "summary": {
            "case_count": len(results),
            "passed_count": sum(result["passed"] for result in results),
            "failed_count": sum(not result["passed"] for result in results),
            "positive_group_hit_count": sum(
                result["case_type"] == "POSITIVE"
                and result["expected_group_hit_at_5"]
                for result in results
            ),
            "negative_no_evidence_count": sum(
                result["case_type"] == "NEGATIVE" and result["no_evidence"]
                for result in results
            ),
            "cross_model_hit_count": sum(
                result["cross_model_hit_count"] for result in results
            ),
            "direct_parent_hit_count": sum(
                result["direct_parent_hit_count"] for result in results
            ),
            "unverified_evidence_hit_count": sum(
                result["unverified_evidence_hit_count"] for result in results
            ),
            "pgvector_search_executed_count": sum(
                bool(result["search_executed"]) for result in results
            ),
            "pre_search_blocked_count": sum(
                not bool(result["search_executed"]) for result in results
            ),
        },
        "failed_positive_diagnostics": failed_positive_diagnostics,
        "cases": results,
    }
    report_path = expansion_report_path()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "verification_status": status,
                "runtime_activation": "NOT_APPROVED",
                "acceptance_contract_blockers": blockers,
                **report["summary"],
                "report_path": str(report_path.relative_to(_repository_root())),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
