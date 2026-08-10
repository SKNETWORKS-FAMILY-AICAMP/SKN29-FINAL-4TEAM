"""T-028B contract preparation and fail-closed readiness tests."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType


BACKEND_DIR = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = BACKEND_DIR.parent
READINESS_PATH = BACKEND_DIR / "apps" / "evidence" / "readiness.py"
EXAMPLE_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "api"
    / "preparation"
    / "evidence"
    / "evidence-card.contract-preparation.json"
)
SCREEN_CONTRACT_FIELDS = {
    "evidence_id",
    "chunk_id",
    "document_id",
    "document_title",
    "document_version",
    "page_refs",
    "section_title",
    "evidence_summary",
    "source_type",
    "provider",
    "risk_level",
    "requires_consultation",
    "safe_actions",
    "escalation_conditions",
    "prohibited_actions",
    "verification_status",
    "source_landing_url",
    "source_direct_download_url",
    "product_code",
    "manual_model",
    "product_generation",
    "model_family",
    "scope_role",
    "data_classification",
}
PROHIBITED_FIELDS = {
    "source_path",
    "manual_page_text",
    "retrieval_text",
    "similarity_score",
    "search_score",
    "prompt",
    "raw_text",
    "source_storage_path",
}


def load_readiness() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "t028b_evidence_readiness",
        READINESS_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def collect_keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key
            for nested in value.values()
            for key in collect_keys(nested)
        }
    if isinstance(value, list):
        return {
            key for nested in value for key in collect_keys(nested)
        }
    return set()


def test_contract_example_matches_screen_fields_and_role_privacy():
    document = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    assert document["artifact_scope"] == (
        "NON_RUNTIME_CONTRACT_PREPARATION"
    )
    assert document["contract_status"] == "PREPARATION_ONLY"
    assert document["runtime_implemented"] is False
    assert set(document["role_examples"]) == {
        "CUSTOMER",
        "CONSULTANT",
        "TECHNICIAN",
    }
    for role, payload in document["role_examples"].items():
        expected_fields = (
            SCREEN_CONTRACT_FIELDS - {"chunk_id"}
            if role == "CUSTOMER"
            else SCREEN_CONTRACT_FIELDS
        )
        assert set(payload) == expected_fields
        assert not (collect_keys(payload) & PROHIBITED_FIELDS)
        assert payload["data_classification"] == "official"
        assert payload["product_code"] == "WPUJAC104DWH"
        assert payload["manual_model"] == "WPU-JAC104D"


def test_current_repository_fails_closed_before_t028b_runtime():
    result = load_readiness().audit_readiness()

    assert result["status"] == "PREPARATION_ONLY"
    assert result["runtime_ready"] is False
    assert result["blockers"] == [
        "W5_G04_NOT_PASS",
        "T028A_NOT_COMPLETE",
        "EVIDENCE_API_CONTRACT_EMPTY",
        "EVIDENCE_RUNTIME_STUBS_ONLY",
    ]
    assert result["evidence"][
        "contract_preparation_example_ready"
    ] is True


def test_runtime_gate_cli_exits_nonzero_while_dependencies_are_open():
    completed = subprocess.run(
        [sys.executable, str(READINESS_PATH), "--require-runtime-ready"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    result = json.loads(completed.stdout)

    assert completed.returncode == 2
    assert result["status"] == "PREPARATION_ONLY"
    assert result["runtime_ready"] is False
