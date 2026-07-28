"""T-005 계약 테이블과 Django 구현 매핑 감사 회귀 검증."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = BACKEND_DIR.parent
READINESS_PATH = (
    REPOSITORY_ROOT
    / "scripts"
    / "database"
    / "audit_t005_implementation_readiness.py"
)


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "t005_implementation_readiness_mapping",
        READINESS_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def readiness_module() -> ModuleType:
    return load_module()


def test_model_declarations_ignore_docstring_only_placeholder(
    readiness_module: ModuleType,
):
    placeholder = (
        REPOSITORY_ROOT
        / "backend"
        / "apps"
        / "inquiries"
        / "models"
        / "inquiry.py"
    )
    actual = (
        REPOSITORY_ROOT
        / "backend"
        / "apps"
        / "accounts"
        / "models"
        / "user.py"
    )

    assert readiness_module.collect_model_declarations(placeholder) == []
    declarations = readiness_module.collect_model_declarations(actual)
    assert len(declarations) == 1
    assert declarations[0]["class_name"] == "User"
    assert declarations[0]["db_table"] == "accounts_user"


def test_migration_declarations_read_actual_db_tables(
    readiness_module: ModuleType,
):
    migration = (
        REPOSITORY_ROOT
        / "backend"
        / "apps"
        / "accounts"
        / "migrations"
        / "0001_initial.py"
    )

    declarations = readiness_module.collect_migration_declarations(
        [migration]
    )

    assert {
        item["db_table"]
        for item in declarations
    } == {"accounts_user", "customers_customer_profile"}
    assert all(
        item["explicit_db_table"] is True
        for item in declarations
    )


def test_mapping_distinguishes_each_implementation_layer(
    readiness_module: ModuleType,
):
    result = readiness_module.build_table_mapping(
        contract_tables={
            "complete_table": {"domain": "A", "owner": "Django"},
            "unregistered_table": {"domain": "B", "owner": "Django"},
            "missing_migration_table": {
                "domain": "C",
                "owner": "Django",
            },
            "missing_table": {"domain": "D", "owner": "Django"},
        },
        model_declarations=[
            {
                "class_name": "Complete",
                "db_table": "complete_table",
                "module_path": "complete.py",
            },
            {
                "class_name": "Unregistered",
                "db_table": "unregistered_table",
                "module_path": "unregistered.py",
            },
            {
                "class_name": "MissingMigration",
                "db_table": "missing_migration_table",
                "module_path": "missing_migration.py",
            },
        ],
        registered_models=[
            {
                "label": "sample.Complete",
                "db_table": "complete_table",
                "module": "sample.complete",
            },
            {
                "label": "sample.MissingMigration",
                "db_table": "missing_migration_table",
                "module": "sample.missing_migration",
            },
        ],
        migration_declarations=[
            {
                "app_label": "sample",
                "model_name": "Complete",
                "db_table": "complete_table",
                "migration_path": "0001_initial.py",
            },
            {
                "app_label": "sample",
                "model_name": "Unregistered",
                "db_table": "unregistered_table",
                "migration_path": "0001_initial.py",
            },
        ],
    )
    statuses = {
        item["table"]: item["status"]
        for item in result["tables"]
    }

    assert statuses == {
        "complete_table": "IMPLEMENTED",
        "missing_migration_table": "MIGRATION_MISSING",
        "missing_table": "MISSING",
        "unregistered_table": "MODEL_NOT_REGISTERED",
    }
    assert result["implemented_tables"] == ["complete_table"]
    assert result["unregistered_model_tables"] == [
        "unregistered_table"
    ]
    assert result["missing_migration_tables"] == [
        "missing_migration_table",
        "missing_table",
    ]


def test_repository_audit_maps_all_32_tables_without_false_completion(
    readiness_module: ModuleType,
):
    result = readiness_module.audit_readiness()
    mapping = result["evidence"]["implementation_mapping"]
    summary = mapping["summary"]

    assert result["status"] == "NOT_READY"
    assert result["scope"] == "T005_DJANGO_MODEL_MIGRATION_MAPPING"
    assert summary["contract_table_count"] == 32
    assert summary["declared_contract_model_count"] == 2
    assert summary["registered_contract_model_count"] == 2
    assert summary["migration_contract_table_count"] == 2
    assert summary["fully_implemented_contract_table_count"] == 2
    assert mapping["implemented_tables"] == [
        "accounts_user",
        "customers_customer_profile",
    ]
    assert len(mapping["missing_model_tables"]) == 30
    assert len(mapping["missing_migration_tables"]) == 30
    assert result["evidence"]["contract"]["contract_status"] == (
        "OWNER_BASELINE"
    )
    assert result["evidence"]["contract"]["contract_confirmation_status"] == (
        "CONFIRMED"
    )
    assert result["evidence"]["contract"]["completion_review_status"] == (
        "PENDING"
    )
    assert "PHYSICAL_CONTRACT_REVIEW_PENDING" not in result["blockers"]
    assert "PHYSICAL_CONTRACT_NOT_CONFIRMED" not in result["blockers"]
    assert "CONTRACT_MODEL_DECLARATIONS_INCOMPLETE" in result["blockers"]
    assert "CONTRACT_MIGRATIONS_INCOMPLETE" in result["blockers"]


def test_postgresql_environment_requires_nonblank_values(
    readiness_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
):
    for key in readiness_module.REQUIRED_POSTGRES_ENV_KEYS:
        monkeypatch.setenv(key, "   ")

    evidence = readiness_module.collect_static_evidence()

    assert evidence["postgres_env_keys_present"] == []
    assert evidence["postgres_env_complete"] is False
