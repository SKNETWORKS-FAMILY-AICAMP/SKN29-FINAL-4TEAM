from __future__ import annotations

import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer


ROOT = Path(__file__).resolve().parents[3]

PREFLIGHT_PATH = ROOT / ".runtime/e02_v2/preflight.json"

MANUAL_FILES = {
    "WPUJAC104DWH": ROOT / "data/processed/documents/manuals/mvp/manual_pages_jac104d.jsonl",
    "WPUIAC425SNW": ROOT / "data/processed/documents/manuals/expansion/manual_pages_iac425.jsonl",
    "WPUIAC606SNW": ROOT / "data/processed/documents/manuals/expansion/manual_pages_iac606.jsonl",
}

CHILD_PATH = ROOT / "data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl"
GROUP_PATH = ROOT / "data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl"

OUT_DIR = ROOT / ".runtime/e02_v2"
VARIANT_DIR = OUT_DIR / "variants"
MANIFEST_PATH = OUT_DIR / "manifest.json"
MAPPING_QA_PATH = OUT_DIR / "mapping_qa.json"

MODEL_NAME = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"

FIXED_WINDOW = 512
FIXED_OVERLAP = 64

SECTION_WINDOW = 512
SECTION_OVERLAP = 64

PC_WINDOW = 256
PC_OVERLAP = 32

MIN_BEST_OVERLAP_RATIO = 0.50
MIN_CANDIDATES_PER_MODEL = 20

VARIANTS = (
    "fixed512",
    "section_aware_512",
    "parent_child_256",
)

