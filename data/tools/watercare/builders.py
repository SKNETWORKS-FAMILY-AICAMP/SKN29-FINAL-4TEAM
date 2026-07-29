"""Declarative processed, RAG, synthetic, and template builders."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

from .config import PipelineConfig
from .io import (
    json_bytes,
    jsonl_bytes,
    read_json,
    read_jsonl,
    replace_tokens,
    sha256_file,
    write_bytes,
)


Preview = dict[str, tuple[Path, bytes, int | None]]


def _ocr_rows(
    faq_rows: list[dict[str, Any]],
    ocr_config: dict[str, Any],
    generated_at: str,
) -> list[dict[str, Any]]:
    by_ordinal = {row["ordinal"]: row for row in faq_rows}
    rows: list[dict[str, Any]] = []
    for definition in ocr_config["records"]:
        source = by_ordinal[definition["ordinal"]]
        if len(source["image_urls"]) != len(definition["hashes"]):
            raise ValueError(f"FAQ ordinal {source['ordinal']}: image/hash mismatch")
        rows.append(
            {
                "ocr_record_id": f"OCR-{source['faq_id']}",
                "faq_id": source["faq_id"],
                "snapshot_id": source["snapshot_id"],
                "source_type": source["source_type"],
                "provider": source["provider"],
                "title": source["title"],
                "ocr_text": definition["text"],
                "image_urls": source["image_urls"],
                "image_sha256s": definition["hashes"],
                "image_count": len(source["image_urls"]),
                "extraction_method": "vision_assisted_transcription",
                "transcription_status": "USER_VERIFIED",
                "model_applicability": "MODEL_UNVERIFIED",
                "allowed_use": "EXCLUDED_FROM_RAG",
                "source_url": source["source_url"],
                "source_file_sha256": source["source_file_sha256"],
                "verified_at": ocr_config["verified_at"],
                "generated_at": generated_at,
            }
        )
    return rows


def _asset_rows(
    ocr_rows: list[dict[str, Any]], generated_at: str
) -> list[dict[str, Any]]:
    occurrences: dict[str, list[dict[str, Any]]] = {}
    for row in ocr_rows:
        for index, (url, digest) in enumerate(
            zip(row["image_urls"], row["image_sha256s"], strict=True), 1
        ):
            occurrences.setdefault(digest, []).append(
                {"faq_id": row["faq_id"], "image_index": index, "image_url": url}
            )
    rows: list[dict[str, Any]] = []
    for digest in sorted(occurrences):
        uses = sorted(
            occurrences[digest], key=lambda item: (item["faq_id"], item["image_index"])
        )
        rows.append(
            {
                "asset_id": f"ASSET-OFFICIAL-FAQ-{digest[:12]}",
                "source_type": "official_faq_image",
                "provider": "SK매직",
                "sha256": digest,
                "media_type": "image/jpeg",
                "asset_role": (
                    "SHARED_GUIDE_IMAGE" if len(uses) > 1 else "FAQ_GUIDE_IMAGE"
                ),
                "verification_status": "USER_VERIFIED_OFFICIAL_ASSET",
                "occurrence_count": len(uses),
                "occurrences": uses,
                "generated_at": generated_at,
            }
        )
    ids = {row["sha256"]: row["asset_id"] for row in rows}
    for row in ocr_rows:
        row["asset_ids"] = [ids[digest] for digest in row["image_sha256s"]]
    return rows


def _enrich_faq(
    faq_rows: list[dict[str, Any]],
    ocr_rows: list[dict[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    ocr_by_id = {row["faq_id"]: row for row in ocr_rows}
    enriched: list[dict[str, Any]] = []
    for source in faq_rows:
        row = dict(source)
        ocr = ocr_by_id.get(row["faq_id"])
        if ocr:
            row.update(
                answer_text=ocr["ocr_text"],
                answer_text_sha256=hashlib.sha256(
                    ocr["ocr_text"].encode("utf-8")
                ).hexdigest().upper(),
                content_status="OCR_TEXT_AND_IMAGE",
                text_source="ocr_verified",
                text_status="OCR_VERIFIED",
                retrieval_eligible=True,
                retrieval_scope="CONDITIONAL_REFERENCE_ONLY",
                exclusion_reason=None,
                mvp_exclusion_reason="MODEL_UNVERIFIED_FOR_MVP",
                ocr_record_id=ocr["ocr_record_id"],
                asset_ids=ocr["asset_ids"],
            )
        elif row["ordinal"] in {7, 9, 10}:
            row.update(
                answer_text="",
                answer_text_sha256=hashlib.sha256(b"").hexdigest().upper(),
                content_status="IMAGE_ONLY",
                text_source="image_only",
                text_status="NOT_TRANSCRIBED",
                retrieval_eligible=False,
                retrieval_scope="EXCLUDED",
                exclusion_reason="OUT_OF_MVP_SCOPE",
                mvp_exclusion_reason="OUT_OF_MVP_SCOPE",
                ocr_record_id=None,
                asset_ids=[],
            )
        else:
            row.update(
                text_source="publisher_text",
                text_status="PUBLISHER_TEXT",
                retrieval_eligible=True,
                retrieval_scope="CONDITIONAL_REFERENCE_ONLY",
                exclusion_reason=None,
                mvp_exclusion_reason="MODEL_UNVERIFIED_FOR_MVP",
                ocr_record_id=None,
                asset_ids=[],
            )
        row["mvp_rag_eligible"] = False
        row["generated_at"] = generated_at
        enriched.append(row)
    return enriched


def build_processed(
    config: PipelineConfig,
    *,
    manual: Path | None = None,
    faq: Path | None = None,
) -> dict[str, Any]:
    manifest = read_json(config.path("dataset_manifest"))
    sources = {"manual": manual, "faq_snapshot": faq}
    for key, source in sources.items():
        if source is None:
            continue
        source = source.resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        temp_root = (config.data_root / ".temp").resolve()
        if source == temp_root or temp_root in source.parents:
            raise ValueError("data/.temp/ must not be used as a source")
        if sha256_file(source) != manifest["source_hashes"][key]:
            raise ValueError(f"{key} source hash does not match verified lineage")
    counts = {
        "manual_pages": len(read_jsonl(config.path("manual_input"))),
        "faq_normalized": len(read_jsonl(config.path("faq_input"))),
        "faq_candidates": len(read_jsonl(config.path("faq_candidates"))),
    }
    expected = config.values["expected_counts"]
    if counts["manual_pages"] != expected["manual_pages"]:
        raise ValueError("manual page count mismatch")
    if counts["faq_normalized"] != expected["faq_normalized"]:
        raise ValueError("FAQ count mismatch")
    return {
        "status": "PASS",
        "mode": "verified_canonical_due_to_raw_non_retention",
        "source_hashes_verified": sum(path is not None for path in sources.values()),
        **counts,
    }


def build_rag_preview(config: PipelineConfig) -> Preview:
    faq_rows = read_jsonl(config.path("faq_input"))
    ocr_rows = _ocr_rows(faq_rows, config.config("ocr"), config.generated_at)
    assets = _asset_rows(ocr_rows, config.generated_at)
    enriched = _enrich_faq(faq_rows, ocr_rows, config.generated_at)
    rag = replace_tokens(config.config("rag"), {"generated_at": config.generated_at})
    return {
        "faq_normalized": (config.path("faq_input"), jsonl_bytes(enriched), len(enriched)),
        "faq_ocr_verified": (
            config.path("ocr_output"),
            jsonl_bytes(ocr_rows),
            len(ocr_rows),
        ),
        "official_faq_assets": (
            config.path("asset_output"),
            jsonl_bytes(assets),
            len(assets),
        ),
        "rag_chunks": (
            config.path("rag_output"),
            jsonl_bytes(rag["chunks"]),
            len(rag["chunks"]),
        ),
        "evidence_registry": (
            config.path("evidence_output"),
            jsonl_bytes(rag["evidence"]),
            len(rag["evidence"]),
        ),
    }


def build_synthetic_preview(config: PipelineConfig) -> Preview:
    definitions = replace_tokens(
        config.config("synthetic"), {"generated_at": config.generated_at}
    )
    outputs = definitions["materialized_outputs"]
    active_scenarios = {
        row["scenario_id"]
        for row in outputs["contract_alignment_registry"]
        if row["include_in_contract_projection"]
    }
    outputs["inquiries"] = [
        row for row in outputs["inquiries"]
        if row["scenario_id"] in active_scenarios
    ]
    active_inquiry_ids = {row["id"] for row in outputs["inquiries"]}
    outputs["consultations"] = [
        row for row in outputs["consultations"]
        if row["inquiry_id"] in active_inquiry_ids
    ]
    active_consultation_ids = {row["id"] for row in outputs["consultations"]}
    outputs["visits"] = [
        row for row in outputs["visits"]
        if row["inquiry_id"] in active_inquiry_ids
    ]
    active_visit_ids = {row["id"] for row in outputs["visits"]}
    outputs["care_histories"] = [
        row for row in outputs["care_histories"]
        if (
            row.get("inquiry_id") is None
            or row["inquiry_id"] in active_inquiry_ids
        )
        and (
            row.get("visit_id") is None
            or row["visit_id"] in active_visit_ids
        )
    ]
    outputs["followup_confirmations"] = [
        row for row in outputs["followup_confirmations"]
        if row["inquiry_id"] in active_inquiry_ids
        and (
            row.get("consultation_id") is None
            or row["consultation_id"] in active_consultation_ids
        )
        and (
            row.get("visit_id") is None
            or row["visit_id"] in active_visit_ids
        )
    ]
    target_ids = {
        "QUESTIONNAIRE": set(),
        "INQUIRY": active_inquiry_ids,
        "CONSULTATION": active_consultation_ids,
        "VISIT": active_visit_ids,
    }
    outputs["inquiry_status_histories"] = [
        row for row in outputs["inquiry_status_histories"]
        if row[f"{row['target_type_code'].lower()}_id"]
        in target_ids[row["target_type_code"]]
    ]
    outputs["audit_events"] = [
        row for row in outputs["audit_events"]
        if row["entity_id"] in target_ids[row["entity_type"]]
    ]
    for name in (
        "workflow_states",
        "evidence_references",
        "safety_assessments",
        "role_handoffs",
        "api_idempotency_cases",
    ):
        outputs[name] = [
            row for row in outputs[name]
            if row["scenario_id"] in active_scenarios
        ]
    definitions["materialized_subsets"] = {
        filename: [
            row for row in rows if row["scenario_id"] in active_scenarios
        ]
        for filename, rows in definitions["materialized_subsets"].items()
    }
    result: Preview = {}
    for key, rows in outputs.items():
        count = len(rows["scenarios"]) if key == "demo_scenarios" else len(rows)
        result[key] = (
            config.data_root / definitions["outputs"][key],
            json_bytes(rows),
            count,
        )
    for filename, rows in definitions["materialized_subsets"].items():
        result[f"scenario_subset:{filename}"] = (
            config.data_root / "synthetic" / "scenarios" / filename,
            json_bytes(rows),
            len(rows),
        )
    return result


def write_preview(config: PipelineConfig, preview: Preview) -> dict[str, Any]:
    for path, content, _ in preview.values():
        write_bytes(config.data_root, path, content)
    return {
        "status": "PASS",
        "generated_at": config.generated_at,
        "files": len(preview),
        "records": sum(count or 0 for _, _, count in preview.values()),
    }


def render_templates(config: PipelineConfig) -> Preview:
    result: Preview = {}
    for name, item in config.values["templates"].items():
        text = (config.data_root / item["template"]).read_text(encoding="utf-8")
        text = text.replace("${dataset_version}", config.dataset_version)
        text = text.replace("${generated_at}", config.generated_at)
        result[f"template:{name}"] = (
            config.data_root / item["target"],
            text.encode("utf-8"),
            None,
        )
    return result
