"""Full Corpus v2 데이터 인계본과 Gold 검수 후보를 결정적으로 생성한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
GENERATED_AT = "2026-08-23T00:00:00+09:00"
CONFIG_PATH = "data/config/rag/full_corpus_v2_segments.json"
DEFAULT_CORPUS_OUTPUT = (
    "data/processed/structured/rag/experimental/full_corpus_chunks_v2.jsonl"
)
DEFAULT_COVERAGE_OUTPUT = (
    "data/processed/structured/rag/experimental/full_corpus_v2_coverage.json"
)
DEFAULT_REVIEW_OUTPUT = (
    "data/processed/validation/rag_experiments/gold_v1_primary_review_packet.json"
)
DEFAULT_CANDIDATE_OUTPUT = "data/config/rag/iac425_gold_candidates.json"
DEFAULT_MANIFEST_OUTPUT = (
    "data/processed/metadata/full_corpus_v2_handoff_manifest.json"
)

CORPUS_SCHEMA = "data/schemas/processed/fullCorpusV2Chunk.schema.json"
COVERAGE_SCHEMA = "data/schemas/processed/fullCorpusV2Coverage.schema.json"
REVIEW_SCHEMA = "data/schemas/config/goldPrimaryReviewPacket.schema.json"
CANDIDATE_SCHEMA = "data/schemas/config/iac425GoldCandidates.schema.json"

RISK_ORDER = {"general": 0, "caution": 1, "danger": 2}
GUIDANCE_ORDER = {
    "NORMAL": 0,
    "PENDING_CONSULTATION": 1,
    "PARTIAL_STOP": 2,
    "TOTAL_STOP": 3,
}

SEMANTIC_CHANGE_PROPOSALS = {
    "RAGV2-GOLD-0045": {
        "field": "expected_evidence/evidence_match_policy",
        "reason": (
            "현재 P004는 제품 내부 유입 방지와 위험만 설명한다. 이미 물이 들어간 "
            "상황의 즉시 중단 조치는 P005가 직접 뒷받침한다."
        ),
        "proposed_value": (
            "P004와 P005를 ALL로 요구하거나, 조치 중심 Case라면 P005 ANY로 교체"
        ),
    },
    "RAGV2-GOLD-0049": {
        "field": "expected_evidence/evidence_match_policy",
        "reason": (
            "현재 P004는 가연성 스프레이 사용 금지만 설명한다. 사용 후 이상한 냄새가 "
            "난 상황의 즉시 중단 조치는 P005가 직접 뒷받침한다."
        ),
        "proposed_value": "P004와 P005를 expected_evidence에 두고 ALL 적용",
    },
}


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


def _base_chunk(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": row["chunk_id"],
        "chunk_index": 0,
        "chunking_profile": "row_child_full_corpus_v2",
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


def _child_chunk(
    child: dict[str, Any], source_page: dict[str, Any]
) -> dict[str, Any]:
    return {
        "chunk_id": child["child_id"],
        "chunk_index": 0,
        "chunking_profile": "row_child_full_corpus_v2",
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
        "chunking_profile": "row_child_full_corpus_v2",
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


def _build_corpus_and_coverage(
    config: dict[str, Any], inputs: dict[str, Path]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    baseline = _read_jsonl(inputs["baseline_corpus"])
    manual_pages = {
        row["page"]: row
        for row in _read_jsonl(inputs["manual_pages"])
        if row["page"] in {5, 7, 37, 38, 39}
    }
    children = {
        row["child_id"]: row
        for row in _read_jsonl(inputs["children"])
        if row["exact_sales_code"] == config["replacement"]["exact_sales_code"]
    }
    replacement_pages = {int(page) for page in config["replacement"]["pages"]}
    baseline_by_page = {
        row["page_refs"][0]: row
        for row in baseline
        if row["document_id"] == config["replacement"]["document_id"]
    }

    replacements: dict[int, list[tuple[int, dict[str, Any]]]] = {}
    coverage_pages: list[dict[str, Any]] = []
    for page in sorted(replacement_pages):
        source_page = baseline_by_page[page]
        lines = manual_pages[page]["text"].split("\n")
        assignments: list[dict[str, Any]] = []
        page_chunks: list[tuple[int, dict[str, Any]]] = []
        occupied: set[int] = set()
        for segment in config["replacement"]["pages"][str(page)]:
            start = segment["line_start"]
            end = segment["line_end"]
            if start < 1 or end > len(lines) or start > end:
                raise ValueError(f"잘못된 행 범위: page={page} {start}-{end}")
            for line_number in range(start, end + 1):
                if line_number in occupied:
                    raise ValueError(f"행 중복 분류: page={page} line={line_number}")
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
                child = children.get(segment["record_id"])
                if child is None:
                    raise ValueError(f"Child 없음: {segment['record_id']}")
                span = child["source_span"]
                if (span["line_start"], span["line_end"]) != (start, end):
                    raise ValueError(f"Child 행 범위 불일치: {segment['record_id']}")
                page_chunks.append((start, _child_chunk(child, source_page)))
            elif segment["classification"] == "PRESERVATION":
                page_chunks.append(
                    (
                        start,
                        _preservation_chunk(
                            segment["record_id"], start, end, lines, source_page
                        ),
                    )
                )
        if occupied != set(range(1, len(lines) + 1)):
            missing = sorted(set(range(1, len(lines) + 1)) - occupied)
            raise ValueError(f"행 미분류: page={page} lines={missing}")
        replacements[page] = sorted(page_chunks, key=lambda item: (item[0], item[1]["chunk_id"]))
        coverage_pages.append(
            {
                "page": page,
                "total_lines": len(lines),
                "assignments": sorted(assignments, key=lambda row: row["line_number"]),
            }
        )

    corpus: list[dict[str, Any]] = []
    for row in baseline:
        page = row["page_refs"][0]
        if (
            row["document_id"] == config["replacement"]["document_id"]
            and page in replacement_pages
        ):
            corpus.extend(chunk for _, chunk in replacements[page])
        else:
            corpus.append(_base_chunk(row))
    for index, row in enumerate(corpus, start=1):
        row["chunk_index"] = index

    coverage = {
        "schema_version": "1.0.0",
        "status": "FULL_CORPUS_V2_DATA_HANDOFF_READY",
        "generated_at": GENERATED_AT,
        "pages": coverage_pages,
    }
    return corpus, coverage


def _check(check_id: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"check_id": check_id, "status": "PASS" if passed else "FAIL", "detail": detail}


def _highest(values: list[str], order: dict[str, int]) -> str | None:
    if not values:
        return None
    return max(values, key=lambda value: order[value])


def _build_gold_review(
    config: dict[str, Any], inputs: dict[str, Path]
) -> dict[str, Any]:
    gold = _read_jsonl(inputs["gold_dataset"])
    registry = {
        row["evidence_id"]: row
        for row in _read_jsonl(inputs["jac104_evidence_registry"])
    }
    manual_pages = {
        row["page_id"]: row for row in _read_jsonl(inputs["manual_pages"])
    }
    baseline = _read_jsonl(inputs["baseline_corpus"])
    sections = {
        (row["document_id"], row["page_refs"][0]): row["section_id"]
        for row in baseline
    }
    reviews: list[dict[str, Any]] = []
    for case in gold:
        checks: list[dict[str, Any]] = []
        suggestions: list[dict[str, Any]] = []
        source_review_context: list[dict[str, Any]] = []
        is_negative = case["expected_no_evidence"]
        coherence = (
            (is_negative and not case["expected_evidence"] and case["evidence_match_policy"] == "NONE")
            or (
                not is_negative
                and bool(case["expected_evidence"])
                and case["evidence_match_policy"] in {"ANY", "ALL"}
            )
        )
        checks.append(_check("EVIDENCE_POLICY_COHERENCE", coherence, case["evidence_match_policy"]))
        if not coherence:
            suggestions.append(
                {"field": "evidence_match_policy", "reason": "근거 유무와 정책 조합을 재검토해야 함"}
            )

        registry_rows: list[dict[str, Any]] = []
        page_evidence_seen = False
        lineage_ok = True
        for expected in case["expected_evidence"]:
            evidence_id = expected["evidence_unit_id"]
            if evidence_id in registry:
                evidence = registry[evidence_id]
                registry_rows.append(evidence)
                lineage_ok = lineage_ok and evidence["document_id"] == expected["document_id"]
                lineage_ok = lineage_ok and set(expected["page_refs"]).issubset(evidence["page_refs"])
                lineage_ok = lineage_ok and evidence["exact_sales_code"] == case["product_model_code"]
                source_review_context.append(
                    {
                        "evidence_unit_id": evidence_id,
                        "source_kind": "EVIDENCE_REGISTRY",
                        "document_id": expected["document_id"],
                        "page_refs": expected["page_refs"],
                        "section_id": expected["section_id"],
                        "verification_status": evidence["verification_status"],
                        "evidence_summary": evidence["evidence_summary"],
                        "source_locator": config["inputs"]["jac104_evidence_registry"]["path"],
                    }
                )
            elif evidence_id in manual_pages:
                page_evidence_seen = True
                page = manual_pages[evidence_id]
                lineage_ok = lineage_ok and page["document_id"] == expected["document_id"]
                lineage_ok = lineage_ok and page["page"] in expected["page_refs"]
                source_review_context.append(
                    {
                        "evidence_unit_id": evidence_id,
                        "source_kind": "MANUAL_PAGE",
                        "document_id": expected["document_id"],
                        "page_refs": expected["page_refs"],
                        "section_id": expected["section_id"],
                        "verification_status": page["verification_status"],
                        "evidence_summary": None,
                        "source_locator": config["inputs"]["manual_pages"]["path"],
                    }
                )
            else:
                lineage_ok = False
            section_values = {
                sections.get((expected["document_id"], page))
                for page in expected["page_refs"]
            }
            lineage_ok = lineage_ok and expected["section_id"] in section_values
        checks.append(_check("EVIDENCE_LINEAGE", lineage_ok, "registry/page/section cross-check"))
        if not lineage_ok:
            suggestions.append(
                {"field": "expected_evidence", "reason": "문서·페이지·Section·Evidence 계보 불일치"}
            )

        forbidden_ok = True
        if not is_negative:
            forbidden_ok = case["product_model_code"] not in case["forbidden_model_codes"]
            forbidden_ok = forbidden_ok and all(
                expected["document_id"] not in case["forbidden_document_ids"]
                for expected in case["expected_evidence"]
            )
        checks.append(_check("FORBIDDEN_SCOPE", forbidden_ok, "target scope is not forbidden for positive cases"))
        if not forbidden_ok:
            suggestions.append(
                {"field": "forbidden_model_codes", "reason": "양성 Case의 대상 제품 또는 문서가 금지 범위에 포함됨"}
            )

        label_ok = True
        if registry_rows and len(registry_rows) == len(case["expected_evidence"]):
            expected_risk = _highest(
                [row["risk_level"] for row in registry_rows], RISK_ORDER
            )
            expected_guidance = _highest(
                [row["use_guidance"] for row in registry_rows], GUIDANCE_ORDER
            )
            label_ok = (
                case["expected_risk_level"] == expected_risk
                and case["expected_guidance_policy"] == expected_guidance
            )
        checks.append(_check("RISK_AND_GUIDANCE", label_ok, "registry-derived when available"))
        if not label_ok:
            suggestions.append(
                {"field": "expected_risk_level/expected_guidance_policy", "reason": "Evidence Registry 파생값과 불일치"}
            )

        semantic_proposal = SEMANTIC_CHANGE_PROPOSALS.get(case["case_id"])
        if semantic_proposal is not None:
            suggestions.append(semantic_proposal)

        failures = [row for row in checks if row["status"] == "FAIL"]
        if failures or semantic_proposal is not None:
            assessment = "CHANGE_PROPOSED"
        elif is_negative or page_evidence_seen:
            assessment = "SOURCE_CHECK_REQUIRED"
        else:
            assessment = "SUPPORTED"

        if is_negative:
            review_priority = "HIGH"
            assistant_reason = (
                "정책과 금지 범위는 기계적으로 일치한다. 검색 범위 전체에 답이 없다는 "
                "판정은 사람이 질문 의미와 Corpus 범위를 확인해야 한다."
            )
        elif semantic_proposal is not None:
            review_priority = "HIGH"
            assistant_reason = "인용 Page가 질문 상황의 일부만 직접 뒷받침해 근거 변경을 제안한다."
        elif page_evidence_seen:
            review_priority = "HIGH"
            assistant_reason = (
                "Safety Page 계보는 일치하지만 입력은 TEXT_EXTRACTED 상태다. 원문 시각 확인이 필요하다."
            )
        elif case["query_variant_type"] == "COMPOUND":
            review_priority = "MEDIUM"
            assistant_reason = "복합 질문의 모든 Evidence Unit과 ALL 정책이 기계적으로 일치한다."
        else:
            review_priority = "NORMAL"
            assistant_reason = "검증된 Evidence Registry의 계보·위험도·안내 정책과 일치한다."

        required_human_checks = [
            "QUERY_AND_EVIDENCE_MEANING",
            "RISK_AND_GUIDANCE_APPROPRIATENESS",
            "FORBIDDEN_SCOPE_APPROPRIATENESS",
        ]
        if page_evidence_seen:
            required_human_checks.append("ORIGINAL_PAGE_VISUAL_CONFIRMATION")
        if is_negative:
            required_human_checks.append("NO_EVIDENCE_CORPUS_ABSENCE")
        if semantic_proposal is not None:
            required_human_checks.append("PROPOSED_CHANGE_DECISION")
        required_human_checks.append("RECORD_REVIEWER_ID_DECISION_AND_REVIEWED_AT")
        reviews.append(
            {
                "case_id": case["case_id"],
                "assistant_assessment": assessment,
                "assistant_reason": assistant_reason,
                "review_priority": review_priority,
                "human_signoff_status": "PENDING",
                "case_snapshot": {
                    "query": case["query"],
                    "query_variant_type": case["query_variant_type"],
                    "product_model_code": case["product_model_code"],
                    "expected_no_evidence": case["expected_no_evidence"],
                    "evidence_match_policy": case["evidence_match_policy"],
                    "expected_risk_level": case["expected_risk_level"],
                    "expected_guidance_policy": case["expected_guidance_policy"],
                    "forbidden_document_ids": case["forbidden_document_ids"],
                    "forbidden_model_codes": case["forbidden_model_codes"],
                    "source_case_ids": case["source_case_ids"],
                },
                "source_review_context": source_review_context,
                "checks": checks,
                "suggested_changes": suggestions,
                "required_human_checks": required_human_checks,
            }
        )

    counts = Counter(row["assistant_assessment"] for row in reviews)
    return {
        "schema_version": "1.0.0",
        "status": "GOLD_REVIEW_PACKET_READY_HUMAN_SIGNOFF_PENDING",
        "generated_at": GENERATED_AT,
        "source_dataset": {
            "path": config["inputs"]["gold_dataset"]["path"],
            "sha256": config["inputs"]["gold_dataset"]["sha256"],
            "record_count": len(gold),
        },
        "summary": {
            "assessment_counts": dict(sorted(counts.items())),
            "priority_counts": dict(
                sorted(Counter(row["review_priority"] for row in reviews).items())
            ),
            "human_signed_records": 0,
            "automatic_gold_promotion": False,
        },
        "reviews": reviews,
    }


def _proposed_guidance(group: dict[str, Any]) -> str:
    if group["risk_level"] == "danger":
        return "TOTAL_STOP"
    if group["risk_level"] == "caution":
        return "PARTIAL_STOP"
    if group["requires_consultation"]:
        return "PENDING_CONSULTATION"
    return "NORMAL"


def _build_iac425_candidates(
    config: dict[str, Any], inputs: dict[str, Path]
) -> dict[str, Any]:
    evaluation = _read_json(inputs["three_model_evaluation"])
    groups = {
        row["evidence_group_id"]: row
        for row in _read_jsonl(inputs["evidence_groups"])
        if row["exact_sales_code"] == "WPUIAC425SNW"
    }
    children = {
        row["child_id"]: row
        for row in _read_jsonl(inputs["children"])
        if row["exact_sales_code"] == "WPUIAC425SNW"
    }
    baseline = _read_jsonl(inputs["baseline_corpus"])
    sections = {
        (row["document_id"], row["page_refs"][0]): row["section_id"]
        for row in baseline
    }
    source_cases = [
        row
        for row in evaluation["cases"]
        if row["case_type"] == "POSITIVE"
        and row["exact_sales_code"] == "WPUIAC425SNW"
    ]
    candidates: list[dict[str, Any]] = []
    for index, source in enumerate(source_cases, start=1):
        variants: list[dict[str, Any]] = []
        risk_levels: list[str] = []
        guidance: list[str] = []
        for group_id in source["expected_evidence_group_ids"]:
            group = groups[group_id]
            risk_levels.append(group["risk_level"])
            guidance.append(_proposed_guidance(group))
            for child_id in group["child_ids"]:
                child = children[child_id]
                page = child["page_refs"][0]
                variants.append(
                    {
                        "document_id": child["document_id"],
                        "page_refs": child["page_refs"],
                        "section_id": sections[(child["document_id"], page)],
                        "evidence_unit_id": group_id,
                        "child_id": child_id,
                        "verification_status": child["verification_status"],
                    }
                )
        candidates.append(
            {
                "candidate_id": f"RAGV2-IAC425-CAND-{index:03d}",
                "source_case_id": source["case_id"],
                "query": source["query"],
                "query_variant_type": "DIRECT",
                "product_model_code": "WPUIAC425SNW",
                "expected_evidence_variants": sorted(
                    variants, key=lambda row: (row["evidence_unit_id"], row["page_refs"], row["child_id"])
                ),
                "forbidden_model_codes": source["forbidden_model_codes"],
                "expected_no_evidence": False,
                "proposed_risk_level": _highest(risk_levels, RISK_ORDER),
                "proposed_guidance_policy": _highest(guidance, GUIDANCE_ORDER),
                "proposed_split": "DEV",
                "human_review_status": "HUMAN_REVIEW_PENDING",
                "merge_status": "AI_OWNER_AND_SECOND_REVIEWER_APPROVAL_REQUIRED",
            }
        )
    return {
        "schema_version": "1.0.0",
        "status": "IAC425_GOLD_CANDIDATES_READY",
        "generated_at": GENERATED_AT,
        "source_gold_dataset_sha256": config["inputs"]["gold_dataset"]["sha256"],
        "source_evaluation_sha256": config["inputs"]["three_model_evaluation"]["sha256"],
        "candidates": candidates,
    }


def build(
    corpus_output: Path,
    coverage_output: Path,
    review_output: Path,
    candidate_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    config_path = REPOSITORY_ROOT / CONFIG_PATH
    config = _read_json(config_path)
    inputs = _resolved_inputs(config)
    corpus, coverage = _build_corpus_and_coverage(config, inputs)
    review = _build_gold_review(config, inputs)
    candidates = _build_iac425_candidates(config, inputs)

    _write_jsonl(corpus_output, corpus)
    _write_json(coverage_output, coverage)
    _write_json(review_output, review)
    _write_json(candidate_output, candidates)

    product_counts = Counter(row["exact_sales_code"] for row in corpus)
    record_type_counts = Counter(row["record_type"] for row in corpus)
    manifest = {
        "schema_version": "1.0.0",
        "status": "FULL_CORPUS_V2_DATA_HANDOFF_READY",
        "gold_review_status": "GOLD_REVIEW_PACKET_READY_HUMAN_SIGNOFF_PENDING",
        "iac425_candidate_status": "IAC425_GOLD_CANDIDATES_READY",
        "generated_at": GENERATED_AT,
        "source_commit": config["source_commit"],
        "inputs": {
            name: {"path": spec["path"], "sha256": spec["sha256"]}
            for name, spec in sorted(config["inputs"].items())
        },
        "schemas": {
            path: _sha256_file(REPOSITORY_ROOT / path)
            for path in (CORPUS_SCHEMA, COVERAGE_SCHEMA, REVIEW_SCHEMA, CANDIDATE_SCHEMA)
        },
        "outputs": {
            "corpus": {"path": _logical_output_path(corpus_output, DEFAULT_CORPUS_OUTPUT), "sha256": _sha256_file(corpus_output), "record_count": len(corpus)},
            "coverage": {"path": _logical_output_path(coverage_output, DEFAULT_COVERAGE_OUTPUT), "sha256": _sha256_file(coverage_output), "page_count": len(coverage["pages"])},
            "gold_review": {"path": _logical_output_path(review_output, DEFAULT_REVIEW_OUTPUT), "sha256": _sha256_file(review_output), "record_count": len(review["reviews"])},
            "iac425_candidates": {"path": _logical_output_path(candidate_output, DEFAULT_CANDIDATE_OUTPUT), "sha256": _sha256_file(candidate_output), "record_count": len(candidates["candidates"])},
        },
        "counts": {
            "search_candidates": len(corpus),
            "by_product": dict(sorted(product_counts.items())),
            "by_record_type": dict(sorted(record_type_counts.items())),
            "context_only_parents": 5,
        },
        "publication_limits": [
            "AI Runner와 운영 청킹 설정에 연결되지 않은 데이터 인계본이다.",
            "Gold 검수표는 사람 서명이나 2인 승인을 대체하지 않는다.",
            "IAC425 후보는 기존 Gold에 병합되지 않은 DEV 제안이다.",
            "Full B1 재실행 전 성능 수치 또는 운영 승격을 주장하지 않는다."
        ],
    }
    _write_json(manifest_output, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-output", default=DEFAULT_CORPUS_OUTPUT)
    parser.add_argument("--coverage-output", default=DEFAULT_COVERAGE_OUTPUT)
    parser.add_argument("--review-output", default=DEFAULT_REVIEW_OUTPUT)
    parser.add_argument("--candidate-output", default=DEFAULT_CANDIDATE_OUTPUT)
    parser.add_argument("--manifest-output", default=DEFAULT_MANIFEST_OUTPUT)
    args = parser.parse_args()
    manifest = build(
        REPOSITORY_ROOT / args.corpus_output,
        REPOSITORY_ROOT / args.coverage_output,
        REPOSITORY_ROOT / args.review_output,
        REPOSITORY_ROOT / args.candidate_output,
        REPOSITORY_ROOT / args.manifest_output,
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
