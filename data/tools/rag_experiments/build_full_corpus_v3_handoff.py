"""Full Corpus v3와 Evidence Group–Child 인계 자산을 결정적으로 생성한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
GENERATED_AT = "2026-08-26T00:00:00+09:00"
CONFIG_PATH = "data/config/rag/full_corpus_v3_segments.json"

DEFAULT_CORPUS_OUTPUT = (
    "data/processed/structured/rag/experimental/full_corpus_chunks_v3.jsonl"
)
DEFAULT_COVERAGE_OUTPUT = (
    "data/processed/structured/rag/experimental/full_corpus_v3_coverage.json"
)
DEFAULT_PARENT_OUTPUT = (
    "data/processed/structured/rag/experimental/full_corpus_v3_context_parents.jsonl"
)
DEFAULT_CHILD_OUTPUT = (
    "data/processed/structured/rag/experimental/full_corpus_v3_children.jsonl"
)
DEFAULT_GROUP_OUTPUT = (
    "data/processed/structured/evidence/full_corpus_v3_evidence_groups.jsonl"
)
DEFAULT_MANIFEST_OUTPUT = (
    "data/processed/metadata/full_corpus_v3_handoff_manifest.json"
)

CORPUS_SCHEMA = "data/schemas/processed/fullCorpusV3Chunk.schema.json"
COVERAGE_SCHEMA = "data/schemas/processed/fullCorpusV3Coverage.schema.json"
PARENT_SCHEMA = "data/schemas/processed/ragParentPage.schema.json"
CHILD_SCHEMA = "data/schemas/processed/ragChildChunk.schema.json"
GROUP_SCHEMA = "ai/evaluation/schemas/evidence_group_registry_v2.schema.json"
SOURCE_REVIEW_SCHEMA = "data/schemas/config/fullCorpusV3SourceReview.schema.json"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    )
    path.write_text(payload, encoding="utf-8", newline="\n")


def _logical_output_path(path: Path, canonical: str) -> str:
    try:
        return str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/")
    except ValueError:
        return canonical


def _resolved_inputs(config: dict[str, Any]) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    for name, spec in config["inputs"].items():
        path = REPOSITORY_ROOT / spec["path"]
        actual = _sha256_file(path)
        if actual != spec["sha256"]:
            raise RuntimeError(
                f"입력 해시 불일치: {name} expected={spec['sha256']} actual={actual}"
            )
        resolved[name] = path
    return resolved


def _clean_child_text(lines: list[str]) -> str:
    return " ".join(" ".join(lines).replace("●", " ").split())


def _base_chunk(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": row["chunk_id"],
        "chunk_index": 0,
        "chunking_profile": "row_child_full_corpus_v3",
        "record_type": "SOURCE_PAGE",
        "retrieval_role": "SEARCH_CANDIDATE",
        "document_id": row["document_id"],
        "source_record_id": row["source_record_id"],
        "source_type": row["source_type"],
        "exact_sales_code": row["exact_sales_code"],
        "product_model": row["product_model"],
        "product_generation": row["product_generation"],
        "corpus_scope": row["corpus_scope"],
        "allowed_use": "EXPERIMENT_ONLY",
        "page_refs": row["page_refs"],
        "section_id": row["section_id"],
        "section_title": row["section_title"],
        "evidence_unit_ids": row["evidence_unit_ids"],
        "text": row["text"],
        "text_sha256": row["text_sha256"],
        "source_file_sha256": row["source_file_sha256"],
        "source_verification_status": row["source_verification_status"],
    }


def _child_chunk(child: dict[str, Any], source_page: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": child["child_id"],
        "chunk_index": 0,
        "chunking_profile": "row_child_full_corpus_v3",
        "record_type": "CHILD",
        "retrieval_role": "SEARCH_CANDIDATE",
        "document_id": child["document_id"],
        "source_record_id": child["child_id"],
        "source_type": "official_manual",
        "exact_sales_code": child["exact_sales_code"],
        "product_model": child["product_model"],
        "product_generation": child["product_generation"],
        "corpus_scope": source_page["corpus_scope"],
        "allowed_use": "EXPERIMENT_ONLY",
        "page_refs": child["page_refs"],
        "section_id": source_page["section_id"],
        "section_title": child["section_title"],
        "evidence_unit_ids": [child["evidence_group_id"]],
        "text": child["child_text"],
        "text_sha256": child["child_text_sha256"],
        "source_file_sha256": child["source_file_sha256"],
        "source_verification_status": child["verification_status"],
        "parent_id": child["parent_id"],
        "source_variant_id": child["source_variant_id"],
        "source_span": child["source_span"],
    }


def _preservation_chunk(
    record_id: str,
    line_start: int,
    line_end: int,
    page_lines: list[str],
    source_page: dict[str, Any],
) -> dict[str, Any]:
    text = "\n".join(page_lines[line_start - 1 : line_end])
    return {
        "chunk_id": record_id,
        "chunk_index": 0,
        "chunking_profile": "row_child_full_corpus_v3",
        "record_type": "PRESERVATION",
        "retrieval_role": "SEARCH_CANDIDATE",
        "document_id": source_page["document_id"],
        "source_record_id": record_id,
        "source_type": source_page["source_type"],
        "exact_sales_code": source_page["exact_sales_code"],
        "product_model": source_page["product_model"],
        "product_generation": source_page["product_generation"],
        "corpus_scope": source_page["corpus_scope"],
        "allowed_use": "EXPERIMENT_ONLY",
        "page_refs": source_page["page_refs"],
        "section_id": source_page["section_id"],
        "section_title": source_page["section_title"],
        "evidence_unit_ids": [record_id],
        "text": text,
        "text_sha256": _sha256_text(text),
        "source_file_sha256": source_page["source_file_sha256"],
        "source_verification_status": source_page["source_verification_status"],
        "source_variant_id": (
            f"PRESERVATION-P{source_page['page_refs'][0]:03d}-"
            f"L{line_start:03d}-L{line_end:03d}"
        ),
        "source_span": {
            "type": "CONTIGUOUS_SOURCE_LINES",
            "line_start": line_start,
            "line_end": line_end,
            "raw_span_sha256": _sha256_text(text),
        },
    }


def _build_manual_maps(
    config: dict[str, Any], inputs: dict[str, Path]
) -> dict[tuple[str, int], dict[str, Any]]:
    pages: dict[tuple[str, int], dict[str, Any]] = {}
    for replacement in config["replacements"]:
        requested = {int(page) for page in replacement["pages"]}
        rows = _read_jsonl(inputs[replacement["manual_input"]])
        found = {row["page"] for row in rows if row["page"] in requested}
        if found != requested:
            raise RuntimeError(
                f"매뉴얼 페이지 누락: {replacement['exact_sales_code']} "
                f"expected={sorted(requested)} actual={sorted(found)}"
            )
        for row in rows:
            if row["page"] in requested:
                pages[(replacement["document_id"], row["page"])] = row
    return pages


def _segment_lookup(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for replacement in config["replacements"]:
        for page, segments in replacement["pages"].items():
            for segment in segments:
                if segment["classification"] != "CHILD":
                    continue
                record_id = segment["record_id"]
                if record_id in lookup:
                    raise RuntimeError(f"중복 Child segment: {record_id}")
                lookup[record_id] = {
                    **segment,
                    "page": int(page),
                    "document_id": replacement["document_id"],
                    "exact_sales_code": replacement["exact_sales_code"],
                }
    return lookup


def _build_parents_and_children(
    config: dict[str, Any],
    inputs: dict[str, Path],
    baseline: list[dict[str, Any]],
    manual_pages: dict[tuple[str, int], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    segments = _segment_lookup(config)
    declared_child_ids = set(segments)
    existing = {
        row["child_id"]: row
        for row in _read_jsonl(inputs["existing_children"])
        if row["child_id"] in declared_child_ids
    }
    baseline_pages = {
        (row["document_id"], row["page_refs"][0]): row for row in baseline
    }
    product_templates: dict[str, dict[str, Any]] = {}
    for row in existing.values():
        product_templates.setdefault(row["exact_sales_code"], row)

    parents: list[dict[str, Any]] = []
    parent_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for replacement in config["replacements"]:
        code = replacement["exact_sales_code"]
        template = product_templates[code]
        for page_text in sorted((int(page) for page in replacement["pages"])):
            key = (replacement["document_id"], page_text)
            source = manual_pages[key]
            baseline_page = baseline_pages[key]
            parent = {
                "parent_id": f"PARENT-{code}-P{page_text:03d}",
                "record_type": "parent",
                "retrieval_role": "CONTEXT_ONLY",
                "exact_sales_code": code,
                "product_model": baseline_page["product_model"],
                "model_family": template["model_family"],
                "product_generation": baseline_page["product_generation"],
                "document_id": replacement["document_id"],
                "version": template["version"],
                "page_id": source["page_id"],
                "page_refs": [page_text],
                "section_title": source["section_title"],
                "parent_text": source["text"],
                "parent_text_sha256": source["text_sha256"],
                "source_page_text_sha256": source["text_sha256"],
                "source_file_sha256": source["source_file_sha256"],
                "source_type": "official_manual",
                "provider": "SK매직",
                "allowed_use": "RAG_HANDOFF_ONLY",
                "verification_status": "TEXT_AND_VISUAL_VERIFIED",
                "generated_at": GENERATED_AT,
            }
            parents.append(parent)
            parent_by_key[key] = parent

    children: list[dict[str, Any]] = []
    for child_id in sorted(declared_child_ids):
        segment = segments[child_id]
        key = (segment["document_id"], segment["page"])
        page = manual_pages[key]
        parent = parent_by_key[key]
        lines = page["text"].split("\n")
        selected = lines[segment["line_start"] - 1 : segment["line_end"]]
        raw_span = "\n".join(selected)

        if child_id in existing:
            child = dict(existing[child_id])
            span = child["source_span"]
            if (
                span["line_start"] != segment["line_start"]
                or span["line_end"] != segment["line_end"]
                or span["start_anchor"] != selected[0]
                or span["end_anchor"] != selected[-1]
                or span["raw_span_sha256"] != _sha256_text(raw_span)
            ):
                raise RuntimeError(f"기존 Child Anchor 불일치: {child_id}")
            child["evidence_group_id"] = config["child_group_remaps"].get(
                child_id, child["evidence_group_id"]
            )
            child["generated_at"] = GENERATED_AT
        else:
            spec = config["new_children"].get(child_id)
            if spec is None:
                raise RuntimeError(f"신규 Child 정의 누락: {child_id}")
            child_text = _clean_child_text(selected)
            template = product_templates[segment["exact_sales_code"]]
            child = {
                "child_id": child_id,
                "record_type": "child",
                "retrieval_role": "SEARCH_CANDIDATE",
                "child_text": child_text,
                "child_text_sha256": _sha256_text(child_text),
                "exact_sales_code": segment["exact_sales_code"],
                "product_model": parent["product_model"],
                "model_family": template["model_family"],
                "product_generation": parent["product_generation"],
                "document_id": segment["document_id"],
                "version": template["version"],
                "parent_id": parent["parent_id"],
                "parent_text_sha256": parent["parent_text_sha256"],
                "page_id": parent["page_id"],
                "page_refs": [segment["page"]],
                "section_title": parent["section_title"],
                "evidence_group_id": spec["evidence_group_id"],
                "source_variant_id": spec["source_variant_id"],
                "source_span": {
                    "type": "TABLE_ROW_OR_PARAGRAPH",
                    "row_label": spec["row_label"],
                    "line_start": segment["line_start"],
                    "line_end": segment["line_end"],
                    "start_anchor": selected[0],
                    "end_anchor": selected[-1],
                    "raw_span_sha256": _sha256_text(raw_span),
                },
                "source_file_sha256": parent["source_file_sha256"],
                "source_page_text_sha256": parent["source_page_text_sha256"],
                "risk_level": spec["risk_level"],
                "safe_actions": spec["safe_actions"],
                "requires_consultation": spec["requires_consultation"],
                "consultation_conditions": spec["consultation_conditions"],
                "allowed_use": "RAG_HANDOFF_ONLY",
                "verification_status": "TEXT_AND_VISUAL_VERIFIED",
                "generated_at": GENERATED_AT,
            }
        children.append(child)

    if {row["child_id"] for row in children} != declared_child_ids:
        raise RuntimeError("Child 생성 집합 불일치")
    return parents, children


def _derived_topic_code(group_id: str, exact_sales_code: str) -> str:
    prefix = f"EVD-{exact_sales_code}-"
    topic = group_id.removeprefix(prefix).removesuffix("-001")
    return re.sub(r"[^A-Z0-9]+", "_", topic).strip("_")


def _build_groups(
    inputs: dict[str, Path], children: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    contract = _read_json(inputs["gold_v2_group_contract"])
    contract_groups = {
        row["evidence_group_id"]: row for row in contract["groups"]
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for child in children:
        grouped[child["evidence_group_id"]].append(child)

    groups: list[dict[str, Any]] = []
    for group_id in sorted(grouped):
        variants = sorted(
            grouped[group_id],
            key=lambda row: (row["page_refs"][0], row["child_id"]),
        )
        if group_id in contract_groups:
            group = dict(contract_groups[group_id])
        else:
            first = variants[0]
            group = {
                "schema_version": "2.0.0-draft.1",
                "evidence_group_id": group_id,
                "topic_code": _derived_topic_code(
                    group_id, first["exact_sales_code"]
                ),
                "exact_sales_code": first["exact_sales_code"],
                "document_id": first["document_id"],
                "page_refs": sorted(
                    {page for row in variants for page in row["page_refs"]}
                ),
                "child_ids": [row["child_id"] for row in variants],
                "source_variant_ids": [
                    row["source_variant_id"] for row in variants
                ],
                "consultation_conditions": [],
                "mapping_action": "REUSE_EXISTING_GROUP",
                "supersedes_group_id": None,
                "activation_gates": ["CORPUS_V3_LINKED"],
            }
        expected_children = [row["child_id"] for row in variants]
        expected_variants = [row["source_variant_id"] for row in variants]
        if (
            group["child_ids"] != expected_children
            or group["source_variant_ids"] != expected_variants
        ):
            raise RuntimeError(f"Evidence Group Variant 계약 불일치: {group_id}")
        groups.append(group)
    return groups


def _build_corpus_and_coverage(
    config: dict[str, Any],
    baseline: list[dict[str, Any]],
    manual_pages: dict[tuple[str, int], dict[str, Any]],
    children: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    baseline_by_key = {
        (row["document_id"], row["page_refs"][0]): row for row in baseline
    }
    child_by_id = {row["child_id"]: row for row in children}
    replacements: dict[tuple[str, int], list[dict[str, Any]]] = {}
    coverage_pages: list[dict[str, Any]] = []

    for replacement in config["replacements"]:
        for page_text in sorted((int(page) for page in replacement["pages"])):
            key = (replacement["document_id"], page_text)
            source_page = baseline_by_key[key]
            lines = manual_pages[key]["text"].split("\n")
            page_chunks: list[dict[str, Any]] = []
            assignments: list[dict[str, Any]] = []
            occupied: set[int] = set()
            for segment in replacement["pages"][str(page_text)]:
                start = segment["line_start"]
                end = segment["line_end"]
                if start < 1 or end > len(lines) or start > end:
                    raise RuntimeError(
                        f"범위 오류: {replacement['exact_sales_code']} P{page_text} "
                        f"L{start}-L{end}"
                    )
                for line_number in range(start, end + 1):
                    if line_number in occupied:
                        raise RuntimeError(
                            f"행 중복: {replacement['exact_sales_code']} "
                            f"P{page_text} L{line_number}"
                        )
                    occupied.add(line_number)
                    assignments.append(
                        {
                            "line_number": line_number,
                            "classification": segment["classification"],
                            "record_id": segment["record_id"],
                            "line_sha256": _sha256_text(lines[line_number - 1]),
                        }
                    )
                if segment["classification"] == "CHILD":
                    child = child_by_id[segment["record_id"]]
                    page_chunks.append(_child_chunk(child, source_page))
                elif segment["classification"] == "PRESERVATION":
                    page_chunks.append(
                        _preservation_chunk(
                            segment["record_id"], start, end, lines, source_page
                        )
                    )
            if occupied != set(range(1, len(lines) + 1)):
                raise RuntimeError(
                    f"행 누락: {replacement['exact_sales_code']} P{page_text}"
                )
            replacements[key] = page_chunks
            coverage_pages.append(
                {
                    "exact_sales_code": replacement["exact_sales_code"],
                    "document_id": replacement["document_id"],
                    "page": page_text,
                    "total_lines": len(lines),
                    "assignments": sorted(
                        assignments, key=lambda row: row["line_number"]
                    ),
                }
            )

    corpus: list[dict[str, Any]] = []
    for source in baseline:
        key = (source["document_id"], source["page_refs"][0])
        if key in replacements:
            corpus.extend(replacements[key])
        else:
            corpus.append(_base_chunk(source))
    for index, row in enumerate(corpus, start=1):
        row["chunk_index"] = index

    coverage = {
        "schema_version": "1.0.0",
        "status": "FULL_CORPUS_V3_DATA_HANDOFF_READY",
        "generated_at": GENERATED_AT,
        "pages": coverage_pages,
    }
    return corpus, coverage


def _build_manifest(
    config: dict[str, Any],
    corpus_path: Path,
    coverage_path: Path,
    parent_path: Path,
    child_path: Path,
    group_path: Path,
    corpus: list[dict[str, Any]],
    coverage: dict[str, Any],
    parents: list[dict[str, Any]],
    children: list[dict[str, Any]],
    groups: list[dict[str, Any]],
) -> dict[str, Any]:
    output_specs = {
        "corpus": (corpus_path, DEFAULT_CORPUS_OUTPUT, len(corpus)),
        "coverage": (coverage_path, DEFAULT_COVERAGE_OUTPUT, len(coverage["pages"])),
        "context_parents": (parent_path, DEFAULT_PARENT_OUTPUT, len(parents)),
        "children": (child_path, DEFAULT_CHILD_OUTPUT, len(children)),
        "evidence_groups": (group_path, DEFAULT_GROUP_OUTPUT, len(groups)),
    }
    return {
        "schema_version": "1.0.0",
        "status": "FULL_CORPUS_V3_DATA_HANDOFF_READY",
        "generated_at": GENERATED_AT,
        "source_commit": config["source_commit"],
        "source_inventory": [
            {
                "source_inventory_id": "SRC-JAC104D-MANUAL",
                "path": config["inputs"]["jac_manual_pages"]["path"],
                "sha256": config["inputs"]["jac_manual_pages"]["sha256"],
            },
            {
                "source_inventory_id": "SRC-IAC425-MANUAL",
                "path": config["inputs"]["iac425_manual_pages"]["path"],
                "sha256": config["inputs"]["iac425_manual_pages"]["sha256"],
            },
        ],
        "inputs": config["inputs"],
        "preserved_baselines": {
            "full_corpus_v1_sha256": config["inputs"]["baseline_corpus"]["sha256"],
            "gold_v1_sha256": config["inputs"]["gold_dataset"]["sha256"],
            "full_corpus_v2_sha256": "2D4A022A8FEABD376C9F5D42E7D28BA8E18571274D19A05794D066B7113D6FC6",
        },
        "counts": {
            "search_candidates": len(corpus),
            "by_product": {
                code: sum(row["exact_sales_code"] == code for row in corpus)
                for code in ("WPUJAC104DWH", "WPUIAC425SNW")
            },
            "by_record_type": {
                record_type: sum(row["record_type"] == record_type for row in corpus)
                for record_type in ("SOURCE_PAGE", "CHILD", "PRESERVATION")
            },
            "context_only_parents": len(parents),
            "evidence_groups": len(groups),
            "registry_children": len(children),
            "iac425_evidence_groups": sum(
                row["exact_sales_code"] == "WPUIAC425SNW" for row in groups
            ),
            "iac425_children": sum(
                row["exact_sales_code"] == "WPUIAC425SNW" for row in children
            ),
        },
        "outputs": {
            name: {
                "path": _logical_output_path(path, canonical),
                "record_count": count,
                "sha256": _sha256_file(path),
            }
            for name, (path, canonical, count) in output_specs.items()
        },
        "schemas": {
            path: _sha256_file(REPOSITORY_ROOT / path)
            for path in (
                CORPUS_SCHEMA,
                COVERAGE_SCHEMA,
                PARENT_SCHEMA,
                CHILD_SCHEMA,
                GROUP_SCHEMA,
                SOURCE_REVIEW_SCHEMA,
            )
        },
        "source_span_review_status": "DATA_QA_SOURCE_SPAN_VERIFIED",
        "gold_signoff_status": "HUMAN_SIGNOFF_PENDING",
        "publication_limits": [
            "기존 Full Corpus v1·v2와 Gold v1 원본은 수정하지 않는다.",
            "Source Span 승인은 Gold Case의 TWO_PERSON_APPROVED를 뜻하지 않는다.",
            "Gold v2 병합과 Full B1 v2 실행은 AI 담당자의 후속 Gate다.",
            "운영 청킹 Profile 또는 AI Runner 연결 완료를 주장하지 않는다."
        ],
    }


def build(
    corpus_output: Path | None = None,
    coverage_output: Path | None = None,
    parent_output: Path | None = None,
    child_output: Path | None = None,
    group_output: Path | None = None,
    manifest_output: Path | None = None,
) -> None:
    config = _read_json(REPOSITORY_ROOT / CONFIG_PATH)
    inputs = _resolved_inputs(config)
    baseline = _read_jsonl(inputs["baseline_corpus"])
    manual_pages = _build_manual_maps(config, inputs)
    parents, children = _build_parents_and_children(
        config, inputs, baseline, manual_pages
    )
    groups = _build_groups(inputs, children)
    corpus, coverage = _build_corpus_and_coverage(
        config, baseline, manual_pages, children
    )

    corpus_path = corpus_output or REPOSITORY_ROOT / DEFAULT_CORPUS_OUTPUT
    coverage_path = coverage_output or REPOSITORY_ROOT / DEFAULT_COVERAGE_OUTPUT
    parent_path = parent_output or REPOSITORY_ROOT / DEFAULT_PARENT_OUTPUT
    child_path = child_output or REPOSITORY_ROOT / DEFAULT_CHILD_OUTPUT
    group_path = group_output or REPOSITORY_ROOT / DEFAULT_GROUP_OUTPUT
    manifest_path = manifest_output or REPOSITORY_ROOT / DEFAULT_MANIFEST_OUTPUT

    _write_jsonl(corpus_path, corpus)
    _write_json(coverage_path, coverage)
    _write_jsonl(parent_path, parents)
    _write_jsonl(child_path, children)
    _write_jsonl(group_path, groups)
    manifest = _build_manifest(
        config,
        corpus_path,
        coverage_path,
        parent_path,
        child_path,
        group_path,
        corpus,
        coverage,
        parents,
        children,
        groups,
    )
    _write_json(manifest_path, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=DEFAULT_CORPUS_OUTPUT)
    parser.add_argument("--coverage", default=DEFAULT_COVERAGE_OUTPUT)
    parser.add_argument("--parents", default=DEFAULT_PARENT_OUTPUT)
    parser.add_argument("--children", default=DEFAULT_CHILD_OUTPUT)
    parser.add_argument("--groups", default=DEFAULT_GROUP_OUTPUT)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST_OUTPUT)
    args = parser.parse_args()
    build(
        REPOSITORY_ROOT / args.corpus,
        REPOSITORY_ROOT / args.coverage,
        REPOSITORY_ROOT / args.parents,
        REPOSITORY_ROOT / args.children,
        REPOSITORY_ROOT / args.groups,
        REPOSITORY_ROOT / args.manifest,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
