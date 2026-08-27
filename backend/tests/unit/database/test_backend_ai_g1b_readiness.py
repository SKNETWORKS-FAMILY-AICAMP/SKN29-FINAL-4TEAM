"""Backend-AI G1-B 읽기 전용 감사의 판정·비밀 보호 검증."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = BACKEND_DIR.parent
SCRIPT_PATH = (
    REPOSITORY_ROOT
    / "scripts"
    / "database"
    / "audit_backend_ai_g1b_readiness.py"
)
VALID_ENV = {
    "POSTGRES_DB": "waterbridge_team_integration",
    "POSTGRES_USER": "audit-user-must-not-appear",
    "POSTGRES_PASSWORD": "audit-password-must-not-appear",
    "POSTGRES_HOST": "127.0.0.1",
    "POSTGRES_PORT": "5432",
}


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "backend_ai_g1b_readiness",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


@pytest.fixture
def audit_module() -> ModuleType:
    return load_module()


def ready_snapshot(module: ModuleType) -> dict[str, object]:
    return {
        "database_name": module.TEAM_INTEGRATION_DATABASE,
        "server_version": "16.14",
        "pgvector_version": module.PREFERRED_PGVECTOR_VERSION,
        "migrations_table_exists": True,
        "applied_migrations": list(module.REQUIRED_MIGRATIONS),
        "crosswalk_table_exists": True,
        "active_verified_count": 7,
        "baseline_identity_count": 7,
        "crosswalk_model_counts": {"WPUJAC104DWH": 7},
        "product_table_exists": True,
        "product_support": {
            "WPUJAC104DWH": {
                "is_active": True,
                "is_supported_mvp": True,
            },
        },
        "crosswalk_page_table_exists": True,
        "crosswalk_page_link_count": 8,
        "view_exists": True,
        "view_columns": list(module.EXPECTED_VIEW_COLUMNS),
        "view_row_count": 7,
        "view_distinct_chunk_count": 7,
        "view_complete_lineage_count": 0,
        "view_model_counts": {"WPUJAC104DWH": 7},
        "role_exists": True,
        "role_policy_safe": True,
        "default_transaction_read_only": True,
        "schema_create": False,
        "view_select": True,
        "view_dml": False,
        "base_table_select": False,
    }


def test_ready_requires_all_crosswalk_view_and_role_gates(
    audit_module: ModuleType,
):
    result = audit_module.evaluate_snapshot(
        ready_snapshot(audit_module),
        require_team_database=True,
    )

    assert result["status"] == "READY"
    assert result["blockers"] == []
    assert result["crosswalk"] == {
        "expected": 7,
        "active_verified": 7,
        "baseline_identity": 7,
        "model_counts_expected": None,
        "model_counts": {"WPUJAC104DWH": 7},
        "page_table_exists": True,
        "page_links_expected": 8,
        "page_links": 8,
    }
    assert result["database"]["pgvector_version"] == "0.8.6"
    assert result["database"]["expected_pgvector_version"] == "0.8.6"
    assert result["database"]["preferred_pgvector_version"] == "0.8.6"
    assert result["database"]["supported_pgvector_versions"] == [
        "0.8.2",
        "0.8.6",
    ]
    assert result["database"]["pgvector_version_supported"] is True
    assert result["ai_readonly_role"]["view_select"] is True
    assert result["ai_readonly_role"]["base_table_select"] is False


def test_three_model_profile_requires_exact_53_row_runtime_gate(
    audit_module: ModuleType,
):
    snapshot = ready_snapshot(audit_module)
    snapshot.update(
        active_verified_count=53,
        baseline_identity_count=53,
        crosswalk_page_link_count=53,
        view_row_count=53,
        view_distinct_chunk_count=53,
        view_complete_lineage_count=53,
        crosswalk_model_counts=dict(audit_module.THREE_MODEL_COUNTS),
        view_model_counts=dict(audit_module.THREE_MODEL_COUNTS),
        product_support=dict(audit_module.THREE_MODEL_PRODUCT_SUPPORT),
    )

    result = audit_module.evaluate_snapshot(
        snapshot,
        require_team_database=True,
        evidence_profile="three-model",
    )

    assert result["status"] == "READY"
    assert result["evidence_profile"] == "three-model"
    assert result["crosswalk"] == {
        "expected": 53,
        "active_verified": 53,
        "baseline_identity": 53,
        "model_counts_expected": audit_module.THREE_MODEL_COUNTS,
        "model_counts": audit_module.THREE_MODEL_COUNTS,
        "page_table_exists": True,
        "page_links_expected": 53,
        "page_links": 53,
    }
    assert result["view"]["lineage"] == {
        "required": True,
        "required_keys": [
            "evidence_group_id",
            "source_variant_id",
            "parent_id",
            "retrieval_role",
            "record_type",
        ],
        "expected_complete": 53,
        "complete": 53,
        "incomplete": 0,
    }
    assert result["view"]["model_counts"] == audit_module.THREE_MODEL_COUNTS
    assert result["public_product_support_scope"] == {
        "required": True,
        "expected": audit_module.THREE_MODEL_PRODUCT_SUPPORT,
        "actual": audit_module.THREE_MODEL_PRODUCT_SUPPORT,
        "matches": True,
    }


def test_three_model_profile_rejects_incomplete_view_lineage(
    audit_module: ModuleType,
):
    snapshot = ready_snapshot(audit_module)
    snapshot.update(
        active_verified_count=53,
        baseline_identity_count=53,
        crosswalk_page_link_count=53,
        view_row_count=53,
        view_distinct_chunk_count=53,
        view_complete_lineage_count=52,
        crosswalk_model_counts=dict(audit_module.THREE_MODEL_COUNTS),
        view_model_counts=dict(audit_module.THREE_MODEL_COUNTS),
        product_support=dict(audit_module.THREE_MODEL_PRODUCT_SUPPORT),
    )

    result = audit_module.evaluate_snapshot(
        snapshot,
        evidence_profile="three-model",
    )

    assert result["status"] == "BLOCKED"
    assert "BACKEND_AI_RAG_VIEW_COMPLETE_LINEAGE_COUNT_NOT_53" in result[
        "blockers"
    ]
    assert result["view"]["lineage"]["incomplete"] == 1


def test_three_model_profile_rejects_legacy_seven_row_database(
    audit_module: ModuleType,
):
    result = audit_module.evaluate_snapshot(
        ready_snapshot(audit_module),
        evidence_profile="three-model",
    )

    assert result["status"] == "BLOCKED"
    assert "ACTIVE_VERIFIED_CROSSWALK_COUNT_NOT_53" in result["blockers"]
    assert "BASELINE_EMBEDDING_IDENTITY_COUNT_NOT_53" in result["blockers"]
    assert "ACTIVE_VERIFIED_CROSSWALK_PAGE_LINK_COUNT_NOT_53" in result[
        "blockers"
    ]
    assert "BACKEND_AI_RAG_VIEW_ROW_COUNT_NOT_53" in result["blockers"]


def test_three_model_profile_rejects_distribution_or_public_scope_drift(
    audit_module: ModuleType,
):
    snapshot = ready_snapshot(audit_module)
    snapshot.update(
        active_verified_count=53,
        baseline_identity_count=53,
        crosswalk_page_link_count=53,
        view_row_count=53,
        view_distinct_chunk_count=53,
        view_complete_lineage_count=53,
        crosswalk_model_counts={"WPUJAC104DWH": 53},
        view_model_counts={"WPUJAC104DWH": 53},
        product_support={
            **audit_module.THREE_MODEL_PRODUCT_SUPPORT,
            "WPUIAC425SNW": {
                "is_active": True,
                "is_supported_mvp": True,
            },
        },
    )

    result = audit_module.evaluate_snapshot(
        snapshot,
        evidence_profile="three-model",
    )

    assert result["status"] == "BLOCKED"
    assert (
        "ACTIVE_VERIFIED_CROSSWALK_MODEL_DISTRIBUTION_MISMATCH"
        in result["blockers"]
    )
    assert "BACKEND_AI_RAG_VIEW_MODEL_DISTRIBUTION_MISMATCH" in result[
        "blockers"
    ]
    assert "THREE_MODEL_PUBLIC_PRODUCT_SUPPORT_SCOPE_MISMATCH" in result[
        "blockers"
    ]


@pytest.mark.parametrize("version", ["0.8.2", "0.8.6"])
def test_explicitly_supported_pgvector_versions_are_ready(
    audit_module: ModuleType,
    version: str,
):
    snapshot = ready_snapshot(audit_module)
    snapshot["pgvector_version"] = version

    result = audit_module.evaluate_snapshot(snapshot)

    assert result["status"] == "READY"
    assert result["blockers"] == []
    assert result["database"]["pgvector_version"] == version
    assert result["database"]["pgvector_version_supported"] is True


@pytest.mark.parametrize("version", ["0.7.4", "0.8.1", "0.8.3", "0.9.0"])
def test_unverified_pgvector_versions_fail_closed(
    audit_module: ModuleType,
    version: str,
):
    snapshot = ready_snapshot(audit_module)
    snapshot["pgvector_version"] = version

    result = audit_module.evaluate_snapshot(snapshot)

    assert result["status"] == "BLOCKED"
    assert "PGVECTOR_VERSION_MISMATCH" in result["blockers"]
    assert result["database"]["pgvector_version_supported"] is False


@pytest.mark.parametrize(
    "field, invalid_value, expected_blocker",
    [
        (
            "active_verified_count",
            6,
            "ACTIVE_VERIFIED_CROSSWALK_COUNT_NOT_7",
        ),
        (
            "baseline_identity_count",
            6,
            "BASELINE_EMBEDDING_IDENTITY_COUNT_NOT_7",
        ),
        (
            "crosswalk_page_link_count",
            7,
            "ACTIVE_VERIFIED_CROSSWALK_PAGE_LINK_COUNT_NOT_8",
        ),
        (
            "pgvector_version",
            "0.7.4",
            "PGVECTOR_VERSION_MISMATCH",
        ),
        ("view_row_count", 0, "BACKEND_AI_RAG_VIEW_ROW_COUNT_NOT_7"),
        ("view_select", False, "AI_READONLY_VIEW_SELECT_DENIED"),
        ("view_dml", True, "AI_READONLY_VIEW_DML_ALLOWED"),
        (
            "base_table_select",
            True,
            "AI_READONLY_BASE_TABLE_SELECT_ALLOWED",
        ),
        (
            "default_transaction_read_only",
            False,
            "AI_READONLY_DEFAULT_TRANSACTION_NOT_READ_ONLY",
        ),
    ],
)
def test_each_data_or_privilege_gap_blocks_ready(
    audit_module: ModuleType,
    field: str,
    invalid_value: object,
    expected_blocker: str,
):
    snapshot = ready_snapshot(audit_module)
    snapshot[field] = invalid_value

    result = audit_module.evaluate_snapshot(snapshot)

    assert result["status"] == "BLOCKED"
    assert expected_blocker in result["blockers"]


def test_view_column_order_and_team_database_are_explicit_gates(
    audit_module: ModuleType,
):
    snapshot = ready_snapshot(audit_module)
    snapshot["database_name"] = "author_local_database"
    snapshot["view_columns"] = list(reversed(snapshot["view_columns"]))

    result = audit_module.evaluate_snapshot(
        snapshot,
        require_team_database=True,
    )

    assert result["status"] == "BLOCKED"
    assert "TEAM_INTEGRATION_DATABASE_MISMATCH" in result["blockers"]
    assert "BACKEND_AI_RAG_VIEW_COLUMNS_MISMATCH" in result["blockers"]


def test_missing_pgvector_and_crosswalk_page_table_fail_closed(
    audit_module: ModuleType,
):
    snapshot = ready_snapshot(audit_module)
    snapshot["pgvector_version"] = None
    snapshot["crosswalk_page_table_exists"] = False
    snapshot["crosswalk_page_link_count"] = 0

    result = audit_module.evaluate_snapshot(snapshot)

    assert result["status"] == "BLOCKED"
    assert "PGVECTOR_EXTENSION_MISSING" in result["blockers"]
    assert "CROSSWALK_PAGE_TABLE_MISSING" in result["blockers"]
    assert (
        "ACTIVE_VERIFIED_CROSSWALK_PAGE_LINK_COUNT_NOT_8"
        in result["blockers"]
    )


def test_latest_pgvector_dimension_migration_is_required(
    audit_module: ModuleType,
):
    snapshot = ready_snapshot(audit_module)
    snapshot["applied_migrations"].remove(
        "0011_cast_chunk_embedding_vector_dimensions"
    )

    result = audit_module.evaluate_snapshot(snapshot)

    assert result["status"] == "BLOCKED"
    assert (
        "MIGRATION_MISSING:0011_cast_chunk_embedding_vector_dimensions"
        in result["blockers"]
    )


def test_latest_readonly_view_lineage_migration_is_required(
    audit_module: ModuleType,
):
    snapshot = ready_snapshot(audit_module)
    snapshot["applied_migrations"].remove(
        "0013_expand_backend_ai_rag_lineage_metadata"
    )

    result = audit_module.evaluate_snapshot(snapshot)

    assert result["status"] == "BLOCKED"
    assert (
        "MIGRATION_MISSING:0013_expand_backend_ai_rag_lineage_metadata"
        in result["blockers"]
    )


def test_latest_ai_product_eligibility_migration_is_required(
    audit_module: ModuleType,
):
    snapshot = ready_snapshot(audit_module)
    snapshot["applied_migrations"].remove(
        "0014_decouple_ai_view_product_eligibility"
    )

    result = audit_module.evaluate_snapshot(snapshot)

    assert result["status"] == "BLOCKED"
    assert (
        "MIGRATION_MISSING:0014_decouple_ai_view_product_eligibility"
        in result["blockers"]
    )


def test_connection_is_forced_read_only_and_result_does_not_expose_secrets(
    audit_module: ModuleType,
):
    options = audit_module.load_connection_options(VALID_ENV)

    assert options["options"] == "-c default_transaction_read_only=on"

    def failing_connect(**_kwargs):
        raise RuntimeError(
            "127.0.0.1 audit-user-must-not-appear "
            "audit-password-must-not-appear"
        )

    result, exit_code = audit_module.run_audit(
        VALID_ENV,
        connect=failing_connect,
    )
    serialized = json.dumps(result, ensure_ascii=False)

    assert exit_code == 1
    assert result["status"] == "AUDIT_FAILED"
    assert "audit-user-must-not-appear" not in serialized
    assert "audit-password-must-not-appear" not in serialized
    assert "127.0.0.1" not in serialized


def test_require_ready_changes_exit_code_without_mutating_result(
    audit_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
):
    blocked = ready_snapshot(audit_module)
    blocked["view_row_count"] = 0
    blocked["view_distinct_chunk_count"] = 0
    monkeypatch.setattr(
        audit_module,
        "collect_snapshot",
        lambda _options, _connect: blocked,
    )

    report, report_exit = audit_module.run_audit(
        VALID_ENV,
        require_ready=False,
    )
    gate, gate_exit = audit_module.run_audit(
        VALID_ENV,
        require_ready=True,
    )

    assert report == gate
    assert report["status"] == "BLOCKED"
    assert report_exit == 0
    assert gate_exit == 1


def test_missing_environment_fails_before_connecting(
    audit_module: ModuleType,
):
    result, exit_code = audit_module.run_audit(
        {},
        connect=lambda **_kwargs: pytest.fail("must not connect"),
    )

    assert exit_code == 2
    assert result["status"] == "NOT_CONFIGURED"
    assert set(result["missing_keys"]) == set(audit_module.REQUIRED_ENV_KEYS)
