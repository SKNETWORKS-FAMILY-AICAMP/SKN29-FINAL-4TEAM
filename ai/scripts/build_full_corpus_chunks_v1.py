#!/usr/bin/env python3
"""A1 매뉴얼 96쪽을 A3-1 Full Corpus 검색 단위로 고정한다."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ai.evaluation.file_integrity import file_sha256


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
JAC_INPUT = "data/processed/documents/manuals/mvp/manual_pages_jac104d.jsonl"
IAC_INPUT = "data/processed/documents/manuals/expansion/manual_pages_iac425.jsonl"
OUTPUT_DATASET = "ai/evaluation/corpora/full_corpus_chunks_v1.jsonl"
OUTPUT_MANIFEST = "ai/evaluation/corpora/full_corpus_chunks_v1_manifest.json"
SCHEMA_PATH = "ai/evaluation/schemas/full_corpus_chunk_v1.schema.json"
CHUNKING_PROFILE = "current_source_page_v1"

JAC_PAGE_EVIDENCE = {
    37: [
        "EVD-WPUJAC104DWH-NO-WATER-001",
        "EVD-WPUJAC104DWH-COLD-TEMPERATURE-001",
        "EVD-WPUJAC104DWH-NOISE-001",
    ],
    38: [
        "EVD-WPUJAC104DWH-LEAK-001",
        "EVD-WPUJAC104DWH-TASTE-ODOR-001",
        "EVD-WPUJAC104DWH-LOW-FLOW-001",
        "EVD-WPUJAC104DWH-INSTANT-HOT-WATER-SAFETY-001",
    ],
    39: ["EVD-WPUJAC104DWH-INSTANT-HOT-WATER-SAFETY-001"],
}


def _sha256(path: Path) -> str:
    return file_sha256(path)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"JSONL 행은 객체여야 합니다: {path}")
    return rows


def _jac_section_id(page: int) -> str:
    if 3 <= page <= 7:
        return "JAC104-SECTION-SAFETY"
    if 37 <= page <= 39:
        return "JAC104-SECTION-TROUBLESHOOTING"
    return f"JAC104-SECTION-P{page:03d}"


def build_chunks() -> list[dict[str, Any]]:
    jac_rows = _load_jsonl(REPOSITORY_ROOT / JAC_INPUT)
    iac_rows = _load_jsonl(REPOSITORY_ROOT / IAC_INPUT)
    chunks: list[dict[str, Any]] = []

    for row in jac_rows:
        page = row["page"]
        source_record_id = row["page_id"]
        chunks.append({
            "chunk_id": source_record_id,
            "chunk_index": len(chunks) + 1,
            "chunking_profile": CHUNKING_PROFILE,
            "document_id": row["document_id"],
            "source_record_id": source_record_id,
            "source_type": row["source_type"],
            "exact_sales_code": row["exact_sales_code"],
            "product_model": row["product_model"],
            "product_generation": row["product_generation"],
            "corpus_scope": "JAC104_ONLY",
            "allowed_use": "EXPERIMENT_ONLY",
            "page_refs": [page],
            "section_id": _jac_section_id(page),
            "section_title": row["section_title"],
            "evidence_unit_ids": JAC_PAGE_EVIDENCE.get(page, [source_record_id]),
            "text": row["text"],
            "text_sha256": row["text_sha256"],
            "source_file_sha256": row["source_file_sha256"],
            "source_verification_status": row["verification_status"],
        })

    for row in iac_rows:
        source_record_id = row["page_id"]
        chunks.append({
            "chunk_id": source_record_id,
            "chunk_index": len(chunks) + 1,
            "chunking_profile": CHUNKING_PROFILE,
            "document_id": row["document_id"],
            "source_record_id": source_record_id,
            "source_type": row["source_type"],
            "exact_sales_code": row["exact_sales_code"],
            "product_model": row["product_model"],
            "product_generation": row["product_generation"],
            "corpus_scope": "IAC425_ONLY",
            "allowed_use": "EXPERIMENT_ONLY",
            "page_refs": [row["page"]],
            "section_id": row["section_id"],
            "section_title": row["section_title"],
            "evidence_unit_ids": [source_record_id],
            "text": row["text"],
            "text_sha256": row["text_sha256"],
            "source_file_sha256": row["source_file_sha256"],
            "source_verification_status": row["verification_status"],
        })
    return chunks


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return ("\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        for row in rows
    ) + "\n").encode("utf-8")


def main() -> None:
    chunks = build_chunks()
    if len(chunks) != 96:
        raise ValueError(f"Full Manual Corpus는 96개여야 합니다: {len(chunks)}")
    if len({row["chunk_id"] for row in chunks}) != len(chunks):
        raise ValueError("중복 Chunk ID가 있습니다.")
    schema_path = REPOSITORY_ROOT / SCHEMA_PATH
    validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))
    schema_errors = [
        f"{row['chunk_id']}: {error.message}"
        for row in chunks
        for error in validator.iter_errors(row)
    ]
    if schema_errors:
        raise ValueError("Full Corpus Schema 오류: " + " | ".join(schema_errors[:10]))

    output_path = REPOSITORY_ROOT / OUTPUT_DATASET
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_jsonl_bytes(chunks))
    scope_counts = Counter(row["corpus_scope"] for row in chunks)
    manifest = {
        "corpus_id": "FULL-MANUAL-CORPUS-V1",
        "corpus_version": "1.0.0",
        "status": "READY_FOR_EMBEDDING",
        "generated_at": "2026-08-10T00:00:00+09:00",
        "chunking_profile": CHUNKING_PROFILE,
        "chunking_interpretation": (
            "A1에서 확정한 페이지 레코드 1개를 검색 Chunk 1개로 사용하는 현재 저장 단위 기준선"
        ),
        "dataset": {
            "path": OUTPUT_DATASET,
            "records": len(chunks),
            "sha256": _sha256(output_path),
        },
        "schema": {"path": SCHEMA_PATH, "sha256": _sha256(schema_path)},
        "scope_counts": dict(sorted(scope_counts.items())),
        "source_files": [
            {"path": path, "sha256": _sha256(REPOSITORY_ROOT / path)}
            for path in [JAC_INPUT, IAC_INPUT]
        ],
        "limitations": [
            "FAQ 119건은 A3-1의 명시된 JAC104+IAC425 매뉴얼 범위에서 제외",
            "페이지 단위는 Phase B 청킹 비교의 최종 우승 전략을 의미하지 않음",
            "전체 시각 검수 및 Gold 2인 승인 전 공식 운영 Corpus로 사용하지 않음",
        ],
    }
    manifest_path = REPOSITORY_ROOT / OUTPUT_MANIFEST
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": manifest["status"],
        "records": len(chunks),
        "scope_counts": manifest["scope_counts"],
        "sha256": manifest["dataset"]["sha256"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
