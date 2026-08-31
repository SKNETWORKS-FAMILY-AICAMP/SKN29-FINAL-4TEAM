"""Strict loader for the isolated three-model reference scenario catalogue."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "reference_cases"
    / "three_model_reference_scenarios_v1.json"
)
EVIDENCE_GROUP_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "processed"
    / "structured"
    / "evidence"
    / "rag_evidence_groups_3model_v1.jsonl"
)

CATALOG_VERSION = "three-model-reference-v1"
EXPECTED_RECORDS = 45
CATALOG_KEYS = {
    "catalog_version",
    "catalog_status",
    "runtime_use",
    "training_use",
    "curation_status",
    "expected_records",
    "description",
    "scenarios",
}
SCENARIO_KEYS = {
    "scenario_id",
    "exact_model_code",
    "model_family",
    "risk_level",
    "title",
    "customer_utterance",
    "topic_code",
    "context_facts",
    "source_document_id",
    "source_policy",
    "manual_page_refs",
    "evidence_group_ids",
    "evidence_readiness",
    "expected_route",
    "expected_requires_consultation",
    "expected_publication_gate",
    "expected_usage_guidance_status",
    "expected_reason",
    "response_outline",
}

MODEL_CONTRACTS = {
    "WPUJAC104DWH": {
        "model_family": "WPU-JAC104",
        "id_prefix": "REF-JAC104",
        "source_document_id": (
            "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00"
        ),
        "source_policy": "MVP_SOURCE_REFERENCE",
        "manual_path": (
            REPOSITORY_ROOT
            / "data"
            / "processed"
            / "documents"
            / "manuals"
            / "mvp"
            / "manual_pages_jac104d.jsonl"
        ),
    },
    "WPUIAC425SNW": {
        "model_family": "WPU-IAC425",
        "id_prefix": "REF-IAC425",
        "source_document_id": "MAN-SKMAGIC-WPU-IAC425-REV02",
        "source_policy": "EXPANSION_REFERENCE_ONLY",
        "manual_path": (
            REPOSITORY_ROOT
            / "data"
            / "processed"
            / "documents"
            / "manuals"
            / "expansion"
            / "manual_pages_iac425.jsonl"
        ),
    },
    "WPUIAC606SNW": {
        "model_family": "WPU-IAC606",
        "id_prefix": "REF-IAC606",
        "source_document_id": "MAN-SKMAGIC-WPU-IAC606-REV00",
        "source_policy": "EXPANSION_REFERENCE_ONLY",
        "manual_path": (
            REPOSITORY_ROOT
            / "data"
            / "processed"
            / "documents"
            / "manuals"
            / "expansion"
            / "manual_pages_iac606.jsonl"
        ),
    },
}

RISK_CONTRACTS = {
    "general": {
        "id_code": "G",
        "expected_route": "AI_GUIDANCE",
        "expected_requires_consultation": False,
        "expected_publication_gate": "AUTO_GUIDANCE_ELIGIBLE",
        "expected_usage_guidance_status": "NORMAL",
    },
    "caution": {
        "id_code": "C",
        "expected_route": "HUMAN_REVIEW",
        "expected_requires_consultation": None,
        "expected_publication_gate": "HUMAN_APPROVAL_REQUIRED",
        "expected_usage_guidance_status": "PARTIAL_STOP",
    },
    "danger": {
        "id_code": "D",
        "expected_route": "EMERGENCY_ESCALATION",
        "expected_requires_consultation": True,
        "expected_publication_gate": "SAFETY_ESCALATION_ONLY",
        "expected_usage_guidance_status": "TOTAL_STOP",
    },
}

EVIDENCE_TOPIC_ALIASES = {
    "symptom_cold_lock": {"cold_lock"},
    "symptom_cold_temperature": {
        "symptom_cold_temperature",
        "cold_temperature_normal",
        "cold_temperature_fault",
    },
    "symptom_noise": {"symptom_noise", "noise_normal"},
    "symptom_low_flow": {"symptom_low_flow", "low_flow"},
    "symptom_no_water": {"symptom_no_water", "no_water"},
    "symptom_taste_odor": {"symptom_taste_odor", "taste_odor"},
    "symptom_hot_steam": {
        "symptom_hot_water",
        "symptom_hot_water_safety",
        "hot_steam",
    },
    "symptom_hot_water_temperature": {
        "symptom_hot_water",
        "symptom_hot_water_safety",
        "no_hot_water",
    },
    "symptom_hot_water_safety": {
        "symptom_hot_water",
        "symptom_hot_water_safety",
        "hot_water_stopped",
    },
    "symptom_ice_making_noise": {"ice_making_noise"},
    "symptom_defrost_noise": {"defrost_noise"},
    "symptom_no_ice": {"no_ice"},
    "symptom_particles": {"particles"},
    "symptom_hot_water_stopped": {"hot_water_stopped"},
    "symptom_leak": {"symptom_leak", "leak"},
}


class ReferenceCatalogError(ValueError):
    """Raised before any database write when catalogue data is invalid."""


@dataclass(frozen=True)
class LoadedReferenceCatalog:
    """Validated source rows plus stable content hashes."""

    path: Path
    catalog_version: str
    catalog_sha256: str
    rows: tuple[dict[str, Any], ...]
    record_sha256: dict[str, str]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ReferenceCatalogError(
                f"invalid JSONL: {path}:{line_number}"
            ) from exc
        if not isinstance(row, dict):
            raise ReferenceCatalogError(
                f"JSONL row must be an object: {path}:{line_number}"
            )
        rows.append(row)
    return rows


def _manual_pages() -> dict[str, set[int]]:
    pages: dict[str, set[int]] = {}
    for model_code, contract in MODEL_CONTRACTS.items():
        rows = _read_jsonl(Path(contract["manual_path"]))
        matching = {
            int(row["page"])
            for row in rows
            if row.get("exact_sales_code") == model_code
            and row.get("document_id") == contract["source_document_id"]
        }
        if not matching:
            raise ReferenceCatalogError(
                f"manual source is empty for {model_code}"
            )
        pages[model_code] = matching
    return pages


def _evidence_groups() -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(EVIDENCE_GROUP_PATH):
        evidence_id = row.get("evidence_group_id")
        if isinstance(evidence_id, str):
            groups[evidence_id] = row
    if not groups:
        raise ReferenceCatalogError("three-model evidence registry is empty")
    return groups


def _require_nonempty_text(row: dict[str, Any], field: str, case_id: str) -> None:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ReferenceCatalogError(f"{case_id}:{field}:nonempty text required")


def _require_text_list(row: dict[str, Any], field: str, case_id: str) -> None:
    value = row.get(field)
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item.strip() for item in value)
        or len(value) != len(set(value))
    ):
        raise ReferenceCatalogError(
            f"{case_id}:{field}:unique nonempty text list required"
        )


def _expected_case_ids() -> set[str]:
    return {
        f"{model['id_prefix']}-{risk['id_code']}-{index:03d}"
        for model in MODEL_CONTRACTS.values()
        for risk in RISK_CONTRACTS.values()
        for index in range(1, 6)
    }


def _validate_scenario(
    row: dict[str, Any],
    *,
    evidence_groups: dict[str, dict[str, Any]],
    manual_pages: dict[str, set[int]],
) -> None:
    case_id = str(row.get("scenario_id", "<missing>"))
    if set(row) != SCENARIO_KEYS:
        missing = sorted(SCENARIO_KEYS - set(row))
        extra = sorted(set(row) - SCENARIO_KEYS)
        raise ReferenceCatalogError(
            f"{case_id}:field contract mismatch missing={missing} extra={extra}"
        )
    for field in (
        "scenario_id",
        "model_family",
        "title",
        "customer_utterance",
        "topic_code",
        "source_document_id",
        "expected_reason",
    ):
        _require_nonempty_text(row, field, case_id)
    _require_text_list(row, "context_facts", case_id)
    _require_text_list(row, "response_outline", case_id)

    model_code = row.get("exact_model_code")
    if model_code not in MODEL_CONTRACTS:
        raise ReferenceCatalogError(f"{case_id}:unsupported exact model")
    model_contract = MODEL_CONTRACTS[model_code]
    for field in ("model_family", "source_document_id", "source_policy"):
        if row.get(field) != model_contract[field]:
            raise ReferenceCatalogError(f"{case_id}:{field}:model mismatch")

    risk_level = row.get("risk_level")
    if risk_level not in RISK_CONTRACTS:
        raise ReferenceCatalogError(f"{case_id}:unsupported risk level")
    risk_contract = RISK_CONTRACTS[risk_level]
    expected_pattern = re.compile(
        rf"^{re.escape(model_contract['id_prefix'])}-"
        rf"{risk_contract['id_code']}-00[1-5]$"
    )
    if not expected_pattern.fullmatch(case_id):
        raise ReferenceCatalogError(f"{case_id}:id/model/risk mismatch")
    for field in (
        "expected_route",
        "expected_publication_gate",
        "expected_usage_guidance_status",
    ):
        if row.get(field) != risk_contract[field]:
            raise ReferenceCatalogError(f"{case_id}:{field}:oracle mismatch")
    consultation_expected = risk_contract["expected_requires_consultation"]
    consultation_value = row.get("expected_requires_consultation")
    if not isinstance(consultation_value, bool):
        raise ReferenceCatalogError(
            f"{case_id}:expected_requires_consultation:boolean required"
        )
    if (
        consultation_expected is not None
        and consultation_value is not consultation_expected
    ):
        raise ReferenceCatalogError(
            f"{case_id}:expected_requires_consultation:oracle mismatch"
        )

    page_refs = row.get("manual_page_refs")
    if (
        not isinstance(page_refs, list)
        or not page_refs
        or any(
            not isinstance(page, int) or isinstance(page, bool) or page <= 0
            for page in page_refs
        )
        or page_refs != sorted(set(page_refs))
    ):
        raise ReferenceCatalogError(
            f"{case_id}:manual_page_refs:sorted unique positive integers required"
        )
    unknown_pages = set(page_refs) - manual_pages[model_code]
    if unknown_pages:
        raise ReferenceCatalogError(
            f"{case_id}:manual pages not found: {sorted(unknown_pages)}"
        )

    evidence_ids = row.get("evidence_group_ids")
    if (
        not isinstance(evidence_ids, list)
        or any(not isinstance(item, str) or not item for item in evidence_ids)
        or evidence_ids != sorted(set(evidence_ids))
    ):
        raise ReferenceCatalogError(
            f"{case_id}:evidence_group_ids:sorted unique text list required"
        )
    readiness = row.get("evidence_readiness")
    linked_readiness = {
        "SCENARIO_GROUP_VERIFIED",
        "TOPIC_GROUP_SELECTION_PENDING",
    }
    if readiness in linked_readiness and not evidence_ids:
        raise ReferenceCatalogError(f"{case_id}:linked evidence group is missing")
    if readiness == "SOURCE_PAGE_ONLY" and evidence_ids:
        raise ReferenceCatalogError(
            f"{case_id}:source-page-only case cannot claim an evidence group"
        )
    if readiness not in linked_readiness | {"SOURCE_PAGE_ONLY"}:
        raise ReferenceCatalogError(f"{case_id}:invalid evidence readiness")
    for evidence_id in evidence_ids:
        evidence = evidence_groups.get(evidence_id)
        if not evidence or evidence.get("exact_sales_code") != model_code:
            raise ReferenceCatalogError(
                f"{case_id}:missing or cross-model evidence: {evidence_id}"
            )
        if evidence.get("document_id") != row["source_document_id"]:
            raise ReferenceCatalogError(
                f"{case_id}:cross-document evidence: {evidence_id}"
            )
        evidence_pages = evidence.get("page_refs")
        if (
            not isinstance(evidence_pages, list)
            or not set(page_refs).issubset(evidence_pages)
        ):
            raise ReferenceCatalogError(
                f"{case_id}:evidence does not cover source pages: {evidence_id}"
            )
        aliases = EVIDENCE_TOPIC_ALIASES.get(row["topic_code"], set())
        if evidence.get("topic_code") not in aliases:
            raise ReferenceCatalogError(
                f"{case_id}:evidence topic mismatch: {evidence_id}"
            )
        if (
            evidence.get("verification_status") != "TEXT_AND_VISUAL_VERIFIED"
            or evidence.get("allowed_use") != "RAG_HANDOFF_ONLY"
        ):
            raise ReferenceCatalogError(
                f"{case_id}:evidence is not verified handoff data: {evidence_id}"
            )
        if readiness == "SCENARIO_GROUP_VERIFIED" and (
            evidence.get("risk_level") != risk_level
            or evidence.get("requires_consultation")
            is not consultation_value
        ):
            raise ReferenceCatalogError(
                f"{case_id}:scenario-level evidence oracle mismatch: {evidence_id}"
            )


def load_reference_catalog(
    path: Path | str = DEFAULT_CATALOG_PATH,
) -> LoadedReferenceCatalog:
    """Load and fail closed on count, lineage, evidence, or oracle drift."""

    resolved = Path(path).resolve()
    raw_bytes = resolved.read_bytes()
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceCatalogError(f"invalid catalogue JSON: {resolved}") from exc
    if not isinstance(payload, dict) or set(payload) != CATALOG_KEYS:
        raise ReferenceCatalogError("catalogue top-level field contract mismatch")
    expected_header = {
        "catalog_version": CATALOG_VERSION,
        "catalog_status": "REFERENCE_ONLY",
        "runtime_use": "REFERENCE_ONLY",
        "training_use": "PROHIBITED",
        "curation_status": "CANDIDATE",
        "expected_records": EXPECTED_RECORDS,
    }
    for field, expected in expected_header.items():
        if payload.get(field) != expected:
            raise ReferenceCatalogError(f"catalogue header mismatch: {field}")
    if not isinstance(payload.get("description"), str) or not payload[
        "description"
    ].strip():
        raise ReferenceCatalogError("catalogue description is required")

    rows = payload.get("scenarios")
    if not isinstance(rows, list) or len(rows) != EXPECTED_RECORDS:
        raise ReferenceCatalogError(
            f"catalogue must contain exactly {EXPECTED_RECORDS} scenarios"
        )
    if any(not isinstance(row, dict) for row in rows):
        raise ReferenceCatalogError("every scenario must be an object")

    manual_pages = _manual_pages()
    evidence_groups = _evidence_groups()
    for row in rows:
        _validate_scenario(
            row,
            evidence_groups=evidence_groups,
            manual_pages=manual_pages,
        )

    case_ids = [row["scenario_id"] for row in rows]
    if len(case_ids) != len(set(case_ids)):
        raise ReferenceCatalogError("scenario IDs must be unique")
    if set(case_ids) != _expected_case_ids():
        raise ReferenceCatalogError("scenario ID matrix is incomplete or unexpected")

    distribution = Counter(
        (row["exact_model_code"], row["risk_level"]) for row in rows
    )
    expected_distribution = {
        (model_code, risk_level): 5
        for model_code in MODEL_CONTRACTS
        for risk_level in RISK_CONTRACTS
    }
    if dict(distribution) != expected_distribution:
        raise ReferenceCatalogError("scenario model/risk distribution must be 5 each")

    record_hashes = {
        row["scenario_id"]: _sha256(_canonical_bytes(row)) for row in rows
    }
    return LoadedReferenceCatalog(
        path=resolved,
        catalog_version=CATALOG_VERSION,
        catalog_sha256=_sha256(raw_bytes),
        rows=tuple(rows),
        record_sha256=record_hashes,
    )
