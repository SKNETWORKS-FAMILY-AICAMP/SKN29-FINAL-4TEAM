"""Gold v2 Evidence Group retrieval scoring shared by Full B1 and Playground.

The scorer deliberately treats Gold evidence groups as semantic answer units and
uses the registry's ``child_ids`` only as source variants.  Corpus rows are
matched through ``source_record_id`` so a page, parent, or preservation record
cannot become relevant merely by copying an evidence-group ID into metadata.

This module has no provider, database, or framework dependency.  Callers pass
the already ranked corpus rows and the observed execution-path counters.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping, Sequence
from typing import Any


SCORING_CONTRACT_VERSION = "evidence_group_policy_v2"
LEGACY_SCORING_CONTRACT_VERSION = "legacy_gold_v1_adapter"
DEFAULT_EVALUATION_TOP_K = 5
DEFAULT_ALLOWED_USE_VALUES = frozenset({"EXPERIMENT_ONLY"})
DEFAULT_VERIFIED_STATUSES = frozenset({"TEXT_AND_VISUAL_VERIFIED"})

_MATCH_POLICIES = frozenset({"ANY", "ALL", "NONE"})
_RETRIEVAL_OUTCOMES = frozenset({"EVIDENCE", "NO_EVIDENCE"})
_PGVECTOR_QUERY = "PGVECTOR_QUERY"
_POLICY_BLOCK_PATHS = frozenset(
    {
        "POLICY_BLOCK_PRODUCT_MISMATCH",
        "POLICY_BLOCK_UNSUPPORTED_MODEL",
        "POLICY_BLOCK_UNSUPPORTED_CAPABILITY",
        "POLICY_BLOCK_OUT_OF_MANUAL_SCOPE",
        "POLICY_BLOCK_UNVERIFIED_SOURCE",
    }
)


def _string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ValueError(f"{field_name}는 문자열 List여야 합니다.")
    if len(set(value)) != len(value):
        raise ValueError(f"{field_name}에는 중복 값이 없어야 합니다.")
    return list(value)


def _positive_int(value: Any, field_name: str, *, allow_zero: bool) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name}는 정수여야 합니다.")
    minimum = 0 if allow_zero else 1
    if value < minimum:
        raise ValueError(f"{field_name}는 {minimum} 이상이어야 합니다.")
    return value


def _corpus_row(result: Mapping[str, Any]) -> Mapping[str, Any]:
    chunk = result.get("chunk")
    if chunk is None:
        return result
    if not isinstance(chunk, Mapping):
        raise ValueError("ranked_results[].chunk는 Object여야 합니다.")
    return chunk


def _normalise_group_registry(
    evidence_groups: Mapping[str, Mapping[str, Any]]
    | Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, str]]:
    """Return validated group and child indexes.

    A Child may be a variant of exactly one semantic Evidence Group.  Sharing a
    Child between groups would make ANY/ALL completion ambiguous, so it is a
    contract error instead of a runtime scoring choice.
    """

    rows: list[tuple[str | None, Mapping[str, Any]]]
    if isinstance(evidence_groups, Mapping):
        rows = []
        for key, value in evidence_groups.items():
            if not isinstance(key, str) or not key or not isinstance(value, Mapping):
                raise ValueError("Evidence Group Registry Mapping이 유효하지 않습니다.")
            rows.append((key, value))
    elif isinstance(evidence_groups, Sequence) and not isinstance(
        evidence_groups, (str, bytes)
    ):
        rows = []
        for value in evidence_groups:
            if not isinstance(value, Mapping):
                raise ValueError("Evidence Group Registry 행은 Object여야 합니다.")
            rows.append((None, value))
    else:
        raise ValueError("evidence_groups는 Mapping 또는 Object Sequence여야 합니다.")

    group_by_id: dict[str, Mapping[str, Any]] = {}
    child_to_group: dict[str, str] = {}
    for mapping_key, row in rows:
        embedded_id = row.get("evidence_group_id")
        group_id = embedded_id if embedded_id is not None else mapping_key
        if not isinstance(group_id, str) or not group_id:
            raise ValueError("Evidence Group에 evidence_group_id가 필요합니다.")
        if mapping_key is not None and embedded_id is not None and mapping_key != embedded_id:
            raise ValueError(f"Evidence Group Mapping Key와 ID가 다릅니다: {mapping_key}")
        if group_id in group_by_id:
            raise ValueError(f"Evidence Group ID가 중복됐습니다: {group_id}")

        child_ids = _string_list(row.get("child_ids"), f"{group_id}.child_ids")
        if not child_ids:
            raise ValueError(f"Evidence Group에 Child가 없습니다: {group_id}")
        for child_id in child_ids:
            owner = child_to_group.get(child_id)
            if owner is not None:
                raise ValueError(
                    f"Child가 둘 이상의 Evidence Group에 연결됐습니다: "
                    f"{child_id} ({owner}, {group_id})"
                )
            child_to_group[child_id] = group_id
        group_by_id[group_id] = row

    return group_by_id, child_to_group


def _variant_child_id(
    corpus_row: Mapping[str, Any],
    child_to_group: Mapping[str, str],
) -> str | None:
    # Full Corpus v3 has one canonical lineage edge.  child_id/chunk_id
    # fallbacks would let a Parent masquerade as a registered Child.
    value = corpus_row.get("source_record_id")
    return value if isinstance(value, str) and value in child_to_group else None


def _verification_status(corpus_row: Mapping[str, Any]) -> Any:
    return corpus_row.get(
        "source_verification_status",
        corpus_row.get("verification_status"),
    )


def _covered_through(covered_by_rank: Sequence[set[str]], k: int) -> set[str]:
    covered: set[str] = set()
    for matched in covered_by_rank[:k]:
        covered.update(matched)
    return covered


def _completion_rank(
    covered_by_rank: Sequence[set[str]],
    required_ids: set[str],
    policy: str,
) -> int | None:
    for rank in range(1, len(covered_by_rank) + 1):
        covered = _covered_through(covered_by_rank, rank)
        if policy == "ANY" and covered:
            return rank
        if policy == "ALL" and required_ids.issubset(covered):
            return rank
    return None


def score_evidence_case_v2(
    case: Mapping[str, Any],
    ranked_results: Sequence[Mapping[str, Any]],
    evidence_groups: Mapping[str, Mapping[str, Any]]
    | Sequence[Mapping[str, Any]],
    *,
    actual_execution_path: str,
    vector_query_count: int,
    evaluation_top_k: int = DEFAULT_EVALUATION_TOP_K,
    allowed_use_values: Collection[str] = DEFAULT_ALLOWED_USE_VALUES,
    verified_statuses: Collection[str] = DEFAULT_VERIFIED_STATUSES,
) -> dict[str, Any]:
    """Score one Gold v2 Case against ranked Full Corpus rows.

    ``passed`` is the semantic top-K result plus the observed execution-path
    contract.  For positive Evidence cases, product leakage or a top-K row that
    is not an allowed, visually verified SEARCH_CANDIDATE also fails the case;
    such rows never satisfy a required or supporting group.
    """

    if not isinstance(case, Mapping):
        raise ValueError("case는 Object여야 합니다.")
    if not isinstance(ranked_results, Sequence) or isinstance(
        ranked_results, (str, bytes)
    ):
        raise ValueError("ranked_results는 Object Sequence여야 합니다.")
    if any(not isinstance(result, Mapping) for result in ranked_results):
        raise ValueError("ranked_results 행은 Object여야 합니다.")

    evaluation_top_k = _positive_int(
        evaluation_top_k, "evaluation_top_k", allow_zero=False
    )
    vector_query_count = _positive_int(
        vector_query_count, "vector_query_count", allow_zero=True
    )
    if not isinstance(actual_execution_path, str) or not actual_execution_path:
        raise ValueError("actual_execution_path는 비어 있지 않은 문자열이어야 합니다.")

    product_model_code = case.get("product_model_code")
    if not isinstance(product_model_code, str) or not product_model_code:
        raise ValueError("product_model_code가 필요합니다.")
    policy = case.get("evidence_match_policy")
    if policy not in _MATCH_POLICIES:
        raise ValueError(f"지원하지 않는 Evidence Match Policy: {policy}")
    outcome = case.get("expected_retrieval_outcome")
    if outcome not in _RETRIEVAL_OUTCOMES:
        raise ValueError(f"지원하지 않는 Retrieval Outcome: {outcome}")
    expected_path = case.get("expected_execution_path")
    if not isinstance(expected_path, str) or not expected_path:
        raise ValueError("expected_execution_path가 필요합니다.")

    required = _string_list(
        case.get("required_evidence_group_ids"),
        "required_evidence_group_ids",
    )
    supporting = _string_list(
        case.get("supporting_evidence_group_ids"),
        "supporting_evidence_group_ids",
    )
    forbidden_document_ids = _string_list(
        case.get("forbidden_document_ids"),
        "forbidden_document_ids",
    )
    forbidden_model_codes = _string_list(
        case.get("forbidden_model_codes"),
        "forbidden_model_codes",
    )
    if set(required).intersection(supporting):
        raise ValueError("Required와 Supporting Evidence Group은 중복될 수 없습니다.")

    if outcome == "EVIDENCE":
        if expected_path != _PGVECTOR_QUERY:
            raise ValueError("EVIDENCE Case의 expected_execution_path는 PGVECTOR_QUERY여야 합니다.")
        if policy not in {"ANY", "ALL"} or not required:
            raise ValueError("EVIDENCE Case에는 Required Group과 ANY/ALL Policy가 필요합니다.")
    else:
        if policy != "NONE" or required or supporting:
            raise ValueError("NO_EVIDENCE Case는 빈 Group과 NONE Policy가 필요합니다.")
        if expected_path != _PGVECTOR_QUERY and expected_path not in _POLICY_BLOCK_PATHS:
            raise ValueError("NO_EVIDENCE 실행 경로는 PGVECTOR_QUERY 또는 POLICY_BLOCK_*여야 합니다.")

    group_by_id, child_to_group = _normalise_group_registry(evidence_groups)
    expected_group_ids = set(required).union(supporting)
    missing_registry_groups = expected_group_ids.difference(group_by_id)
    if missing_registry_groups:
        raise ValueError(
            "Gold가 Registry에 없는 Evidence Group을 참조합니다: "
            + ", ".join(sorted(missing_registry_groups))
        )
    for group_id in expected_group_ids:
        group_product = group_by_id[group_id].get("exact_sales_code")
        if group_product != product_model_code:
            raise ValueError(
                f"Gold와 Evidence Group 제품이 다릅니다: {group_id} "
                f"({product_model_code}, {group_product})"
            )

    if isinstance(allowed_use_values, (str, bytes)):
        raise ValueError("allowed_use_values는 문자열 Collection이어야 합니다.")
    if isinstance(verified_statuses, (str, bytes)):
        raise ValueError("verified_statuses는 문자열 Collection이어야 합니다.")
    allowed_values = frozenset(allowed_use_values)
    verified_values = frozenset(verified_statuses)
    if not allowed_values or any(not isinstance(value, str) for value in allowed_values):
        raise ValueError("allowed_use_values에는 하나 이상의 문자열이 필요합니다.")
    if not verified_values or any(not isinstance(value, str) for value in verified_values):
        raise ValueError("verified_statuses에는 하나 이상의 문자열이 필요합니다.")

    required_by_rank: list[set[str]] = []
    supporting_by_rank: list[set[str]] = []
    matched_variant_child_ids: list[str] = []
    seen_variant_child_ids: set[str] = set()
    rows = [_corpus_row(result) for result in ranked_results]
    evaluated_rows = rows[:evaluation_top_k]
    required_set = set(required)
    supporting_set = set(supporting)
    forbidden_document_set = set(forbidden_document_ids)
    forbidden_model_set = set(forbidden_model_codes)
    for row in evaluated_rows:
        forbidden_hit = (
            row.get("document_id") in forbidden_document_set
            or row.get("exact_sales_code") in forbidden_model_set
        )
        row_is_valid = (
            row.get("exact_sales_code") == product_model_code
            and str(row.get("record_type", "")).upper() == "CHILD"
            and row.get("retrieval_role") == "SEARCH_CANDIDATE"
            and row.get("allowed_use") in allowed_values
            and _verification_status(row) in verified_values
            and not forbidden_hit
        )
        child_id = _variant_child_id(row, child_to_group) if row_is_valid else None
        group_id = child_to_group.get(child_id) if child_id is not None else None

        required_match = {group_id} if group_id in required_set else set()
        supporting_match = {group_id} if group_id in supporting_set else set()
        required_by_rank.append(required_match)
        supporting_by_rank.append(supporting_match)
        if (
            group_id in expected_group_ids
            and child_id is not None
            and child_id not in seen_variant_child_ids
        ):
            matched_variant_child_ids.append(child_id)
            seen_variant_child_ids.add(child_id)

    covered_required = _covered_through(required_by_rank, len(required_by_rank))
    covered_supporting = _covered_through(supporting_by_rank, len(supporting_by_rank))
    completion_rank = (
        _completion_rank(required_by_rank, set(required), policy)
        if outcome == "EVIDENCE"
        else None
    )

    def hit_at(k: int) -> float | None:
        if outcome == "NO_EVIDENCE":
            return None
        covered = _covered_through(required_by_rank, min(k, evaluation_top_k))
        if policy == "ANY":
            return float(bool(covered))
        return float(set(required).issubset(covered))

    def recall_at(k: int) -> float | None:
        if outcome == "NO_EVIDENCE":
            return None
        covered = _covered_through(required_by_rank, min(k, evaluation_top_k))
        return len(covered) / len(required)

    wrong_product_hit_count = sum(
        row.get("exact_sales_code") != product_model_code for row in evaluated_rows
    )
    non_child_hit_count = sum(
        str(row.get("record_type", "")).upper() != "CHILD"
        for row in evaluated_rows
    )
    non_search_candidate_hit_count = sum(
        row.get("retrieval_role") != "SEARCH_CANDIDATE" for row in evaluated_rows
    )
    disallowed_use_hit_count = sum(
        row.get("allowed_use") not in allowed_values for row in evaluated_rows
    )
    unverified_hit_count = sum(
        _verification_status(row) not in verified_values for row in evaluated_rows
    )
    forbidden_document_hit_count = sum(
        row.get("document_id") in forbidden_document_set for row in evaluated_rows
    )
    forbidden_model_hit_count = sum(
        row.get("exact_sales_code") in forbidden_model_set for row in evaluated_rows
    )
    invalid_top_k_hit_count = sum(
        not (
            row.get("exact_sales_code") == product_model_code
            and str(row.get("record_type", "")).upper() == "CHILD"
            and row.get("retrieval_role") == "SEARCH_CANDIDATE"
            and row.get("allowed_use") in allowed_values
            and _verification_status(row) in verified_values
            and row.get("document_id") not in forbidden_document_set
            and row.get("exact_sales_code") not in forbidden_model_set
        )
        for row in evaluated_rows
    )

    actual_path_matches = actual_execution_path == expected_path
    if outcome == "EVIDENCE":
        execution_contract_passed = actual_path_matches and vector_query_count >= 1
        semantic_passed = bool(hit_at(evaluation_top_k))
        passed = (
            execution_contract_passed
            and semantic_passed
            and invalid_top_k_hit_count == 0
        )
        no_evidence_success = None
        policy_block_success = None
        mrr = 1.0 / completion_rank if completion_rank else 0.0
    elif expected_path == _PGVECTOR_QUERY:
        execution_contract_passed = actual_path_matches and vector_query_count >= 1
        no_evidence_success = execution_contract_passed and not rows
        policy_block_success = None
        passed = no_evidence_success
        semantic_passed = None
        mrr = None
    else:
        execution_contract_passed = actual_path_matches and vector_query_count == 0
        no_evidence_success = None
        policy_block_success = execution_contract_passed and not rows
        passed = policy_block_success
        semantic_passed = None
        mrr = None

    return {
        "scoring_contract_version": SCORING_CONTRACT_VERSION,
        "evaluation_top_k": evaluation_top_k,
        "expected_retrieval_outcome": outcome,
        "evidence_match_policy": policy,
        "required_evidence_group_ids": sorted(required),
        "supporting_evidence_group_ids": sorted(supporting),
        "covered_required_group_ids": sorted(covered_required),
        "missing_required_group_ids": sorted(set(required).difference(covered_required)),
        "covered_supporting_group_ids": sorted(covered_supporting),
        "matched_variant_child_ids": matched_variant_child_ids,
        "hit_at_1": hit_at(1),
        "hit_at_3": hit_at(3),
        "hit_at_5": hit_at(5),
        "recall_at_1": recall_at(1),
        "recall_at_3": recall_at(3),
        "recall_at_5": recall_at(5),
        "required_completion_rank": completion_rank,
        "mrr": mrr,
        "expected_execution_path": expected_path,
        "actual_execution_path": actual_execution_path,
        "vector_query_count": vector_query_count,
        "execution_contract_passed": execution_contract_passed,
        "semantic_passed": semantic_passed,
        "wrong_product_hit_count": wrong_product_hit_count,
        "non_child_hit_count": non_child_hit_count,
        "non_search_candidate_hit_count": non_search_candidate_hit_count,
        "disallowed_use_hit_count": disallowed_use_hit_count,
        "unverified_hit_count": unverified_hit_count,
        "forbidden_document_hit_count": forbidden_document_hit_count,
        "forbidden_model_hit_count": forbidden_model_hit_count,
        "invalid_top_k_hit_count": invalid_top_k_hit_count,
        "no_evidence_success": no_evidence_success,
        "policy_block_success": policy_block_success,
        "passed": passed,
    }


def score_legacy_gold_case_v1(
    case: Mapping[str, Any],
    ranked_results: Sequence[Mapping[str, Any]],
    *,
    actual_execution_path: str = _PGVECTOR_QUERY,
    vector_query_count: int = 1,
    evaluation_top_k: int = DEFAULT_EVALUATION_TOP_K,
) -> dict[str, Any]:
    """Score a current Gold v1 case without changing its matching semantics.

    A v1 unit matches only when evidence-unit ID, document ID, and overlapping
    page all agree.  Unlike v2, this adapter does not introduce new allowed-use
    or visual-verification gates, so existing TEXT_EXTRACTED v1 rows keep their
    historical meaning.  NONE still passes only for an empty ranked result.
    """

    if not isinstance(case, Mapping):
        raise ValueError("case는 Object여야 합니다.")
    if not isinstance(ranked_results, Sequence) or isinstance(
        ranked_results, (str, bytes)
    ):
        raise ValueError("ranked_results는 Object Sequence여야 합니다.")
    if any(not isinstance(result, Mapping) for result in ranked_results):
        raise ValueError("ranked_results 행은 Object여야 합니다.")
    evaluation_top_k = _positive_int(
        evaluation_top_k, "evaluation_top_k", allow_zero=False
    )
    vector_query_count = _positive_int(
        vector_query_count, "vector_query_count", allow_zero=True
    )

    product_model_code = case.get("product_model_code")
    if not isinstance(product_model_code, str) or not product_model_code:
        raise ValueError("product_model_code가 필요합니다.")
    policy = case.get("evidence_match_policy")
    if policy not in _MATCH_POLICIES:
        raise ValueError(f"지원하지 않는 Evidence Match Policy: {policy}")
    expected_no_evidence = case.get("expected_no_evidence")
    if not isinstance(expected_no_evidence, bool):
        raise ValueError("expected_no_evidence는 Boolean이어야 합니다.")

    expected = case.get("expected_evidence")
    if not isinstance(expected, list) or any(not isinstance(row, Mapping) for row in expected):
        raise ValueError("expected_evidence는 Object List여야 합니다.")
    if policy == "NONE":
        if expected or not expected_no_evidence:
            raise ValueError("NONE Policy는 빈 expected_evidence와 expected_no_evidence=true가 필요합니다.")
    elif not expected or expected_no_evidence:
        raise ValueError("ANY/ALL Policy는 expected_evidence와 expected_no_evidence=false가 필요합니다.")

    expected_by_id: dict[str, Mapping[str, Any]] = {}
    for unit in expected:
        unit_id = unit.get("evidence_unit_id")
        document_id = unit.get("document_id")
        page_refs = unit.get("page_refs")
        if not isinstance(unit_id, str) or not unit_id:
            raise ValueError("expected_evidence에 evidence_unit_id가 필요합니다.")
        if not isinstance(document_id, str) or not document_id:
            raise ValueError("expected_evidence에 document_id가 필요합니다.")
        if not isinstance(page_refs, list) or not page_refs:
            raise ValueError("expected_evidence에 page_refs가 필요합니다.")
        if unit_id in expected_by_id:
            raise ValueError("expected_evidence의 evidence_unit_id는 고유해야 합니다.")
        expected_by_id[unit_id] = unit

    rows = [_corpus_row(result) for result in ranked_results]
    covered_by_rank: list[set[str]] = []
    for row in rows:
        unit_ids_value = row.get("evidence_unit_ids", [])
        unit_ids = set(unit_ids_value) if isinstance(unit_ids_value, list) else set()
        page_refs_value = row.get("page_refs", [])
        page_refs = set(page_refs_value) if isinstance(page_refs_value, list) else set()
        matched = {
            unit_id
            for unit_id, unit in expected_by_id.items()
            if unit_id in unit_ids
            and row.get("document_id") == unit["document_id"]
            and bool(page_refs.intersection(unit["page_refs"]))
        }
        covered_by_rank.append(matched)

    required_ids = set(expected_by_id)
    covered_ids = _covered_through(covered_by_rank, len(covered_by_rank))
    first_matched_rank = next(
        (
            rank
            for rank, matched_ids in enumerate(covered_by_rank, start=1)
            if matched_ids
        ),
        None,
    )
    completion_rank = (
        _completion_rank(covered_by_rank, required_ids, policy)
        if policy != "NONE"
        else None
    )

    def hit_at(k: int) -> float:
        if policy == "NONE":
            return 0.0
        covered = _covered_through(covered_by_rank, min(k, evaluation_top_k))
        if policy == "ANY":
            return float(bool(covered))
        return float(required_ids.issubset(covered))

    def recall_at(k: int) -> float | None:
        if policy == "NONE":
            return None
        covered = _covered_through(covered_by_rank, min(k, evaluation_top_k))
        return len(covered) / len(required_ids)

    expected_path = case.get("expected_execution_path", _PGVECTOR_QUERY)
    if not isinstance(expected_path, str) or not expected_path:
        raise ValueError("expected_execution_path는 문자열이어야 합니다.")
    top_k_rows = rows[:evaluation_top_k]
    wrong_product_hit_count = sum(
        row.get("exact_sales_code") != product_model_code for row in top_k_rows
    )
    if policy == "NONE":
        passed = not rows
        semantic_passed: bool | None = passed
        mrr = 0.0
        ndcg_at_5: float | None = 0.0
    else:
        passed = bool(hit_at(evaluation_top_k))
        semantic_passed = passed
        mrr = 1.0 / completion_rank if completion_rank else 0.0
        ndcg_at_5 = (
            1.0 / math.log2(completion_rank + 1)
            if policy == "ANY"
            and completion_rank is not None
            and completion_rank <= evaluation_top_k
            else None if policy == "ALL" else 0.0
        )

    return {
        "scoring_contract_version": LEGACY_SCORING_CONTRACT_VERSION,
        "evaluation_top_k": evaluation_top_k,
        "expected_retrieval_outcome": (
            "NO_EVIDENCE" if expected_no_evidence else "EVIDENCE"
        ),
        "evidence_match_policy": policy,
        "required_evidence_unit_ids": sorted(required_ids),
        "covered_required_evidence_unit_ids": sorted(covered_ids),
        # Existing Full B1 _metrics compatibility aliases start here.
        "covered_evidence_unit_ids": sorted(covered_ids),
        "missing_required_evidence_unit_ids": sorted(required_ids.difference(covered_ids)),
        "hit_at_1": hit_at(1),
        "hit_at_3": hit_at(3),
        "hit_at_5": hit_at(5),
        "recall_at_1": recall_at(1),
        "recall_at_3": recall_at(3),
        "recall_at_5": recall_at(5),
        "required_completion_rank": completion_rank,
        "mrr": mrr,
        "ndcg_at_5": ndcg_at_5,
        "first_matched_rank": first_matched_rank,
        "evidence_completion_rank": completion_rank,
        "first_relevant_rank": completion_rank,
        "expected_execution_path": expected_path,
        "actual_execution_path": actual_execution_path,
        "vector_query_count": vector_query_count,
        "execution_contract_passed": actual_execution_path == expected_path,
        "semantic_passed": semantic_passed,
        "wrong_product_hit_count": wrong_product_hit_count,
        "no_evidence_retrieval_empty": bool(expected_no_evidence and not rows),
        "no_evidence_passed": bool(expected_no_evidence and not rows),
        "answerability_gate_passed": None,
        "no_evidence_success": passed if policy == "NONE" else None,
        "policy_block_success": None,
        "passed": passed,
    }


def score_gold_case(
    case: Mapping[str, Any],
    ranked_results: Sequence[Mapping[str, Any]],
    *,
    actual_execution_path: str,
    vector_query_count: int,
    evidence_groups: Mapping[str, Mapping[str, Any]]
    | Sequence[Mapping[str, Any]]
    | None = None,
    evaluation_top_k: int = DEFAULT_EVALUATION_TOP_K,
    allowed_use_values: Collection[str] = DEFAULT_ALLOWED_USE_VALUES,
    verified_statuses: Collection[str] = DEFAULT_VERIFIED_STATUSES,
) -> dict[str, Any]:
    """Dispatch v1 and v2 Gold through one scorer entrypoint.

    Full B1 and Playground call this function instead of selecting their own
    matching rules.  Gold v2 is identified by its Group fields and requires an
    Evidence Group Registry; Gold v1 is identified by ``expected_evidence``.
    Supplying both contracts is rejected so a partially migrated Case cannot be
    scored under whichever branch happens to run first.
    """

    if not isinstance(case, Mapping):
        raise ValueError("case는 Object여야 합니다.")
    is_v2 = any(
        field in case
        for field in (
            "required_evidence_group_ids",
            "supporting_evidence_group_ids",
            "expected_retrieval_outcome",
        )
    )
    is_v1 = any(
        field in case
        for field in ("expected_evidence", "expected_no_evidence")
    )
    if is_v1 and is_v2:
        raise ValueError("Gold v1과 v2 필드를 한 Case에 함께 사용할 수 없습니다.")
    if is_v2:
        if evidence_groups is None:
            raise ValueError("Gold v2 채점에는 Evidence Group Registry가 필요합니다.")
        return score_evidence_case_v2(
            case,
            ranked_results,
            evidence_groups,
            actual_execution_path=actual_execution_path,
            vector_query_count=vector_query_count,
            evaluation_top_k=evaluation_top_k,
            allowed_use_values=allowed_use_values,
            verified_statuses=verified_statuses,
        )
    if is_v1:
        return score_legacy_gold_case_v1(
            case,
            ranked_results,
            actual_execution_path=actual_execution_path,
            vector_query_count=vector_query_count,
            evaluation_top_k=evaluation_top_k,
        )
    raise ValueError("지원하는 Gold v1 또는 v2 필드가 없습니다.")


__all__ = [
    "DEFAULT_ALLOWED_USE_VALUES",
    "DEFAULT_EVALUATION_TOP_K",
    "DEFAULT_VERIFIED_STATUSES",
    "LEGACY_SCORING_CONTRACT_VERSION",
    "SCORING_CONTRACT_VERSION",
    "score_evidence_case_v2",
    "score_gold_case",
    "score_legacy_gold_case_v1",
]
