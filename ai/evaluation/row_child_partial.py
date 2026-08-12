"""Adapters and context accounting for the D04 partial row-child diagnostic."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any


def adapt_child(row: dict[str, Any]) -> dict[str, Any]:
    """Expose one experimental Child through the existing retrieval metric contract."""

    evidence_group_id = row.get("evidence_group_id")
    if not isinstance(evidence_group_id, str) or not evidence_group_id:
        raise ValueError("Child에는 evidence_group_id 문자열이 정확히 1개 필요합니다.")
    return {
        "chunk_id": row["child_id"],
        "document_id": row["document_id"],
        "page_refs": row["page_refs"],
        "exact_sales_code": "WPUJAC104DWH",
        "evidence_unit_ids": [evidence_group_id],
        "text": row["child_text"],
        "text_sha256": row["child_text_sha256"],
        "parent_id": row["parent_id"],
        "source_variant_id": row["source_variant_id"],
        "source_span": row["source_span"],
        "record_type": "child",
    }


def build_partial_replacement_corpus(
    source_rows: list[dict[str, Any]],
    child_rows: list[dict[str, Any]],
    *,
    document_id: str,
    replaced_page_refs: set[int],
) -> tuple[list[dict[str, Any]], int]:
    """Replace only configured source pages with experimental row Children."""

    retained = [
        dict(row)
        for row in source_rows
        if not (
            row["document_id"] == document_id
            and bool(set(row["page_refs"]).intersection(replaced_page_refs))
        )
    ]
    removed_count = len(source_rows) - len(retained)
    return [*retained, *(adapt_child(row) for row in child_rows)], removed_count


def expand_parent_context(
    ranked: list[dict[str, Any]],
    parent_by_id: dict[str, dict[str, Any]],
    child_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Deduplicate selected Parents and report context breadth without scoring Parents."""

    started = time.perf_counter()
    child_groups_by_parent: dict[str, set[str]] = defaultdict(set)
    for row in child_rows:
        child_groups_by_parent[row["parent_id"]].add(row["evidence_group_id"])

    selected_parent_ids: list[str] = []
    raw_parent_ids: list[str] = []
    retrieved_groups: set[str] = set()
    for item in ranked:
        chunk = item["chunk"]
        retrieved_groups.update(chunk.get("evidence_unit_ids", []))
        parent_id = chunk.get("parent_id")
        if not parent_id:
            continue
        raw_parent_ids.append(parent_id)
        if parent_id not in selected_parent_ids:
            selected_parent_ids.append(parent_id)

    parents = [parent_by_id[parent_id] for parent_id in selected_parent_ids]
    context_groups = set().union(
        *(child_groups_by_parent[parent_id] for parent_id in selected_parent_ids)
    ) if selected_parent_ids else set()
    context_texts = [row["parent_text"] for row in parents]
    context_texts.extend(
        item["chunk"]["text"]
        for item in ranked
        if not item["chunk"].get("parent_id")
    )
    latency_ms = (time.perf_counter() - started) * 1000
    return {
        "selected_parent_ids": selected_parent_ids,
        "raw_parent_reference_count": len(raw_parent_ids),
        "deduplicated_parent_count": len(selected_parent_ids),
        "deduplicated_parent_reference_count": len(raw_parent_ids) - len(selected_parent_ids),
        "context_whitespace_tokens": sum(len(text.split()) for text in context_texts),
        "context_character_count": sum(len(text) for text in context_texts),
        "known_context_evidence_group_ids": sorted(context_groups),
        "additional_context_evidence_group_ids": sorted(context_groups - retrieved_groups),
        "contains_excluded_micro_particle_row": any(
            "미세한 입자 발생" in text for text in context_texts
        ),
        "expansion_latency_ms": round(latency_ms, 6),
        "human_context_review_status": (
            "REVIEW_REQUIRED" if selected_parent_ids else "NOT_APPLICABLE"
        ),
    }
