"""Deterministic chunk builders used by the Experiment Lab B1 comparison."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _windows(tokens: list[str], size: int, overlap: int) -> list[tuple[int, int, str]]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Chunk window는 size > overlap >= 0 이어야 합니다.")
    if not tokens:
        return [(0, 0, "")]
    step = size - overlap
    windows = []
    for start in range(0, len(tokens), step):
        end = min(start + size, len(tokens))
        windows.append((start, end, " ".join(tokens[start:end])))
        if end == len(tokens):
            break
    return windows


def _section_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["document_id"], row["exact_sales_code"], row["section_id"]


def _section_groups(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for row in rows:
        if not groups or _section_key(groups[-1][-1]) != _section_key(row):
            groups.append([row])
        else:
            groups[-1].append(row)
    return groups


def _derived_chunk(
    profile_id: str,
    index: int,
    sources: list[dict[str, Any]],
    text: str,
    **extra: Any,
) -> dict[str, Any]:
    first = sources[0]
    page_refs = sorted({page for source in sources for page in source["page_refs"]})
    evidence_ids = list(dict.fromkeys(
        evidence_id
        for source in sources
        for evidence_id in source.get("evidence_unit_ids", [])
    ))
    return {
        "chunk_id": f"{first['document_id']}::{profile_id}::{index:04d}",
        "chunk_index": index,
        "chunking_profile": profile_id,
        "document_id": first["document_id"],
        "source_record_id": first["source_record_id"],
        "source_type": first["source_type"],
        "exact_sales_code": first["exact_sales_code"],
        "product_model": first["product_model"],
        "product_generation": first["product_generation"],
        "corpus_scope": first["corpus_scope"],
        "allowed_use": "EXPERIMENT_ONLY",
        "page_refs": page_refs,
        "section_id": first["section_id"],
        "section_title": first["section_title"],
        "evidence_unit_ids": evidence_ids,
        "text": text,
        "text_sha256": _text_sha256(text),
        "source_file_sha256": first["source_file_sha256"],
        "source_verification_status": first["source_verification_status"],
        **extra,
    }


def build_profile_chunks(
    source_rows: list[dict[str, Any]],
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build one configured B1 profile without changing the source corpus."""

    if profile.get("status") != "RUNNABLE":
        raise ValueError(f"실행할 수 없는 Chunking Profile: {profile['profile_id']}")
    profile_id = profile["profile_id"]
    strategy = profile["strategy"]
    chunks: list[dict[str, Any]] = []

    if strategy == "source_page":
        for index, row in enumerate(source_rows, 1):
            chunk = dict(row)
            chunk["chunk_id"] = f"{row['document_id']}::{profile_id}::{index:04d}"
            chunk["chunk_index"] = index
            chunk["chunking_profile"] = profile_id
            chunks.append(chunk)
        return chunks

    if strategy == "fixed_tokens_per_page":
        for source in source_rows:
            tokens = source["text"].split()
            for start, end, text in _windows(
                tokens,
                profile["window_tokens"],
                profile["overlap_tokens"],
            ):
                chunks.append(_derived_chunk(
                    profile_id,
                    len(chunks) + 1,
                    [source],
                    text,
                    source_token_start=start,
                    source_token_end=end,
                ))
        return chunks

    if strategy == "consecutive_section":
        for sources in _section_groups(source_rows):
            text = "\n\n".join(source["text"] for source in sources)
            chunks.append(_derived_chunk(
                profile_id,
                len(chunks) + 1,
                sources,
                text,
            ))
        return chunks

    if strategy == "parent_section_child_tokens_per_page":
        parent_text_by_key = {
            _section_key(group[0]): "\n\n".join(row["text"] for row in group)
            for group in _section_groups(source_rows)
        }
        for source in source_rows:
            parent_id = "::".join((*_section_key(source), "PARENT"))
            parent_text = parent_text_by_key[_section_key(source)]
            tokens = source["text"].split()
            for start, end, text in _windows(
                tokens,
                profile["child_window_tokens"],
                profile["child_overlap_tokens"],
            ):
                chunks.append(_derived_chunk(
                    profile_id,
                    len(chunks) + 1,
                    [source],
                    text,
                    parent_id=parent_id,
                    context_text=parent_text,
                    source_token_start=start,
                    source_token_end=end,
                ))
        return chunks

    raise ValueError(f"지원하지 않는 Chunking Strategy: {strategy}")


def profile_statistics(
    source_rows: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return structural metrics without presenting them as retrieval quality."""

    source_tokens = sum(len(row["text"].split()) for row in source_rows)
    indexed_tokens = sum(len(row["text"].split()) for row in chunks)
    context_tokens = sum(len(row.get("context_text", "").split()) for row in chunks)
    by_product = defaultdict(int)
    for row in chunks:
        by_product[row["exact_sales_code"]] += 1
    lineage_complete = sum(bool(
        row.get("document_id")
        and row.get("page_refs")
        and row.get("exact_sales_code")
        and row.get("source_file_sha256")
    ) for row in chunks)
    lengths = [len(row["text"].split()) for row in chunks]
    return {
        "chunk_count": len(chunks),
        "chunk_count_by_product": dict(sorted(by_product.items())),
        "average_chunk_tokens": round(sum(lengths) / len(lengths), 3) if lengths else 0.0,
        "minimum_chunk_tokens": min(lengths, default=0),
        "maximum_chunk_tokens": max(lengths, default=0),
        "source_tokens": source_tokens,
        "indexed_tokens": indexed_tokens,
        "structural_overlap_ratio": round(
            max(0, indexed_tokens - source_tokens) / indexed_tokens,
            6,
        ) if indexed_tokens else 0.0,
        "context_payload_tokens": context_tokens,
        "lineage_restore_rate": round(lineage_complete / len(chunks), 6) if chunks else 0.0,
    }
