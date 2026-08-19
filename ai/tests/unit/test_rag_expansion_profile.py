"""3모델 rag-expansion Consumer Profile의 AI 소비 경계 테스트."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from ai.app.common.candidate_vector_index import (
    RAG_EXPANSION_TABLE,
    assert_rag_expansion_candidate_target,
)
from ai.app.retrieval.indexing import ChunkLoader, load_rag_handoff_profile
from ai.evaluation.three_model_rag import (
    acceptance_contract_blockers,
    build_candidate_answerability_gate,
    diversify_evidence_groups,
    evaluate_three_model_cases,
    load_three_model_evaluation_inputs,
    product_generation_by_model,
)
from ai.scripts.build_vector_index import _manifest_path


def test_rag_expansion_profile_loads_only_53_search_children() -> None:
    profile = load_rag_handoff_profile("rag-expansion")
    chunks = ChunkLoader.from_handoff_profile("rag-expansion").load_verified_chunks()

    assert profile.candidate_only is True
    assert profile.required_pre_score_filter == "exact_sales_code"
    assert profile.expected_counts == {
        "parents": 15,
        "children": 53,
        "evidence_groups": 43,
        "evaluation_cases": 50,
    }
    assert len(chunks) == 53
    assert Counter(chunk.model_code for chunk in chunks) == {
        "WPUJAC104DWH": 15,
        "WPUIAC425SNW": 19,
        "WPUIAC606SNW": 19,
    }
    assert len({chunk.evidence_group_id for chunk in chunks}) == 43
    assert all(chunk.retrieval_role == "SEARCH_CANDIDATE" for chunk in chunks)
    assert all(chunk.dataset_profile == "rag-expansion" for chunk in chunks)
    assert all(chunk.allowed_use for chunk in chunks)
    assert not any(chunk.runtime_eligible for chunk in chunks)
    assert product_generation_by_model(chunks) == {
        "WPUJAC104DWH": "D",
        "WPUIAC425SNW": "IAC425",
        "WPUIAC606SNW": "IAC606",
    }


def test_rag_expansion_evaluation_contract_consumes_all_50_cases() -> None:
    profile = load_rag_handoff_profile("rag-expansion")
    cases, groups, chunks = load_three_model_evaluation_inputs(profile)
    child_by_group = {}
    for chunk in chunks:
        child_by_group.setdefault(chunk.evidence_group_id, chunk)
    case_by_query = {case["query"]: case for case in cases}

    def search(query: str, exact_sales_code: str, top_k: int):
        assert top_k == 5
        case = case_by_query[query]
        if case["expected_no_evidence"]:
            return []
        chunk = child_by_group[case["expected_evidence_group_ids"][0]]
        assert chunk.model_code == exact_sales_code
        return [chunk]

    results = evaluate_three_model_cases(cases, groups, search)

    assert len(results) == 50
    assert sum(row["case_type"] == "POSITIVE" for row in results) == 43
    assert sum(row["case_type"] == "NEGATIVE" for row in results) == 7
    assert sum(row["expected_group_hit_at_5"] for row in results) == 43
    assert sum(row["no_evidence"] for row in results) == 7
    assert sum(row["cross_model_hit_count"] for row in results) == 0
    assert all(row["passed"] for row in results)
    assert all(
        row["expected_group_rank_at_5"] == 1
        for row in results
        if row["case_type"] == "POSITIVE"
    )


def test_dense_results_are_diversified_by_evidence_group() -> None:
    chunks = ChunkLoader.from_handoff_profile("rag-expansion").load_verified_chunks()
    repeated_group = next(
        group_id
        for group_id in {chunk.evidence_group_id for chunk in chunks}
        if sum(chunk.evidence_group_id == group_id for chunk in chunks) > 1
    )
    repeated = [chunk for chunk in chunks if chunk.evidence_group_id == repeated_group]
    other = next(chunk for chunk in chunks if chunk.evidence_group_id != repeated_group)

    diversified = diversify_evidence_groups([*repeated, other], top_k=2)

    assert diversified == [repeated[0], other]


def test_candidate_gate_reuses_approved_rules_without_blocking_positive_models() -> None:
    profile = load_rag_handoff_profile("rag-expansion")
    cases, _, chunks = load_three_model_evaluation_inputs(profile)
    gate = build_candidate_answerability_gate(chunks)
    generations = product_generation_by_model(chunks)

    for case in (row for row in cases if row["case_type"] == "POSITIVE"):
        decision = gate.evaluate(
            query_text=case["query"],
            model_code=case["exact_sales_code"],
            product_generation=generations[case["exact_sales_code"]],
        )
        assert decision.blocked is False, case["case_id"]

    unsupported_feature = next(
        row
        for row in cases
        if row.get("negative_reason") == "UNSUPPORTED_FEATURE_FOR_MODEL"
    )
    decision = gate.evaluate(
        query_text=unsupported_feature["query"],
        model_code=unsupported_feature["exact_sales_code"],
        product_generation=generations[unsupported_feature["exact_sales_code"]],
    )
    assert decision.execution_path == "POLICY_BLOCK_UNSUPPORTED_CAPABILITY"


def test_group_level_top5_and_unregistered_model_contract_have_no_blocker() -> None:
    profile = load_rag_handoff_profile("rag-expansion")
    cases, groups, _ = load_three_model_evaluation_inputs(profile)

    assert acceptance_contract_blockers(profile, groups, cases) == []


def test_cross_model_result_fails_even_when_similarity_result_exists() -> None:
    profile = load_rag_handoff_profile("rag-expansion")
    cases, groups, chunks = load_three_model_evaluation_inputs(profile)
    case = next(row for row in cases if row["case_type"] == "POSITIVE")
    wrong_model = next(
        chunk for chunk in chunks if chunk.model_code != case["exact_sales_code"]
    )

    results = evaluate_three_model_cases(
        [case],
        groups,
        lambda query, exact_sales_code, top_k: [wrong_model],
    )

    assert results[0]["passed"] is False
    assert results[0]["cross_model_hit_count"] == 1


def test_parent_or_unknown_retrieval_role_cannot_pass_as_direct_evidence() -> None:
    profile = load_rag_handoff_profile("rag-expansion")
    cases, groups, chunks = load_three_model_evaluation_inputs(profile)
    case = next(row for row in cases if row["case_type"] == "POSITIVE")
    child = next(
        row
        for row in chunks
        if row.evidence_group_id == case["expected_evidence_group_ids"][0]
    )
    parent_projection = child.model_copy(update={"retrieval_role": "CONTEXT_ONLY"})

    result = evaluate_three_model_cases(
        [case],
        groups,
        lambda query, exact_sales_code, top_k: [parent_projection],
    )[0]

    assert result["expected_group_hit_at_5"] is True
    assert result["direct_parent_hit_count"] == 1
    assert result["passed"] is False


def test_rag_expansion_candidate_target_requires_separate_table_and_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AI_VECTOR_DISPOSABLE_CONFIRM", raising=False)
    with pytest.raises(RuntimeError, match="전용 Table"):
        assert_rag_expansion_candidate_target("protected", "ai_rag_chunks")
    with pytest.raises(RuntimeError, match="DISPOSABLE_ONLY"):
        assert_rag_expansion_candidate_target("protected", RAG_EXPANSION_TABLE)


def test_rag_expansion_manifest_does_not_overwrite_runtime_manifest(tmp_path: Path) -> None:
    assert _manifest_path(tmp_path, "rag") == tmp_path / "ai/configs/index_manifest.json"
    assert _manifest_path(tmp_path, "rag-expansion") == (
        tmp_path / ".runtime/rag-expansion/index_manifest.json"
    )
