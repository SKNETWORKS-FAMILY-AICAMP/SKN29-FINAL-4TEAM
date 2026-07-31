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


def test_model_declarations_detect_implemented_contract_models(
    readiness_module: ModuleType,
):
    action_result = (
        REPOSITORY_ROOT
        / "backend"
        / "apps"
        / "inquiries"
        / "models"
        / "customer_action_result.py"
    )
    actual = (
        REPOSITORY_ROOT
        / "backend"
        / "apps"
        / "inquiries"
        / "models"
        / "inquiry.py"
    )

    action_result_declarations = (
        readiness_module.collect_model_declarations(action_result)
    )
    inquiry_declarations = (
        readiness_module.collect_model_declarations(actual)
    )

    assert action_result_declarations == [
        {
            "class_name": "CustomerActionResult",
            "db_table": "support_customer_action_result",
            "module_path": (
                "backend/apps/inquiries/models/"
                "customer_action_result.py"
            ),
        }
    ]
    assert len(inquiry_declarations) == 1
    assert inquiry_declarations[0]["class_name"] == "Inquiry"
    assert inquiry_declarations[0]["db_table"] == "support_inquiry"


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


def test_runtime_support_allowlist_is_exact_and_unknown_fifth_table_blocks(
    readiness_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
):
    contract_table = "contract_table"
    unknown_table = "unapproved_runtime_table"
    runtime_tables = sorted(
        readiness_module.APPROVED_RUNTIME_SUPPORT_TABLES
    )
    all_tables = [contract_table, *runtime_tables, unknown_table]
    model_declarations = [
        {
            "class_name": f"Model{index}",
            "db_table": table_name,
            "module_path": f"model_{index}.py",
        }
        for index, table_name in enumerate(all_tables)
    ]
    registered_models = [
        {
            "label": f"sample.Model{index}",
            "db_table": table_name,
            "module": f"sample.model_{index}",
        }
        for index, table_name in enumerate(all_tables)
    ]
    migration_declarations = [
        {
            "app_label": "sample",
            "model_name": f"Model{index}",
            "db_table": table_name,
            "migration_path": "0001_initial.py",
        }
        for index, table_name in enumerate(all_tables)
    ]
    contract = {
        "manifest_expected_table_count": 1,
        "contract_table_count": 1,
        "contract_snapshot": readiness_module.SCHEMA_PATH.name,
        "contract_snapshot_immutable": True,
        "contract_status": "OWNER_BASELINE",
        "contract_confirmation_status": "CONFIRMED",
        "completion_review_status": "PENDING",
        "tables": {
            contract_table: {
                "domain": "test",
                "owner": "Django",
            }
        },
    }
    static = {
        "model_declarations": model_declarations,
        "migration_declarations": migration_declarations,
        "model_class_count": len(model_declarations),
        "numbered_migration_count": 1,
        "docker_compose_configured": True,
        "postgres_env_complete": True,
    }
    django_evidence = {
        "registered_models": registered_models,
        "registered_local_apps": ["apps.sample"],
        "registered_model_count": len(registered_models),
    }

    monkeypatch.setattr(
        readiness_module,
        "collect_contract_evidence",
        lambda: contract,
    )
    monkeypatch.setattr(
        readiness_module,
        "collect_static_evidence",
        lambda: static,
    )
    monkeypatch.setattr(
        readiness_module,
        "collect_django_evidence",
        lambda _settings_module: django_evidence,
    )

    result = readiness_module.audit_readiness()
    mapping = result["evidence"]["implementation_mapping"]

    assert mapping["approved_runtime_support_model_tables"] == (
        runtime_tables
    )
    assert mapping["approved_runtime_support_migration_tables"] == (
        runtime_tables
    )
    assert mapping["unknown_model_tables"] == [unknown_table]
    assert mapping["unknown_migration_tables"] == [unknown_table]
    assert result["status"] == "NOT_READY"
    assert result["blockers"] == [
        "MODEL_TABLES_OUTSIDE_CONTRACT",
        "MIGRATION_TABLES_OUTSIDE_CONTRACT",
    ]


def test_repository_audit_reports_ready_when_all_32_layers_match(
    readiness_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
):
    for key in readiness_module.REQUIRED_POSTGRES_ENV_KEYS:
        monkeypatch.setenv(key, "readiness-test-value")

    result = readiness_module.audit_readiness()
    mapping = result["evidence"]["implementation_mapping"]
    summary = mapping["summary"]

    assert result["status"] == "READY"
    assert result["scope"] == "T005_DJANGO_MODEL_MIGRATION_MAPPING"
    assert summary == {
        "contract_table_count": 32,
        "declared_contract_model_count": 32,
        "registered_contract_model_count": 32,
        "migration_contract_table_count": 32,
        "fully_implemented_contract_table_count": 32,
    }
    assert len(mapping["implemented_tables"]) == 32
    assert {
        item["status"] for item in mapping["tables"]
    } == {"IMPLEMENTED"}
    assert mapping["missing_model_tables"] == []
    assert mapping["unregistered_model_tables"] == []
    assert mapping["missing_migration_tables"] == []
    runtime_tables = sorted(
        readiness_module.APPROVED_RUNTIME_SUPPORT_TABLES
    )
    assert mapping["approved_runtime_support_model_tables"] == (
        runtime_tables
    )
    assert mapping["approved_runtime_support_migration_tables"] == (
        runtime_tables
    )
    assert mapping["unknown_model_tables"] == []
    assert mapping["unknown_migration_tables"] == []
    approved_evidence = {
        item["table"]: item
        for item in result["evidence"][
            "approved_runtime_support_tables"
        ]
    }
    assert set(approved_evidence) == set(runtime_tables)
    for table_name, reason in (
        readiness_module.APPROVED_RUNTIME_SUPPORT_TABLES.items()
    ):
        assert approved_evidence[table_name] == {
            "table": table_name,
            "reason": reason,
            "model_present": True,
            "migration_present": True,
        }
    assert result["evidence"]["contract"]["contract_status"] == (
        "OWNER_BASELINE"
    )
    assert result["evidence"]["contract"]["contract_confirmation_status"] == (
        "CONFIRMED"
    )
    assert result["evidence"]["contract"]["completion_review_status"] == (
        "PENDING"
    )
    assert result["blockers"] == []


def test_postgresql_environment_requires_nonblank_values(
    readiness_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
):
    for key in readiness_module.REQUIRED_POSTGRES_ENV_KEYS:
        monkeypatch.setenv(key, "   ")

    evidence = readiness_module.collect_static_evidence()

    assert evidence["postgres_env_keys_present"] == []
    assert evidence["postgres_env_complete"] is False
