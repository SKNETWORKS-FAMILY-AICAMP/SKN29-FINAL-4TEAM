from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer


ROOT = Path(__file__).resolve().parents[3]

MANUAL_FILES = {
    "WPUJAC104DWH": ROOT / "data/processed/documents/manuals/mvp/manual_pages_jac104d.jsonl",
    "WPUIAC425SNW": ROOT / "data/processed/documents/manuals/expansion/manual_pages_iac425.jsonl",
    "WPUIAC606SNW": ROOT / "data/processed/documents/manuals/expansion/manual_pages_iac606.jsonl",
}

FAQ_PATH = ROOT / "data/processed/documents/faq/faq_snapshot_normalized.jsonl"
E01_CHILD_PATH = ROOT / "data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl"
E01_GROUP_PATH = ROOT / "data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl"
E01_CASE_PATH = ROOT / "data/config/rag/three_model_evaluation_cases.json"
GOLD_V2_PATH = ROOT / "ai/evaluation/datasets/gold/rag_gold_v2.jsonl"

OUT_DIR = ROOT / ".runtime/e02_v2"
OUT_PATH = OUT_DIR / "preflight.json"

MODEL_NAME = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"

FIXED_WINDOW = 512
FIXED_OVERLAP = 64

SECTION_WINDOW = 512
SECTION_OVERLAP = 64

PC_CHILD_WINDOW = 256
PC_CHILD_OVERLAP = 32

TOP_K = 5
MIN_CANDIDATES_PER_MODEL = 20

EXPECTED_PAGE_COUNTS = {
    "WPUJAC104DWH": 44,
    "WPUIAC425SNW": 52,
    "WPUIAC606SNW": 48,
}

