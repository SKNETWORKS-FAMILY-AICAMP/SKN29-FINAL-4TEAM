"""3모델 RAG Expansion의 평가 계약과 검색 결과 판정."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from ai.app.retrieval.indexing import ChunkLoader, RagHandoffProfile
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk
from ai.app.retrieval.verification.answerability_capability_gate import (
    AnswerabilityCapabilityGate,
)


TOP_K = 5


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def product_generation_by_model(
    chunks: Sequence[RetrievedChunk],
) -> dict[str, str]:
    """판매코드별로 정확히 하나인 제품 세대를 Candidate Child에서 파생한다."""

    generations: dict[str, set[str]] = {}
    for chunk in chunks:
        if not chunk.model_code:
            raise ValueError("rag-expansion Child에 정확 판매코드가 없습니다.")
        generations.setdefault(chunk.model_code, set()).add(chunk.product_generation)
    ambiguous = {
        model_code: sorted(values)
        for model_code, values in generations.items()
        if len(values) != 1
    }
    if ambiguous:
        raise ValueError("rag-expansion 판매코드별 제품 세대가 유일하지 않습니다.")
    return {
        model_code: next(iter(values))
        for model_code, values in generations.items()
    }


def diversify_evidence_groups(
    chunks: Sequence[RetrievedChunk],
    *,
    top_k: int = TOP_K,
) -> list[RetrievedChunk]:
    """Dense 순위를 보존하며 Evidence Group당 최고 Child 하나만 Top-K에 남긴다."""

    selected: list[RetrievedChunk] = []
    seen_groups: set[str] = set()
    for chunk in chunks:
        group_key = chunk.evidence_group_id or f"CHILD:{chunk.chunk_id}"
        if group_key in seen_groups:
            continue
        seen_groups.add(group_key)
        selected.append(chunk)
        if len(selected) == top_k:
            break
    return selected


def build_candidate_answerability_gate(
    chunks: Sequence[RetrievedChunk],
) -> AnswerabilityCapabilityGate:
    """기존 정책 규칙은 보존하고 Candidate 모델·세대 범위만 격리 확장한다."""

    base_gate = AnswerabilityCapabilityGate()
    definition = deepcopy(base_gate.definition)
    definition["policy_id"] = "ANSWERABILITY_CAPABILITY_GATE_RAG_EXPANSION_CANDIDATE_V1"
    definition["supported_model_codes"] = sorted(
        {chunk.model_code for chunk in chunks if chunk.model_code}
    )
    definition["supported_generations"] = sorted(
        {chunk.product_generation for chunk in chunks}
    )
    return AnswerabilityCapabilityGate(definition=definition)


def load_three_model_evaluation_inputs(
    profile: RagHandoffProfile,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[RetrievedChunk]]:
    """Profile이 가리키는 50 Case·43 Group·53 Child를 함께 검증한다."""

    if profile.name != "rag-expansion" or not profile.candidate_only:
        raise ValueError("3모델 평가는 rag-expansion Candidate Profile만 지원합니다.")
    if profile.evaluation_path is None or profile.evidence_groups_path is None:
        raise ValueError("rag-expansion 평가 계약 또는 Evidence Group 입력이 없습니다.")
    if profile.required_pre_score_filter != "exact_sales_code":
        raise ValueError("3모델 평가는 exact_sales_code 선필터 계약이 필요합니다.")

    contract = json.loads(profile.evaluation_path.read_text(encoding="utf-8"))
    cases = contract["cases"]
    group_rows = _read_jsonl(profile.evidence_groups_path)
    groups = {row["evidence_group_id"]: row for row in group_rows}
    chunks = ChunkLoader.from_handoff_profile(profile.name).load_verified_chunks()

    expected = profile.expected_counts
    actual_counts = {
        "children": len(chunks),
        "evidence_groups": len(groups),
        "evaluation_cases": len(cases),
    }
    for key, actual in actual_counts.items():
        if key in expected and expected[key] != actual:
            raise ValueError(
                f"rag-expansion {key} 수가 Profile과 다릅니다: "
                f"expected={expected[key]}, actual={actual}"
            )
    if len(groups) != len(group_rows):
        raise ValueError("rag-expansion Evidence Group ID가 중복됐습니다.")
    if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
        raise ValueError("rag-expansion Child ID가 중복됐습니다.")

    child_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    for group_id, group in groups.items():
        child_ids = group["child_ids"]
        variant_ids = group["source_variant_ids"]
        if len(child_ids) != len(variant_ids):
            raise ValueError(f"Evidence Group의 Child·Variant 수가 다릅니다: {group_id}")
        for child_id, variant_id in zip(child_ids, variant_ids, strict=True):
            child = child_by_id.get(child_id)
            if child is None:
                raise ValueError(f"Evidence Group이 알 수 없는 Child를 참조합니다: {group_id}")
            if child.evidence_group_id != group_id or child.source_variant_id != variant_id:
                raise ValueError(f"Child와 Evidence Group Lineage가 다릅니다: {group_id}")
            if child.model_code != group["exact_sales_code"]:
                raise ValueError(f"Child와 Evidence Group 판매코드가 다릅니다: {group_id}")

    for case in cases:
        expected_groups = case["expected_evidence_group_ids"]
        if case["case_type"] == "POSITIVE" and not expected_groups:
            raise ValueError(f"정상 Case에 기대 Evidence Group이 없습니다: {case['case_id']}")
        if any(group_id not in groups for group_id in expected_groups):
            raise ValueError(f"평가 Case가 알 수 없는 Evidence Group을 참조합니다: {case['case_id']}")
    return cases, groups, chunks


def acceptance_contract_blockers(
    profile: RagHandoffProfile,
    groups: dict[str, dict[str, Any]],
    cases: Sequence[dict[str, Any]],
    *,
    top_k: int = TOP_K,
) -> list[str]:
    """현재 데이터만으로 만족 불가능한 평가 계약을 실행 전에 표시한다."""

    if profile.evaluation_path is None:
        return ["EVALUATION_CONTRACT_MISSING"]
    contract = json.loads(profile.evaluation_path.read_text(encoding="utf-8"))
    positive_policy = str(contract.get("retrieval_acceptance", {}).get("positive", ""))
    blockers: list[str] = []
    expected_group_ids = {
        group_id
        for case in cases
        if case["case_type"] == "POSITIVE"
        for group_id in case["expected_evidence_group_ids"]
    }
    if (
        "모든 Source Variant" in positive_policy
        and any(
            len(groups[group_id]["source_variant_ids"]) > top_k
            for group_id in expected_group_ids
        )
    ):
        blockers.append("ALL_SOURCE_VARIANTS_EXCEED_TOP_K")
    negative_reasons = {
        str(case.get("negative_reason", ""))
        for case in cases
        if case["case_type"] == "NEGATIVE"
    }
    if not negative_reasons.intersection(
        {
            "UNKNOWN_MODEL",
            "NONEXISTENT_MODEL",
            "UNREGISTERED_EXACT_SALES_CODE",
        }
    ):
        blockers.append("NONEXISTENT_MODEL_NEGATIVE_CASE_MISSING")
    return blockers


def evaluate_three_model_cases(
    cases: Sequence[dict[str, Any]],
    groups: dict[str, dict[str, Any]],
    search: Callable[[str, str, int], Sequence[RetrievedChunk]],
    *,
    top_k: int = TOP_K,
) -> list[dict[str, Any]]:
    """질의 본문을 결과에 남기지 않고 Group Hit·교차 모델·No Evidence를 판정한다."""

    results: list[dict[str, Any]] = []
    for case in cases:
        chunks = list(search(case["query"], case["exact_sales_code"], top_k))
        returned_groups = [chunk.evidence_group_id for chunk in chunks if chunk.evidence_group_id]
        returned_variants = [chunk.source_variant_id for chunk in chunks if chunk.source_variant_id]
        expected_groups = set(case["expected_evidence_group_ids"])
        expected_variants = {
            variant_id
            for group_id in expected_groups
            for variant_id in groups[group_id]["source_variant_ids"]
        }
        cross_model_hits = sum(
            chunk.model_code != case["exact_sales_code"] for chunk in chunks
        )
        forbidden_hits = sum(
            chunk.model_code in set(case["forbidden_model_codes"]) for chunk in chunks
        )
        group_hit = bool(expected_groups.intersection(returned_groups))
        expected_group_rank = next(
            (
                rank
                for rank, group_id in enumerate(returned_groups, start=1)
                if group_id in expected_groups
            ),
            None,
        )
        no_evidence = not chunks
        unverified_evidence_hits = sum(
            chunk.verification_status != "official_verified" or not chunk.allowed_use
            for chunk in chunks
        )
        direct_parent_hits = sum(
            chunk.retrieval_role != "SEARCH_CANDIDATE" for chunk in chunks
        )
        if case["expected_no_evidence"]:
            passed = (
                no_evidence
                and cross_model_hits == 0
                and forbidden_hits == 0
                and unverified_evidence_hits == 0
                and direct_parent_hits == 0
            )
        else:
            passed = (
                group_hit
                and cross_model_hits == 0
                and forbidden_hits == 0
                and unverified_evidence_hits == 0
                and direct_parent_hits == 0
            )
        results.append(
            {
                "case_id": case["case_id"],
                "case_type": case["case_type"],
                "exact_sales_code": case["exact_sales_code"],
                "result_count": len(chunks),
                "top_similarity_score": (
                    round(chunks[0].similarity_score, 6) if chunks else None
                ),
                "expected_group_hit_at_5": group_hit,
                "expected_group_rank_at_5": expected_group_rank,
                "all_source_variants_hit_at_5": expected_variants.issubset(
                    set(returned_variants)
                ),
                "expected_no_evidence": case["expected_no_evidence"],
                "no_evidence": no_evidence,
                "cross_model_hit_count": cross_model_hits,
                "cross_model_document_retrieved": cross_model_hits > 0,
                "forbidden_hit_count": forbidden_hits,
                "unverified_evidence_hit_count": unverified_evidence_hits,
                "direct_parent_hit_count": direct_parent_hits,
                "passed": passed,
            }
        )
    return results
