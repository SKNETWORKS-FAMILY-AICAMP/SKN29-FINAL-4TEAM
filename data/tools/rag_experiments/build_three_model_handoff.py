"""검증된 3개 정수기 매뉴얼의 제한 RAG 인계 패키지를 결정적으로 생성한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
GENERATED_AT = "2026-08-18T00:00:00+09:00"
SUPPORTED_PRODUCTS = "data/config/rag/supported_products.json"
JAC_PARENTS = "data/processed/structured/rag/experimental/rag_parent_pages_v2.jsonl"
JAC_CHILDREN = "data/processed/structured/rag/experimental/rag_child_chunks_v2.jsonl"
JAC_EVIDENCE = "data/processed/structured/evidence/jac104_evidence_registry.jsonl"
IAC425_PAGES = "data/processed/documents/manuals/expansion/manual_pages_iac425.jsonl"
IAC606_PAGES = "data/processed/documents/manuals/expansion/manual_pages_iac606.jsonl"

DEFAULT_PARENT_OUTPUT = (
    "data/processed/structured/rag/expansion/rag_parent_pages_3model_v1.jsonl"
)
DEFAULT_CHILD_OUTPUT = (
    "data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl"
)
DEFAULT_EVIDENCE_OUTPUT = (
    "data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl"
)
DEFAULT_EVALUATION_OUTPUT = "data/config/rag/three_model_evaluation_cases.json"
DEFAULT_MANIFEST_OUTPUT = "data/processed/metadata/rag_three_model_handoff_manifest.json"


ICE_SEGMENTS = (
    ("COLD-LOCK", "냉수 선택이 안 됨", 0, 4, 7),
    ("COLD-TEMPERATURE-NORMAL", "냉수가 차갑지 않음 (제품 고장이 아닌 경우)", 0, 8, 17),
    ("COLD-TEMPERATURE-FAULT", "냉수가 차갑지 않음 (제품 고장인 경우)", 0, 18, 23),
    ("NOISE-NORMAL", "소음 발생", 0, 24, 37),
    ("NOISE-VENTILATION", "소음이 큼", 0, 38, None),
    ("ICE-MAKING-NOISE", "제빙수 공급 및 순환 소리", 1, 2, 9),
    ("DEFROST-NOISE", "탈빙 소음", 1, 10, 14),
    ("NO-WATER", "물이 나오지 않음", 1, 15, 28),
    ("LOW-FLOW", "출수량이 적을 경우", 1, 29, 41),
    ("NO-ICE", "얼음이 나오지 않음", 2, 2, 17),
    ("LEAK", "제품 누수 발생", 2, 18, 22),
    ("TASTE-ODOR", "불쾌한 맛과 냄새 발생", 2, 23, 34),
    ("PARTICLES", "정수된 물에 미세한 입자 발생", 2, 35, 40),
    ("ICE-QUALITY", "얼음이 깨지거나 단단하지 않음", 3, 2, 5),
    ("HOT-STEAM", "온수 사용 중 스팀 분사", 3, 6, 12),
    ("HOT-WATER-INTERRUPTION", "온수 사용 중 물 끊김", 3, 13, 19),
    ("NO-HOT-WATER", "온수가 나오지 않음", 3, 20, 28),
    ("HOT-WATER-STOPPED", "온수 출수 중 중단", 3, 29, 39),
)

RISK_LEVELS = {
    "LEAK": "danger",
    "HOT-WATER-STOPPED": "danger",
    "HOT-STEAM": "caution",
    "COLD-TEMPERATURE-FAULT": "caution",
    "NO-WATER": "caution",
    "NO-ICE": "caution",
    "NO-HOT-WATER": "caution",
}

JAC_SPAN_OVERRIDES = {
    "CHILD-WPUJAC104DWH-P038-LEAK-001": (2, 4),
    "CHILD-WPUJAC104DWH-P038-HOT-INTERRUPTION-001": (36, 38),
    "CHILD-WPUJAC104DWH-P039-HOT-MODULE-CHECK-001": (19, 25),
    "CHILD-WPUJAC104DWH-P039-HOT-CHECK-PROCESS-001": (26, 30),
}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _read_json(path: str) -> Any:
    return json.loads((REPOSITORY_ROOT / path).read_text(encoding="utf-8"))


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (REPOSITORY_ROOT / path).read_text(encoding="utf-8").splitlines()
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
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )
    path.write_text(payload, encoding="utf-8", newline="\n")


def _product_map() -> dict[str, dict[str, Any]]:
    registry = _read_json(SUPPORTED_PRODUCTS)
    return {row["exact_sales_code"]: row for row in registry["products"]}


def _source_span(text: str, line_start: int, line_end: int, row_label: str) -> dict[str, Any]:
    lines = text.splitlines()
    if line_start < 1 or line_end > len(lines) or line_start > line_end:
        raise ValueError(f"invalid source span {row_label}: {line_start}-{line_end}/{len(lines)}")
    selected = lines[line_start - 1 : line_end]
    raw_span = "\n".join(selected)
    return {
        "type": "TABLE_ROW_OR_PARAGRAPH",
        "row_label": row_label,
        "line_start": line_start,
        "line_end": line_end,
        "start_anchor": selected[0],
        "end_anchor": selected[-1],
        "raw_span_sha256": _sha256_text(raw_span),
    }


def _clean_child_text(text: str, line_start: int, line_end: int) -> str:
    raw = " ".join(text.splitlines()[line_start - 1 : line_end])
    return " ".join(raw.replace("●", " ").split())


def _actions(child_text: str) -> tuple[list[str], list[str], bool]:
    sentences = [piece.strip() for piece in child_text.split(".") if piece.strip()]
    consultation = [sentence + "." for sentence in sentences if "고객상담센터" in sentence]
    safe = [
        sentence + "."
        for sentence in sentences
        if "고객상담센터" not in sentence
        and any(token in sentence for token in ("확인", "해제", "청소", "열어", "잠그", "뽑", "기다", "교체"))
    ]
    if not safe:
        safe = [child_text]
    return safe, consultation, bool(consultation)


def _validated_span(parent_text: str, span: dict[str, Any]) -> dict[str, Any]:
    lines = parent_text.splitlines()
    selected = lines[span["line_start"] - 1 : span["line_end"]]
    if not selected or selected[0] != span["start_anchor"] or selected[-1] != span["end_anchor"]:
        raise ValueError(f"JAC104 anchor mismatch: {span['row_label']}")
    return _source_span(
        parent_text,
        span["line_start"],
        span["line_end"],
        span["row_label"],
    )


def _build_jac(
    products: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    product = products["WPUJAC104DWH"]
    registry = {
        row["evidence_id"]: row
        for row in _read_jsonl(JAC_EVIDENCE)
        if row.get("evidence_class") == "MANUAL"
    }
    parents: list[dict[str, Any]] = []
    parent_map: dict[str, dict[str, Any]] = {}
    for source in _read_jsonl(JAC_PARENTS):
        row = {
            **source,
            "retrieval_role": "CONTEXT_ONLY",
            "model_family": product["model_family"],
            "product_generation": product["product_generation"],
            "allowed_use": "RAG_HANDOFF_ONLY",
            "verification_status": "TEXT_AND_VISUAL_VERIFIED",
            "generated_at": GENERATED_AT,
        }
        parents.append(row)
        parent_map[row["parent_id"]] = row

    children: list[dict[str, Any]] = []
    for source in _read_jsonl(JAC_CHILDREN):
        evidence = registry[source["evidence_group_id"]]
        parent = parent_map[source["parent_id"]]
        if source["child_id"] in JAC_SPAN_OVERRIDES:
            line_start, line_end = JAC_SPAN_OVERRIDES[source["child_id"]]
            validated_span = _source_span(
                parent["parent_text"],
                line_start,
                line_end,
                source["source_span"]["row_label"],
            )
            validated_span["correction_id"] = "JAC104-EXPANSION-SPAN-ANCHOR-REALIGN-01"
        else:
            validated_span = _validated_span(parent["parent_text"], source["source_span"])
        row = {
            **source,
            "source_span": validated_span,
            "retrieval_role": "SEARCH_CANDIDATE",
            "exact_sales_code": product["exact_sales_code"],
            "product_model": product["manual_model"],
            "model_family": product["model_family"],
            "product_generation": product["product_generation"],
            "version": product["revision"],
            "risk_level": evidence["risk_level"],
            "safe_actions": evidence["safe_actions"],
            "requires_consultation": evidence["requires_consultation"],
            "consultation_conditions": evidence["consultation_conditions"],
            "allowed_use": "RAG_HANDOFF_ONLY",
            "verification_status": "TEXT_AND_VISUAL_VERIFIED",
            "generated_at": GENERATED_AT,
        }
        children.append(row)

    groups: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for child in children:
        grouped[child["evidence_group_id"]].append(child)
    for group_id in sorted(grouped):
        source = registry[group_id]
        variants = grouped[group_id]
        groups.append({
            "evidence_group_id": group_id,
            "record_type": "evidence_group",
            "exact_sales_code": product["exact_sales_code"],
            "product_model": product["manual_model"],
            "document_id": product["document_id"],
            "topic_code": source["topic_code"],
            "row_labels": sorted({row["source_span"]["row_label"] for row in variants}),
            "page_refs": sorted({page for row in variants for page in row["page_refs"]}),
            "source_variant_ids": [row["source_variant_id"] for row in variants],
            "child_ids": [row["child_id"] for row in variants],
            "risk_level": source["risk_level"],
            "safe_actions": source["safe_actions"],
            "requires_consultation": source["requires_consultation"],
            "consultation_conditions": source["consultation_conditions"],
            "allowed_use": "RAG_HANDOFF_ONLY",
            "verification_status": "TEXT_AND_VISUAL_VERIFIED",
            "generated_at": GENERATED_AT,
        })
    return parents, children, groups


def _build_ice_model(
    product: dict[str, Any], page_source: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    page_rows = {row["page"]: row for row in _read_jsonl(page_source)}
    selected_pages = product["rag_parent_pages"]
    selected = [page_rows[page] for page in selected_pages]
    parents: list[dict[str, Any]] = []
    parent_map: dict[int, dict[str, Any]] = {}
    for source in selected:
        page = source["page"]
        row = {
            "parent_id": f"PARENT-{product['exact_sales_code']}-P{page:03d}",
            "record_type": "parent",
            "retrieval_role": "CONTEXT_ONLY",
            "exact_sales_code": product["exact_sales_code"],
            "product_model": product["manual_model"],
            "model_family": product["model_family"],
            "product_generation": product["product_generation"],
            "document_id": product["document_id"],
            "version": product["revision"],
            "page_id": source["page_id"],
            "page_refs": [page],
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
        parents.append(row)
        parent_map[page] = row

    troubleshooting_pages = selected_pages[1:]
    children: list[dict[str, Any]] = []

    def add_child(topic: str, label: str, page: int, start: int, end: int, variant: str) -> None:
        parent = parent_map[page]
        text = parent["parent_text"]
        span = _source_span(text, start, end, label)
        child_text = _clean_child_text(text, start, end)
        safe, consultation, requires_consultation = _actions(child_text)
        children.append({
            "child_id": f"CHILD-{product['exact_sales_code']}-P{page:03d}-{topic}-001",
            "record_type": "child",
            "retrieval_role": "SEARCH_CANDIDATE",
            "child_text": child_text,
            "child_text_sha256": _sha256_text(child_text),
            "exact_sales_code": product["exact_sales_code"],
            "product_model": product["manual_model"],
            "model_family": product["model_family"],
            "product_generation": product["product_generation"],
            "document_id": product["document_id"],
            "version": product["revision"],
            "parent_id": parent["parent_id"],
            "parent_text_sha256": parent["parent_text_sha256"],
            "page_id": parent["page_id"],
            "page_refs": [page],
            "section_title": parent["section_title"],
            "evidence_group_id": f"EVD-{product['exact_sales_code']}-{topic}-001",
            "source_variant_id": variant,
            "source_span": span,
            "source_file_sha256": parent["source_file_sha256"],
            "source_page_text_sha256": parent["source_page_text_sha256"],
            "risk_level": RISK_LEVELS.get(topic, "general"),
            "safe_actions": safe,
            "requires_consultation": requires_consultation,
            "consultation_conditions": consultation,
            "allowed_use": "RAG_HANDOFF_ONLY",
            "verification_status": "TEXT_AND_VISUAL_VERIFIED",
            "generated_at": GENERATED_AT,
        })

    add_child("LEAK", "누수 안전조치", selected_pages[0], 2, 4, "SAFETY-P005")
    for topic, label, page_offset, start, configured_end in ICE_SEGMENTS:
        page = troubleshooting_pages[page_offset]
        end = configured_end
        if topic == "NOISE-VENTILATION":
            end = 43 if product["exact_sales_code"] == "WPUIAC425SNW" else 44
        add_child(topic, label, page, start, int(end), f"TROUBLESHOOTING-P{page:03d}")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for child in children:
        grouped[child["evidence_group_id"]].append(child)
    groups: list[dict[str, Any]] = []
    for group_id in sorted(grouped):
        variants = grouped[group_id]
        groups.append({
            "evidence_group_id": group_id,
            "record_type": "evidence_group",
            "exact_sales_code": product["exact_sales_code"],
            "product_model": product["manual_model"],
            "document_id": product["document_id"],
            "topic_code": group_id.split(f"EVD-{product['exact_sales_code']}-", 1)[1].rsplit("-001", 1)[0].lower().replace("-", "_"),
            "row_labels": sorted({row["source_span"]["row_label"] for row in variants}),
            "page_refs": sorted({page for row in variants for page in row["page_refs"]}),
            "source_variant_ids": [row["source_variant_id"] for row in variants],
            "child_ids": [row["child_id"] for row in variants],
            "risk_level": max(
                (row["risk_level"] for row in variants),
                key={"general": 0, "caution": 1, "danger": 2}.get,
            ),
            "safe_actions": list(dict.fromkeys(action for row in variants for action in row["safe_actions"])),
            "requires_consultation": any(row["requires_consultation"] for row in variants),
            "consultation_conditions": list(
                dict.fromkeys(condition for row in variants for condition in row["consultation_conditions"])
            ),
            "allowed_use": "RAG_HANDOFF_ONLY",
            "verification_status": "TEXT_AND_VISUAL_VERIFIED",
            "generated_at": GENERATED_AT,
        })
    return parents, children, groups


def _build_evaluations(
    groups: list[dict[str, Any]], products: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    product_codes = sorted(products)
    positive_cases = []
    for index, group in enumerate(groups, start=1):
        code = group["exact_sales_code"]
        label = group["row_labels"][0]
        positive_cases.append({
            "case_id": f"RAG3-POS-{index:03d}",
            "case_type": "POSITIVE",
            "query": f"{group['product_model']}에서 {label} 증상이 있을 때 확인할 내용을 알려주세요.",
            "exact_sales_code": code,
            "expected_evidence_group_ids": [group["evidence_group_id"]],
            "forbidden_model_codes": [candidate for candidate in product_codes if candidate != code],
            "expected_no_evidence": False,
            "data_status": "DATA_READY_AI_NOT_RUN",
            "human_review_status": "HUMAN_REVIEW_PENDING",
        })
    negative_specs = [
        ("WPUJAC104DWH", "WPU-JAC104D에서 얼음이 만들어지지 않을 때 조치 방법은?", "UNSUPPORTED_FEATURE_FOR_MODEL"),
        ("WPUIAC425SNW", "WPU-IAC425에서 출수/출빙 버튼을 눌러 온수를 다시 받는 방법은?", "MODEL_CONTROL_MISMATCH"),
        ("WPUIAC606SNW", "WPU-IAC606에서 [물] 버튼을 눌러 온수를 다시 받는 방법은?", "MODEL_CONTROL_MISMATCH"),
        ("WPUJCC104D", "WPU-JCC104D의 누수 대처 방법은?", "INACTIVE_BUNDLED_MANUAL_ALIAS"),
        ("WPUIAC506SNW", "WPU-IAC506의 필터 교체 방법은?", "BLOCKED_MODEL"),
        ("UNVERIFIED_FAQ", "모델을 확인할 수 없는 정수기 FAQ 답변을 알려줘.", "MODEL_UNVERIFIED_FAQ"),
        ("WPUIAC999ZZZ", "WPUIAC999ZZZ 모델의 온수 잠금을 해제하는 방법은?", "UNREGISTERED_EXACT_SALES_CODE"),
    ]
    negative_cases = []
    for index, (code, query, reason) in enumerate(negative_specs, start=1):
        negative_cases.append({
            "case_id": f"RAG3-NEG-{index:03d}",
            "case_type": "NEGATIVE",
            "query": query,
            "exact_sales_code": code,
            "expected_evidence_group_ids": [],
            "forbidden_model_codes": product_codes,
            "expected_no_evidence": True,
            "negative_reason": reason,
            "data_status": "DATA_READY_AI_NOT_RUN",
            "human_review_status": "HUMAN_REVIEW_PENDING",
        })
    return {
        "schema_version": "1.0.0",
        "dataset_id": "RAG-3MODEL-EVALUATION-DRAFT-V1",
        "status": "DATA_READY_AI_NOT_RUN",
        "human_review_status": "HUMAN_REVIEW_PENDING",
        "retrieval_acceptance": {
            "positive": "질문의 정확 판매코드와 일치하는 검증된 expected Evidence Group의 근거 중 1개 이상이 Top-5 안에 포함",
            "negative": "no-evidence",
            "cross_model_hits": 0,
            "direct_parent_hits": 0,
            "verified_evidence_only": True,
        },
        "generated_at": GENERATED_AT,
        "cases": positive_cases + negative_cases,
    }


def build(
    parent_output: Path,
    child_output: Path,
    evidence_output: Path,
    evaluation_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    products = _product_map()
    parents, children, groups = _build_jac(products)
    for code, page_source in (
        ("WPUIAC425SNW", IAC425_PAGES),
        ("WPUIAC606SNW", IAC606_PAGES),
    ):
        model_parents, model_children, model_groups = _build_ice_model(products[code], page_source)
        parents.extend(model_parents)
        children.extend(model_children)
        groups.extend(model_groups)

    parents.sort(key=lambda row: row["parent_id"])
    children.sort(key=lambda row: row["child_id"])
    groups.sort(key=lambda row: row["evidence_group_id"])
    evaluations = _build_evaluations(groups, products)
    if (len(parents), len(children), len(groups), len(evaluations["cases"])) != (15, 53, 43, 50):
        raise ValueError("three-model handoff count gate failed")

    _write_jsonl(parent_output, parents)
    _write_jsonl(child_output, children)
    _write_jsonl(evidence_output, groups)
    _write_json(evaluation_output, evaluations)
    outputs = [
        (parent_output, DEFAULT_PARENT_OUTPUT),
        (child_output, DEFAULT_CHILD_OUTPUT),
        (evidence_output, DEFAULT_EVIDENCE_OUTPUT),
        (evaluation_output, DEFAULT_EVALUATION_OUTPUT),
    ]
    manifest = {
        "manifest_version": "1.0.0",
        "dataset_version": "1.0.0",
        "status": "DATA_READY_AI_NOT_RUN",
        "role": "INGEST_CANDIDATE",
        "runtime_status": "CONTRACT_BLOCKED_NOT_INDEXED",
        "generated_at": GENERATED_AT,
        "counts": {
            "supported_products": 3,
            "reference_pages": 144,
            "parent_pages": len(parents),
            "child_chunks": len(children),
            "evidence_groups": len(groups),
            "evaluation_cases": len(evaluations["cases"]),
            "positive_cases": 43,
            "negative_cases": 7,
        },
        "outputs": [
            {
                "path": canonical_path,
                "sha256": _sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path, canonical_path in outputs
        ],
    }
    _write_json(manifest_output, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="3모델 제한 RAG 인계 패키지 생성")
    parser.add_argument("--parent-output", default=DEFAULT_PARENT_OUTPUT)
    parser.add_argument("--child-output", default=DEFAULT_CHILD_OUTPUT)
    parser.add_argument("--evidence-output", default=DEFAULT_EVIDENCE_OUTPUT)
    parser.add_argument("--evaluation-output", default=DEFAULT_EVALUATION_OUTPUT)
    parser.add_argument("--manifest-output", default=DEFAULT_MANIFEST_OUTPUT)
    args = parser.parse_args()
    manifest = build(
        REPOSITORY_ROOT / args.parent_output,
        REPOSITORY_ROOT / args.child_output,
        REPOSITORY_ROOT / args.evidence_output,
        REPOSITORY_ROOT / args.evaluation_output,
        REPOSITORY_ROOT / args.manifest_output,
    )
    print(json.dumps({"status": manifest["status"], **manifest["counts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