EXPECTED_TOTAL_PAGES = 144
EXPECTED_FAQ_COUNT = 119
EXPECTED_E01_CHILD_COUNT = 53
EXPECTED_E01_GROUP_COUNT = 43
EXPECTED_E01_CASE_COUNT = 50


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


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def git_value(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def load_e01_cases() -> list[dict[str, Any]]:
    data = load_json(E01_CASE_PATH)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("cases", "evaluation_cases", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    raise RuntimeError("E01 Case JSON 구조를 해석하지 못했습니다.")


def tokenize_len(tokenizer, text: str) -> int:
    return len(
        tokenizer(
            text,
            add_special_tokens=False,
        )["input_ids"]
    )


def window_count(token_count: int, window: int, overlap: int) -> int:
    if token_count <= 0:
        return 1
    if token_count <= window:
        return 1
    step = window - overlap
    return 1 + (token_count - window + step - 1) // step


def page_section_key(row: dict[str, Any]) -> tuple[str, str]:
    section_id = str(row.get("section_id") or "").strip()
    section_title = str(row.get("section_title") or "").strip()
    if section_id:
        return (section_id, section_title)
    return (
        f"PAGE-{int(row['page']):03d}",
        section_title or f"Page {int(row['page'])}",
    )


def consecutive_sections(
    rows: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    ordered = sorted(rows, key=lambda row: int(row["page"]))
    sections: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_key: tuple[str, str] | None = None

    for row in ordered:
        key = page_section_key(row)
        if current and key != current_key:
            sections.append(current)
            current = []
        current.append(row)
        current_key = key

    if current:
        sections.append(current)

    return sections


def page_record_id(row: dict[str, Any]) -> str:
    return str(
        row.get("page_id")
        or row.get("source_record_id")
        or ""
    )


def locate_child_on_full_page(
    child: dict[str, Any],
    page: dict[str, Any],
) -> tuple[bool, str | None]:
    span = child.get("source_span")
    if not isinstance(span, dict):
        return False, "SOURCE_SPAN_MISSING"

    text = str(page.get("text") or "")
    start_anchor = str(span.get("start_anchor") or "")
    end_anchor = str(span.get("end_anchor") or "")

    if not start_anchor or not end_anchor:
        return False, "ANCHOR_MISSING"

    start = text.find(start_anchor)
    if start < 0:
        return False, "START_ANCHOR_NOT_FOUND"

    end = text.find(end_anchor, start)
    if end < 0:
        return False, "END_ANCHOR_NOT_FOUND"

    return True, None


def group_ids_from_case(row: dict[str, Any]) -> set[str]:
    ids = set()
    for key in (
        "required_evidence_group_ids",
        "supporting_evidence_group_ids",
        "expected_evidence_group_ids",
    ):
        value = row.get(key)
        if isinstance(value, list):
            ids.update(str(item) for item in value if item)
    return ids


def main() -> int:
    required = [
        *MANUAL_FILES.values(),
        FAQ_PATH,
        E01_CHILD_PATH,
        E01_GROUP_PATH,
        E01_CASE_PATH,
        GOLD_V2_PATH,
    ]
    missing = [
        str(path.relative_to(ROOT))
        for path in required
        if not path.exists()
    ]
    if missing:
        raise RuntimeError(
            "필수 입력 파일이 없습니다: " + ", ".join(missing)
        )

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        revision=MODEL_REVISION,
        local_files_only=True,
        use_fast=True,
    )

    manual_rows_by_model: dict[str, list[dict[str, Any]]] = {}
    all_manual_rows: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    for model, path in MANUAL_FILES.items():
        rows = load_jsonl(path)
        manual_rows_by_model[model] = rows
        all_manual_rows.extend(rows)

        expected = EXPECTED_PAGE_COUNTS[model]
        if len(rows) != expected:
            errors.append(
                f"{model} page count={len(rows)}, expected={expected}"
            )

        bad_model_rows = [
            page_record_id(row)
            for row in rows
            if str(row.get("exact_sales_code") or "") != model
        ]
        if bad_model_rows:
            errors.append(
                f"{model} exact_sales_code 불일치 {len(bad_model_rows)}건"
            )

        pages = sorted(int(row["page"]) for row in rows)
        if pages != list(range(1, expected + 1)):
            errors.append(
                f"{model} page sequence가 1..{expected} 연속이 아닙니다."
            )

        empty_text = [
            page_record_id(row)
            for row in rows
            if not str(row.get("text") or "").strip()
        ]
        if empty_text:
            errors.append(
                f"{model} 빈 page text {len(empty_text)}건"
            )

    if len(all_manual_rows) != EXPECTED_TOTAL_PAGES:
        errors.append(
            f"전체 Manual page={len(all_manual_rows)}, expected={EXPECTED_TOTAL_PAGES}"
        )

    faq_rows = load_jsonl(FAQ_PATH)
    if len(faq_rows) != EXPECTED_FAQ_COUNT:
        errors.append(
            f"FAQ count={len(faq_rows)}, expected={EXPECTED_FAQ_COUNT}"
        )

    faq_ids = {
        str(row.get("faq_id") or "")
        for row in faq_rows
        if row.get("faq_id")
    }
    if len(faq_ids) != len(faq_rows):
        errors.append("FAQ ID 누락 또는 중복이 있습니다.")

    e01_children = load_jsonl(E01_CHILD_PATH)
    e01_groups = load_jsonl(E01_GROUP_PATH)
    e01_cases = load_e01_cases()

    if len(e01_children) != EXPECTED_E01_CHILD_COUNT:
        errors.append(
            f"E01 Child={len(e01_children)}, expected={EXPECTED_E01_CHILD_COUNT}"
        )
    if len(e01_groups) != EXPECTED_E01_GROUP_COUNT:
        errors.append(
            f"E01 Group={len(e01_groups)}, expected={EXPECTED_E01_GROUP_COUNT}"
        )
    if len(e01_cases) != EXPECTED_E01_CASE_COUNT:
        errors.append(
            f"E01 Case={len(e01_cases)}, expected={EXPECTED_E01_CASE_COUNT}"
        )

    # Full 144-page corpus에서 기존 53 Child의 source span을 정확히 복원할 수 있는지 확인.
    page_map: dict[str, dict[str, Any]] = {}
    for row in all_manual_rows:
        pid = page_record_id(row)
        if not pid:
            errors.append("Full Manual page_id 누락 행이 있습니다.")
            continue
        if pid in page_map:
            errors.append(f"Full Manual page_id 중복: {pid}")
        page_map[pid] = row

    lineage_ok = 0
    lineage_failures: list[dict[str, str]] = []

    for child in e01_children:
        cid = str(child.get("child_id") or child.get("chunk_id") or "")
        parent_id = str(child.get("parent_id") or "")
        page_refs = list(child.get("page_refs") or [])

        # 3모델 handoff의 parent_id가 page_id 기반이므로 우선 parent_id로 찾고,
        # 필요하면 document_id + 단일 page_ref로 fallback한다.
        page = page_map.get(parent_id)

        if page is None and len(page_refs) == 1:
            document_id = str(child.get("document_id") or "")
            page_number = int(page_refs[0])
            matches = [
                row
                for row in all_manual_rows
                if str(row.get("document_id") or "") == document_id
                and int(row.get("page") or -1) == page_number
            ]
            if len(matches) == 1:
                page = matches[0]

        if page is None:
            lineage_failures.append(
                {
                    "child_id": cid,
                    "reason": "FULL_PAGE_NOT_FOUND",
                }
            )
            continue

        if str(page.get("exact_sales_code")) != str(child.get("exact_sales_code")):
            lineage_failures.append(
                {
                    "child_id": cid,
                    "reason": "MODEL_MISMATCH",
                }
            )
            continue

        ok, reason = locate_child_on_full_page(child, page)
        if not ok:
            lineage_failures.append(
                {
                    "child_id": cid,
                    "reason": str(reason),
                }
            )
            continue

        lineage_ok += 1

    if lineage_ok != EXPECTED_E01_CHILD_COUNT:
        errors.append(
            f"E01 Child → Full 144-page source span 복원 "
            f"{lineage_ok}/{EXPECTED_E01_CHILD_COUNT}"
        )

    # 청킹 전략별 "실험 난도" 사전 계산.
    candidate_counts: dict[str, dict[str, int]] = {
        "fixed512": {},
        "section_aware_512": {},
        "parent_child_256": {},
    }
    structural: dict[str, dict[str, Any]] = {}

    for model, rows in manual_rows_by_model.items():
        # Fixed512: 페이지 경계를 넘지 않는 tokenizer window.
        fixed_count = 0
        page_token_lengths = []
        for row in rows:
            tokens = tokenize_len(tokenizer, str(row["text"]))
            page_token_lengths.append(tokens)
            fixed_count += window_count(
                tokens,
                FIXED_WINDOW,
                FIXED_OVERLAP,
            )
        candidate_counts["fixed512"][model] = fixed_count

        # Section-aware-512: 실제 연속 section을 병합한 뒤 512/64로 다시 분할.
        sections = consecutive_sections(rows)
        section_count = 0
        section_token_lengths = []
        for section_rows in sections:
            text = "\n\n".join(
                str(row["text"])
                for row in section_rows
            )
            tokens = tokenize_len(tokenizer, text)
            section_token_lengths.append(tokens)
            section_count += window_count(
                tokens,
                SECTION_WINDOW,
                SECTION_OVERLAP,
            )
        candidate_counts["section_aware_512"][model] = section_count

        # Parent-Child: Section 전체를 Parent context로 유지하되
        # 검색 대상 Child는 256/32 window.
        pc_count = 0
        for section_rows in sections:
            text = "\n\n".join(
                str(row["text"])
                for row in section_rows
            )
            tokens = tokenize_len(tokenizer, text)
            pc_count += window_count(
                tokens,
                PC_CHILD_WINDOW,
                PC_CHILD_OVERLAP,
            )
        candidate_counts["parent_child_256"][model] = pc_count

        structural[model] = {
            "page_count": len(rows),
            "section_count": len(sections),
            "page_tokens": {
                "min": min(page_token_lengths),
                "max": max(page_token_lengths),
                "mean": round(
                    sum(page_token_lengths) / len(page_token_lengths),
                    3,
                ),
            },
            "section_tokens": {
                "min": min(section_token_lengths),
                "max": max(section_token_lengths),
                "mean": round(
                    sum(section_token_lengths) / len(section_token_lengths),
                    3,
                ),
            },
        }

    difficulty_gate: dict[str, dict[str, Any]] = {}
    for strategy, counts in candidate_counts.items():
        ratios = {
            model: round(TOP_K / count, 4)
            for model, count in counts.items()
        }
        minimum = min(counts.values())
        status = (
            "PASS"
            if minimum >= MIN_CANDIDATES_PER_MODEL
            else "FAIL"
        )
        difficulty_gate[strategy] = {
            "status": status,
            "candidate_counts_by_model": counts,
            "top5_candidate_fraction_by_model": ratios,
            "minimum_candidates_after_product_filter": minimum,
            "required_minimum": MIN_CANDIDATES_PER_MODEL,
        }
        if status != "PASS":
            errors.append(
                f"{strategy} 제품 필터 후 최소 후보 수={minimum}, "
                f"required>={MIN_CANDIDATES_PER_MODEL}"
            )

    # FAQ 119건 자체를 Corpus에 넣지 않고, 이미 Gold v2에서 FAQ → Evidence
    # mapping이 부여된 Case만 supplemental diagnostic query 후보로 집계한다.
    gold_v2 = load_jsonl(GOLD_V2_PATH)
    active_gold = [
        row
        for row in gold_v2
        if str(row.get("evaluation_status") or "").upper() == "ACTIVE"
    ]
    faq_origin_active = [
        row
        for row in active_gold
        if str(row.get("source_query_origin") or "").upper() == "EXISTING_FAQ"
    ]

    e01_group_ids = {
        str(row["evidence_group_id"])
        for row in e01_groups
    }
    supported_models = set(MANUAL_FILES)

    faq_compatible: list[dict[str, Any]] = []
    faq_incompatible: list[dict[str, Any]] = []

    for row in faq_origin_active:
        source_ids = [
            str(value)
            for value in (row.get("source_case_ids") or [])
            if str(value).startswith("FAQ-")
        ]
        required_groups = group_ids_from_case(row)

        reasons = []
        missing_faq_ids = [
            faq_id
            for faq_id in source_ids
            if faq_id not in faq_ids
        ]
        if missing_faq_ids:
            reasons.append(
                "FAQ_SOURCE_NOT_FOUND:" + ",".join(missing_faq_ids)
            )

        unknown_groups = sorted(
            required_groups - e01_group_ids
        )
        if unknown_groups:
            reasons.append(
                "OUTSIDE_E01_GROUP_UNIVERSE:" + ",".join(unknown_groups)
            )

        model = str(row.get("product_model_code") or "")
        if model not in supported_models:
            reasons.append(
                f"UNSUPPORTED_MODEL:{model}"
            )

        item = {
            "case_id": row.get("case_id"),
            "faq_ids": source_ids,
            "model": model,
            "query": row.get("query"),
            "group_ids": sorted(required_groups),
            "review_status": row.get("review_status"),
            "label_generation": row.get("label_generation"),
        }

        if reasons:
            item["reasons"] = reasons
            faq_incompatible.append(item)
        else:
            faq_compatible.append(item)

    if not faq_compatible:
        warnings.append(
            "E01 Evidence Group과 직접 호환되는 FAQ-origin Gold v2 Case가 없습니다."
        )

    # Gold v2는 사람 승인 전 Draft이므로 공식 TEST로 사용하지 않는다.
    faq_review_counts = Counter(
        str(row.get("review_status") or "UNKNOWN")
        for row in faq_compatible
    )

    input_hashes = {
        str(path.relative_to(ROOT)): sha256_file(path)
        for path in required
    }

    status = (
        "E02_V2_PREFLIGHT_READY"
        if not errors
        else "E02_V2_PREFLIGHT_BLOCKED"
    )

    result = {
        "status": status,
        "experiment_id": "E02-v2",
        "git": {
            "branch": git_value("branch", "--show-current"),
            "head_sha": git_value("rev-parse", "HEAD"),
        },
        "manual_corpus": {
            "total_pages": len(all_manual_rows),
            "pages_by_model": {
                model: len(rows)
                for model, rows in manual_rows_by_model.items()
            },
            "structural_statistics": structural,
        },
        "e01_gold_lineage": {
            "child_count": len(e01_children),
            "evidence_group_count": len(e01_groups),
            "case_count": len(e01_cases),
            "child_source_span_restored_on_full_corpus": (
                f"{lineage_ok}/{EXPECTED_E01_CHILD_COUNT}"
            ),
            "failures": lineage_failures,
        },
        "retrieval_difficulty_gate": {
            "top_k": TOP_K,
            "minimum_candidates_per_model": MIN_CANDIDATES_PER_MODEL,
            "strategies": difficulty_gate,
        },
        "faq": {
            "raw_faq_count": len(faq_rows),
            "usage": "QUERY_SOURCE_ONLY_NOT_RETRIEVAL_CORPUS",
            "gold_v2_total_cases": len(gold_v2),
            "gold_v2_active_cases": len(active_gold),
            "faq_origin_active_cases": len(faq_origin_active),
            "faq_origin_e01_compatible_cases": len(faq_compatible),
            "faq_origin_incompatible_cases": len(faq_incompatible),
            "compatible_review_status_counts": dict(
                sorted(faq_review_counts.items())
            ),
            "compatible_cases": faq_compatible,
            "incompatible_cases": faq_incompatible,
            "publication_guardrail": (
                "Gold v2 FAQ-origin Case는 UNREVIEWED_DRAFT이면 "
                "공식 TEST 지표가 아니라 supplemental DRAFT_DIAGNOSTIC로만 사용"
            ),
        },
        "planned_v2_comparison": {
            "primary_query_set": "E01 50 cases",
            "supplemental_query_set": (
                "Gold v2 ACTIVE + EXISTING_FAQ + E01 group-compatible cases"
            ),
            "retrieval_corpus": "3 official manuals, 144 processed pages only",
            "strategies": [
                "fixed512",
                "section_aware_512",
                "parent_child_256",
            ],
            "embedding_model": MODEL_NAME,
            "embedding_revision": MODEL_REVISION,
            "top_k": TOP_K,
            "exact_sales_code_pre_filter": True,
            "cross_model_fallback": False,
        },
        "input_hashes": input_hashes,
        "warnings": warnings,
        "errors": errors,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    compact = {
        "status": status,
        "git_sha": result["git"]["head_sha"],
        "manual_pages": result["manual_corpus"]["pages_by_model"],
        "total_manual_pages": len(all_manual_rows),
        "e01_child_span_restored": (
            f"{lineage_ok}/{EXPECTED_E01_CHILD_COUNT}"
        ),
        "candidate_counts_after_product_filter": {
            strategy: info["candidate_counts_by_model"]
            for strategy, info in difficulty_gate.items()
        },
        "difficulty_gate": {
            strategy: info["status"]
            for strategy, info in difficulty_gate.items()
        },
        "faq_count": len(faq_rows),
        "faq_origin_active_cases": len(faq_origin_active),
        "faq_origin_e01_compatible_cases": len(faq_compatible),
        "faq_compatible_review_status": dict(
            sorted(faq_review_counts.items())
        ),
        "output": str(
            OUT_PATH.relative_to(ROOT)
        ).replace("\\", "/"),
        "warnings": warnings,
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