BUILD_SCRIPT_VERSION = "1.0"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, raw in enumerate(f, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception as exc:
                raise RuntimeError(
                    f"{path.relative_to(ROOT)}:{line_no} JSON parse 실패: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise RuntimeError(
                    f"{path.relative_to(ROOT)}:{line_no} JSON object가 아닙니다."
                )
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def git_branch() -> str:
    return subprocess.check_output(
        ["git", "branch", "--show-current"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def page_id(row: dict[str, Any]) -> str:
    return str(
        row.get("page_id")
        or row.get("source_record_id")
        or ""
    )


def child_id(row: dict[str, Any]) -> str:
    return str(
        row.get("child_id")
        or row.get("chunk_id")
        or ""
    )


def section_key(row: dict[str, Any]) -> tuple[str, str]:
    sid = str(row.get("section_id") or "").strip()
    title = str(row.get("section_title") or "").strip()
    if sid:
        return sid, title
    page = int(row["page"])
    return f"PAGE-{page:03d}", title or f"Page {page}"


def load_tokenizer():
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        revision=MODEL_REVISION,
        local_files_only=True,
        use_fast=True,
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("Fast tokenizer가 필요합니다.")
    return tokenizer


def token_windows(
    tokenizer,
    text: str,
    *,
    window: int,
    overlap: int,
) -> list[dict[str, Any]]:
    encoded = tokenizer(
        text,
        add_special_tokens=False,
        return_offsets_mapping=True,
    )
    ids = list(encoded["input_ids"])
    offsets = [tuple(pair) for pair in encoded["offset_mapping"]]

    if not ids:
        return [{
            "token_start": 0,
            "token_end": 0,
            "char_start": 0,
            "char_end": 0,
            "text": "",
        }]

    step = window - overlap
    rows: list[dict[str, Any]] = []

    for start in range(0, len(ids), step):
        end = min(start + window, len(ids))
        chunk_offsets = [
            (a, b)
            for a, b in offsets[start:end]
            if b > a
        ]
        if chunk_offsets:
            char_start = chunk_offsets[0][0]
            char_end = chunk_offsets[-1][1]
        else:
            char_start = 0
            char_end = 0

        rows.append({
            "token_start": start,
            "token_end": end,
            "char_start": char_start,
            "char_end": char_end,
            "text": text[char_start:char_end],
        })

        if end >= len(ids):
            break

    return rows


def consecutive_sections(
    pages: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    ordered = sorted(pages, key=lambda row: int(row["page"]))
    result: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_key: tuple[str, str] | None = None

    for row in ordered:
        key = section_key(row)
        if current and key != current_key:
            result.append(current)
            current = []
        current.append(row)
        current_key = key

    if current:
        result.append(current)

    return result


def compose_section(
    pages: list[dict[str, Any]],
) -> dict[str, Any]:
    parts: list[str] = []
    page_offsets: dict[str, tuple[int, int]] = {}
    cursor = 0

    for index, row in enumerate(pages):
        if index:
            separator = "\n\n"
            parts.append(separator)
            cursor += len(separator)

        text = str(row["text"])
        start = cursor
        parts.append(text)
        cursor += len(text)
        page_offsets[page_id(row)] = (start, cursor)

    text = "".join(parts)
    sid, title = section_key(pages[0])

    return {
        "section_id": sid,
        "section_title": title,
        "exact_sales_code": str(pages[0]["exact_sales_code"]),
        "document_id": str(pages[0]["document_id"]),
        "page_refs": [int(row["page"]) for row in pages],
        "page_ids": [page_id(row) for row in pages],
        "page_offsets": page_offsets,
        "text": text,
    }


def locate_gold_spans(
    all_pages: list[dict[str, Any]],
    children: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_page = {page_id(row): row for row in all_pages}
    spans: list[dict[str, Any]] = []

    for child in children:
        cid = child_id(child)
        parent_id = str(child.get("parent_id") or "")
        page = by_page.get(parent_id)

        if page is None:
            page_refs = list(child.get("page_refs") or [])
            document_id = str(child.get("document_id") or "")
            if len(page_refs) == 1:
                matches = [
                    row
                    for row in all_pages
                    if str(row.get("document_id") or "") == document_id
                    and int(row.get("page") or -1) == int(page_refs[0])
                ]
                if len(matches) == 1:
                    page = matches[0]

        if page is None:
            raise RuntimeError(f"{cid}: Full page를 찾지 못했습니다.")

        source_span = child.get("source_span") or {}
        start_anchor = str(source_span.get("start_anchor") or "")
        end_anchor = str(source_span.get("end_anchor") or "")

        if not start_anchor or not end_anchor:
            raise RuntimeError(f"{cid}: source anchor 누락")

        text = str(page["text"])
        start = text.find(start_anchor)
        if start < 0:
            raise RuntimeError(f"{cid}: start anchor 불일치")

        end_start = text.find(end_anchor, start)
        if end_start < 0:
            raise RuntimeError(f"{cid}: end anchor 불일치")

        end = end_start + len(end_anchor)

        spans.append({
            "source_child_id": cid,
            "evidence_group_id": str(child["evidence_group_id"]),
            "exact_sales_code": str(child["exact_sales_code"]),
            "document_id": str(child["document_id"]),
            "page_id": page_id(page),
            "page": int(page["page"]),
            "page_char_start": start,
            "page_char_end": end,
            "span_chars": end - start,
        })

    return spans


def common_row(
    *,
    variant: str,
    chunk_id_value: str,
    exact_sales_code: str,
    document_id: str,
    page_refs: list[int],
    section_id: str,
    section_title: str,
    text: str,
    token_start: int,
    token_end: int,
    char_start: int,
    char_end: int,
    context_text: str | None = None,
    source_unit_id: str,
) -> dict[str, Any]:
    row = {
        "experiment_id": "E02-v2",
        "chunking_variant": variant,
        "chunk_id": chunk_id_value,
        "record_type": "child",
        "retrieval_role": "SEARCH_CANDIDATE",
        "allowed_use": "EXPERIMENT_ONLY",
        "exact_sales_code": exact_sales_code,
        "document_id": document_id,
        "page_refs": sorted(set(page_refs)),
        "section_id": section_id,
        "section_title": section_title,
        "source_unit_id": source_unit_id,
        "tokenizer_model": MODEL_NAME,
        "tokenizer_revision": MODEL_REVISION,
        "token_start": token_start,
        "token_end": token_end,
        "char_start": char_start,
        "char_end": char_end,
        "text": text,
        "text_sha256": sha256_text(text),
        "source_child_ids": [],
        "evidence_group_ids": [],
        "gold_span_assignments": [],
    }
    if context_text is not None:
        row["context_text"] = context_text
        row["context_text_sha256"] = sha256_text(context_text)
    return row


def build_fixed512(
    tokenizer,
    pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for page in sorted(
        pages,
        key=lambda row: (
            str(row["exact_sales_code"]),
            int(row["page"]),
        ),
    ):
        pid = page_id(page)
        text = str(page["text"])
        sid, title = section_key(page)

        for index, window in enumerate(
            token_windows(
                tokenizer,
                text,
                window=FIXED_WINDOW,
                overlap=FIXED_OVERLAP,
            ),
            start=1,
        ):
            rows.append(
                common_row(
                    variant="fixed512",
                    chunk_id_value=f"{pid}::fixed512::{index:03d}",
                    exact_sales_code=str(page["exact_sales_code"]),
                    document_id=str(page["document_id"]),
                    page_refs=[int(page["page"])],
                    section_id=sid,
                    section_title=title,
                    text=window["text"],
                    token_start=window["token_start"],
                    token_end=window["token_end"],
                    char_start=window["char_start"],
                    char_end=window["char_end"],
                    source_unit_id=pid,
                )
            )

    return rows


def build_section_variants(
    tokenizer,
    pages_by_model: dict[str, list[dict[str, Any]]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    section_rows: list[dict[str, Any]] = []
    pc_rows: list[dict[str, Any]] = []
    section_units: dict[str, dict[str, Any]] = {}

    for model, pages in pages_by_model.items():
        for section_index, section_pages in enumerate(
            consecutive_sections(pages),
            start=1,
        ):
            unit = compose_section(section_pages)
            unit_id = (
                f"{unit['document_id']}::"
                f"{unit['section_id']}::{section_index:03d}"
            )
            unit["source_unit_id"] = unit_id
            section_units[unit_id] = unit

            section_windows = token_windows(
                tokenizer,
                unit["text"],
                window=SECTION_WINDOW,
                overlap=SECTION_OVERLAP,
            )
            for index, window in enumerate(section_windows, start=1):
                section_rows.append(
                    common_row(
                        variant="section_aware_512",
                        chunk_id_value=(
                            f"{unit_id}::section512::{index:03d}"
                        ),
                        exact_sales_code=model,
                        document_id=unit["document_id"],
                        page_refs=unit["page_refs"],
                        section_id=unit["section_id"],
                        section_title=unit["section_title"],
                        text=window["text"],
                        token_start=window["token_start"],
                        token_end=window["token_end"],
                        char_start=window["char_start"],
                        char_end=window["char_end"],
                        source_unit_id=unit_id,
                    )
                )

            pc_windows = token_windows(
                tokenizer,
                unit["text"],
                window=PC_WINDOW,
                overlap=PC_OVERLAP,
            )
            for index, window in enumerate(pc_windows, start=1):
                pc_rows.append(
                    common_row(
                        variant="parent_child_256",
                        chunk_id_value=(
                            f"{unit_id}::pc256::{index:03d}"
                        ),
                        exact_sales_code=model,
                        document_id=unit["document_id"],
                        page_refs=unit["page_refs"],
                        section_id=unit["section_id"],
                        section_title=unit["section_title"],
                        text=window["text"],
                        token_start=window["token_start"],
                        token_end=window["token_end"],
                        char_start=window["char_start"],
                        char_end=window["char_end"],
                        context_text=unit["text"],
                        source_unit_id=unit_id,
                    )
                )

    return section_rows, pc_rows, section_units


def char_overlap(
    a_start: int,
    a_end: int,
    b_start: int,
    b_end: int,
) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def assign_gold_fixed(
    rows: list[dict[str, Any]],
    spans: list[dict[str, Any]],
) -> dict[str, Any]:
    by_page: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_page[str(row["source_unit_id"])].append(row)

    assignments = []
    below = []

    for span in spans:
        candidates = by_page.get(span["page_id"], [])
        if not candidates:
            raise RuntimeError(
                f"fixed512: {span['page_id']} 후보 Chunk 없음"
            )

        ranked = []
        for row in candidates:
            overlap = char_overlap(
                span["page_char_start"],
                span["page_char_end"],
                int(row["char_start"]),
                int(row["char_end"]),
            )
            ratio = overlap / span["span_chars"]
            ranked.append((ratio, overlap, -int(row["token_start"]), row))

        ratio, overlap, _, best = max(
            ranked,
            key=lambda item: (item[0], item[1], item[2]),
        )

        assignment = {
            "source_child_id": span["source_child_id"],
            "evidence_group_id": span["evidence_group_id"],
            "assigned_chunk_id": best["chunk_id"],
            "overlap_chars": overlap,
            "span_chars": span["span_chars"],
            "overlap_ratio": round(ratio, 6),
            "mapping_policy": "MAX_CHAR_OVERLAP_SINGLE_CHUNK",
        }
        assignments.append(assignment)
        if ratio < MIN_BEST_OVERLAP_RATIO:
            below.append(assignment)

        best["source_child_ids"].append(span["source_child_id"])
        best["evidence_group_ids"].append(span["evidence_group_id"])
        best["gold_span_assignments"].append(assignment)

    return finalize_assignments(rows, assignments, below)


def map_span_to_section_unit(
    span: dict[str, Any],
    section_units: dict[str, dict[str, Any]],
) -> tuple[str, int, int]:
    matches = []

    for unit_id, unit in section_units.items():
        offset = unit["page_offsets"].get(span["page_id"])
        if offset is None:
            continue
        if unit["exact_sales_code"] != span["exact_sales_code"]:
            continue

        page_start, _ = offset
        matches.append(
            (
                unit_id,
                page_start + span["page_char_start"],
                page_start + span["page_char_end"],
            )
        )

    if len(matches) != 1:
        raise RuntimeError(
            f"{span['source_child_id']}: section unit 매핑 수={len(matches)}"
        )

    return matches[0]


def assign_gold_section_based(
    *,
    variant: str,
    rows: list[dict[str, Any]],
    spans: list[dict[str, Any]],
    section_units: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_unit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_unit[str(row["source_unit_id"])].append(row)

    assignments = []
    below = []

    for span in spans:
        unit_id, start, end = map_span_to_section_unit(
            span,
            section_units,
        )
        candidates = by_unit.get(unit_id, [])
        if not candidates:
            raise RuntimeError(
                f"{variant}: {unit_id} 후보 Chunk 없음"
            )

        ranked = []
        for row in candidates:
            overlap = char_overlap(
                start,
                end,
                int(row["char_start"]),
                int(row["char_end"]),
            )
            ratio = overlap / span["span_chars"]
            ranked.append((ratio, overlap, -int(row["token_start"]), row))

        ratio, overlap, _, best = max(
            ranked,
            key=lambda item: (item[0], item[1], item[2]),
        )

        assignment = {
            "source_child_id": span["source_child_id"],
            "evidence_group_id": span["evidence_group_id"],
            "assigned_chunk_id": best["chunk_id"],
            "overlap_chars": overlap,
            "span_chars": span["span_chars"],
            "overlap_ratio": round(ratio, 6),
            "mapping_policy": "MAX_CHAR_OVERLAP_SINGLE_CHUNK",
        }
        assignments.append(assignment)
        if ratio < MIN_BEST_OVERLAP_RATIO:
            below.append(assignment)

        best["source_child_ids"].append(span["source_child_id"])
        best["evidence_group_ids"].append(span["evidence_group_id"])
        best["gold_span_assignments"].append(assignment)

    return finalize_assignments(rows, assignments, below)


def finalize_assignments(
    rows: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    below: list[dict[str, Any]],
) -> dict[str, Any]:
    for row in rows:
        row["source_child_ids"] = list(
            dict.fromkeys(row["source_child_ids"])
        )
        row["evidence_group_ids"] = list(
            dict.fromkeys(row["evidence_group_ids"])
        )

    ratios = [
        float(item["overlap_ratio"])
        for item in assignments
    ]

    return {
        "assignment_count": len(assignments),
        "minimum_best_overlap_ratio": min(ratios, default=0.0),
        "mean_best_overlap_ratio": (
            round(sum(ratios) / len(ratios), 6)
            if ratios
            else 0.0
        ),
        "full_coverage_assignment_count": sum(
            ratio == 1.0 for ratio in ratios
        ),
        "partial_assignment_count": sum(
            ratio < 1.0 for ratio in ratios
        ),
        "below_minimum_count": len(below),
        "below_minimum": below,
    }


def variant_stats(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    token_counts = [
        int(row["token_end"]) - int(row["token_start"])
        for row in rows
    ]
    group_counts = [
        len(row.get("evidence_group_ids") or [])
        for row in rows
    ]
    candidate_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        candidate_counts[str(row["exact_sales_code"])] += 1

    return {
        "chunk_count": len(rows),
        "candidate_counts_by_model": dict(
            sorted(candidate_counts.items())
        ),
        "average_chunk_tokens": round(
            sum(token_counts) / len(token_counts),
            3,
        ),
        "max_chunk_tokens": max(token_counts),
        "chunks_with_gold": sum(
            bool(row.get("evidence_group_ids"))
            for row in rows
        ),
        "mean_gold_groups_per_chunk": round(
            sum(group_counts) / len(group_counts),
            6,
        ),
        "max_gold_groups_per_chunk": max(group_counts),
    }


def main() -> int:
    if not PREFLIGHT_PATH.exists():
        raise RuntimeError(
            "E02-v2 preflight 결과가 없습니다. "
            "e02_v2_preflight.py를 먼저 실행하세요."
        )

    preflight = json.loads(
        PREFLIGHT_PATH.read_text(encoding="utf-8")
    )
    if preflight.get("status") != "E02_V2_PREFLIGHT_READY":
        raise RuntimeError(
            f"Preflight 상태가 READY가 아닙니다: {preflight.get('status')}"
        )

    # HEAD가 바뀌어도 실험 입력 파일 자체가 그대로면 진행 가능하게 한다.
    input_hashes = preflight.get("input_hashes") or {}
    changed_inputs = []

    relevant_inputs = [
        *MANUAL_FILES.values(),
        CHILD_PATH,
        GROUP_PATH,
    ]
    for path in relevant_inputs:
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        expected = input_hashes.get(rel)
        if expected is None:
            continue
        actual = sha256_file(path)
        if actual != expected:
            changed_inputs.append({
                "path": rel,
                "expected": expected,
                "actual": actual,
            })

    if changed_inputs:
        raise RuntimeError(
            "Preflight 이후 E02-v2 입력 파일이 변경되었습니다. "
            "Preflight를 다시 실행해야 합니다:\n"
            + json.dumps(
                changed_inputs,
                ensure_ascii=False,
                indent=2,
            )
        )

    pages_by_model = {
        model: load_jsonl(path)
        for model, path in MANUAL_FILES.items()
    }
    all_pages = [
        row
        for model in MANUAL_FILES
        for row in pages_by_model[model]
    ]
    children = load_jsonl(CHILD_PATH)
    groups = load_jsonl(GROUP_PATH)

    tokenizer = load_tokenizer()
    spans = locate_gold_spans(
        all_pages,
        children,
    )

    fixed_rows = build_fixed512(
        tokenizer,
        all_pages,
    )
    section_rows, pc_rows, section_units = (
        build_section_variants(
            tokenizer,
            pages_by_model,
        )
    )

    variants = {
        "fixed512": fixed_rows,
        "section_aware_512": section_rows,
        "parent_child_256": pc_rows,
    }

    mapping = {
        "fixed512": assign_gold_fixed(
            fixed_rows,
            spans,
        ),
        "section_aware_512": assign_gold_section_based(
            variant="section_aware_512",
            rows=section_rows,
            spans=spans,
            section_units=section_units,
        ),
        "parent_child_256": assign_gold_section_based(
            variant="parent_child_256",
            rows=pc_rows,
            spans=spans,
            section_units=section_units,
        ),
    }

    expected_groups = {
        str(row["evidence_group_id"])
        for row in groups
    }
    expected_children = {
        child_id(row)
        for row in children
    }

    qa_rows = []
    errors = []
    stats = {}

    for name in VARIANTS:
        rows = variants[name]
        observed_groups = {
            gid
            for row in rows
            for gid in row.get("evidence_group_ids") or []
        }
        observed_children = {
            cid
            for row in rows
            for cid in row.get("source_child_ids") or []
        }

        candidate_counts: dict[str, int] = defaultdict(int)
        for row in rows:
            candidate_counts[str(row["exact_sales_code"])] += 1

        low_candidate_models = {
            model: count
            for model, count in candidate_counts.items()
            if count < MIN_CANDIDATES_PER_MODEL
        }

        qa_status = "PASS"
        qa_errors = []

        if observed_groups != expected_groups:
            qa_status = "FAIL"
            missing = sorted(expected_groups - observed_groups)
            qa_errors.append(
                f"Evidence Group 미커버 {len(missing)}건"
            )

        if observed_children != expected_children:
            qa_status = "FAIL"
            missing = sorted(expected_children - observed_children)
            qa_errors.append(
                f"Source Child 미커버 {len(missing)}건"
            )

        if mapping[name]["below_minimum_count"] > 0:
            qa_status = "FAIL"
            qa_errors.append(
                "Gold overlap ratio가 최소 기준 미만"
            )

        if low_candidate_models:
            qa_status = "FAIL"
            qa_errors.append(
                f"후보 Chunk 최소 {MIN_CANDIDATES_PER_MODEL} 미만: "
                f"{low_candidate_models}"
            )

        qa_rows.append({
            "variant": name,
            "status": qa_status,
            "evidence_group_coverage": (
                f"{len(observed_groups)}/{len(expected_groups)}"
            ),
            "source_child_span_coverage": (
                f"{len(observed_children)}/{len(expected_children)}"
            ),
            "minimum_best_overlap_ratio": mapping[name][
                "minimum_best_overlap_ratio"
            ],
            "partial_assignment_count": mapping[name][
                "partial_assignment_count"
            ],
            "candidate_counts_by_model": dict(
                sorted(candidate_counts.items())
            ),
            "errors": qa_errors,
        })

        if qa_errors:
            errors.extend(
                f"{name}: {message}"
                for message in qa_errors
            )

        stats[name] = variant_stats(rows)

    status = (
        "E02_V2_VARIANTS_READY"
        if not errors
        else "E02_V2_VARIANTS_BLOCKED"
    )

    VARIANT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    for name, rows in variants.items():
        write_jsonl(
            VARIANT_DIR / f"{name}.jsonl",
            rows,
        )

    current_sha = git_sha()
    manifest = {
        "status": status,
        "experiment_id": "E02-v2",
        "build_script_version": BUILD_SCRIPT_VERSION,
        "source": {
            "preflight_git_sha": preflight["git"]["head_sha"],
            "build_git_sha": current_sha,
            "branch": git_branch(),
            "manual_page_count": len(all_pages),
            "e01_child_count": len(children),
            "evidence_group_count": len(groups),
        },
        "chunking_contract": {
            "fixed512": {
                "window_tokens": FIXED_WINDOW,
                "overlap_tokens": FIXED_OVERLAP,
                "source_boundary": "PAGE",
            },
            "section_aware_512": {
                "window_tokens": SECTION_WINDOW,
                "overlap_tokens": SECTION_OVERLAP,
                "source_boundary": "CONSECUTIVE_SECTION",
            },
            "parent_child_256": {
                "child_window_tokens": PC_WINDOW,
                "child_overlap_tokens": PC_OVERLAP,
                "retrieval_text": "CHILD_ONLY",
                "context_text": "FULL_SECTION_PARENT",
            },
        },
        "mapping_policy": {
            "policy": "MAX_CHAR_OVERLAP_SINGLE_CHUNK",
            "minimum_best_overlap_ratio": MIN_BEST_OVERLAP_RATIO,
            "reason": (
                "window 경계에서 Gold span이 분리되어도 정답 Label을 "
                "여러 Chunk에 중복 부여하지 않고 가장 많이 겹치는 한 Chunk에만 매핑"
            ),
        },
        "difficulty_gate": {
            "top_k": 5,
            "minimum_candidates_per_model": MIN_CANDIDATES_PER_MODEL,
        },
        "variant_statistics": stats,
        "mapping_qa": qa_rows,
        "input_hashes": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
            for path in relevant_inputs
        },
        "errors": errors,
    }

    MAPPING_QA_PATH.write_text(
        json.dumps(
            {
                "status": status,
                "mapping": mapping,
                "qa": qa_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    compact = {
        "status": status,
        "preflight_git_sha": preflight["git"]["head_sha"],
        "build_git_sha": current_sha,
        "variants": {
            name: {
                "chunks": stats[name]["chunk_count"],
                "candidate_counts_by_model": stats[name][
                    "candidate_counts_by_model"
                ],
                "group_coverage": next(
                    row["evidence_group_coverage"]
                    for row in qa_rows
                    if row["variant"] == name
                ),
                "child_span_coverage": next(
                    row["source_child_span_coverage"]
                    for row in qa_rows
                    if row["variant"] == name
                ),
                "avg_tokens": stats[name]["average_chunk_tokens"],
                "max_tokens": stats[name]["max_chunk_tokens"],
                "min_best_overlap_ratio": mapping[name][
                    "minimum_best_overlap_ratio"
                ],
                "partial_assignments": mapping[name][
                    "partial_assignment_count"
                ],
            }
            for name in VARIANTS
        },
        "output_dir": ".runtime/e02_v2",
        "errors": errors,
    }

    print(
        json.dumps(
            compact,
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
