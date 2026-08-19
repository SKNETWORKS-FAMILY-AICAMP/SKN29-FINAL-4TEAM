"""T-005 계약 테이블과 Django 구현의 대응 상태를 사실 기반으로 감사한다."""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPOSITORY_ROOT / "backend"
BACKEND_APPS_DIR = BACKEND_DIR / "apps"
COMPOSE_PATH = REPOSITORY_ROOT / "docker-compose.yml"
ARTIFACT_DIR = REPOSITORY_ROOT / "docs" / "database" / "t-005"
MANIFEST_PATH = ARTIFACT_DIR / "manifest.json"
SCHEMA_PATH = ARTIFACT_DIR / "watercare_schema_v3.json"
PHYSICAL_CONTRACT_PATH = ARTIFACT_DIR / "t005_physical_contract_v1.3.json"
REQUIRED_POSTGRES_ENV_KEYS = {
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
}
APPROVED_RUNTIME_SUPPORT_TABLES = {
    "knowledge_ai_chunk_crosswalk": (
        "Verified one-to-one AI canonical chunk to Backend evidence UUID "
        "mapping; runtime AI evidence support outside the immutable "
        "32-table domain contract."
    ),
    "knowledge_ai_chunk_crosswalk_page": (
        "Reviewed multi-page provenance for AI canonical chunk mappings; "
        "runtime AI evidence support outside the immutable 32-table domain "
        "contract."
    ),
    "accounts_account_audit_event": (
        "Append-only synthetic-account lifecycle audit ledger for T-017C; "
        "runtime security support outside the immutable 32-table domain contract."
    ),
    "accounts_account_lifecycle_lock": (
        "Singleton lock serializing last-account-administrator checks for "
        "T-017C; runtime security support outside the immutable 32-table "
        "domain contract."
    ),
    "audit_event": (
        "Append-only workflow audit ledger; runtime audit support outside "
        "the immutable 32-table domain contract."
    ),
    "operations_synthetic_import_batch": (
        "Synthetic importer execution and provenance ledger; operational "
        "import support outside the immutable 32-table domain contract."
    ),
    "operations_synthetic_import_item": (
        "Synthetic importer per-item outcome and provenance ledger; "
        "operational import support outside the immutable 32-table domain "
        "contract."
    ),
    "operations_staff_directory_entry": (
        "Consultant dashboard staff directory projection; operational "
        "read-model support outside the immutable 32-table domain contract."
    ),
    "operations_dashboard_notice": (
        "Consultant dashboard notice projection; operational read-model "
        "support outside the immutable 32-table domain contract."
    ),
    "operations_inquiry_dashboard_profile": (
        "Consultant inquiry dashboard presentation profile; operational "
        "read-model support outside the immutable 32-table domain contract."
    ),
    "workflow_idempotency_record": (
        "HTTP replay and payload-conflict request ledger defined by ADR "
        "0011; runtime idempotency support outside the immutable 32-table "
        "domain contract."
    ),
    "support_followup_answer": (
        "Customer follow-up answer ledger separated from AI question "
        "metadata for SUBMIT_ANSWERS runtime; support storage outside the "
        "immutable 32-table domain contract."
    ),
}


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _is_model_base(base: ast.expr) -> bool:
    return (
        isinstance(base, ast.Attribute)
        and base.attr == "Model"
    ) or (
        isinstance(base, ast.Name)
        and base.id.endswith("Model")
    )


def _constant_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _keyword_value(call: ast.Call, name: str) -> ast.AST | None:
    return next(
        (
            keyword.value
            for keyword in call.keywords
            if keyword.arg == name
        ),
        None,
    )


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


def _meta_db_table(class_node: ast.ClassDef) -> str | None:
    for node in class_node.body:
        if not isinstance(node, ast.ClassDef) or node.name != "Meta":
            continue
        for statement in node.body:
            if isinstance(statement, ast.Assign):
                if not any(
                    isinstance(target, ast.Name)
                    and target.id == "db_table"
                    for target in statement.targets
                ):
                    continue
                return _constant_string(statement.value)
            if (
                isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and statement.target.id == "db_table"
            ):
                return _constant_string(statement.value)
    return None


def collect_model_declarations(path: Path) -> list[dict[str, Any]]:
    """모델 모듈에서 실제 Model 클래스와 명시적 ``db_table``을 수집한다."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    declarations = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(_is_model_base(base) for base in node.bases):
            continue
        declarations.append(
            {
                "class_name": node.name,
                "db_table": _meta_db_table(node),
                "module_path": _relative_path(path),
            }
        )
    return declarations


def count_model_classes(path: Path) -> int:
    """기존 호출자 호환을 위해 실제 모델 클래스 개수를 반환한다."""

    return len(collect_model_declarations(path))


def _migration_options_db_table(call: ast.Call) -> str | None:
    options_node = _keyword_value(call, "options")
    if not isinstance(options_node, ast.Dict):
        return None
    for key, value in zip(options_node.keys, options_node.values):
        if _constant_string(key) == "db_table":
            return _constant_string(value)
    return None


def collect_migration_declarations(
    migration_files: Iterable[Path],
) -> list[dict[str, Any]]:
    """Migration 연산으로 생성되는 최종 모델 테이블 선언을 정적으로 수집한다."""

    models: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted(migration_files):
        app_label = path.parent.parent.name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = sorted(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and _call_name(node)
                in {
                    "CreateModel",
                    "AlterModelTable",
                    "DeleteModel",
                    "RenameModel",
                }
            ),
            key=lambda node: node.lineno,
        )
        for call in calls:
            operation = _call_name(call)
            if operation == "CreateModel":
                model_name = _constant_string(_keyword_value(call, "name"))
                if not model_name:
                    continue
                db_table = _migration_options_db_table(call)
                explicit_db_table = db_table is not None
                if db_table is None:
                    db_table = f"{app_label}_{model_name.lower()}"
                models[(app_label, model_name.lower())] = {
                    "app_label": app_label,
                    "model_name": model_name,
                    "db_table": db_table,
                    "explicit_db_table": explicit_db_table,
                    "migration_path": _relative_path(path),
                }
                continue

            name = _constant_string(_keyword_value(call, "name"))
            if not name:
                continue
            key = (app_label, name.lower())
            if operation == "DeleteModel":
                models.pop(key, None)
            elif operation == "AlterModelTable":
                table = _constant_string(_keyword_value(call, "table"))
                if key in models and table:
                    models[key]["db_table"] = table
                    models[key]["explicit_db_table"] = True
                    models[key]["migration_path"] = _relative_path(path)
            elif operation == "RenameModel":
                new_name = _constant_string(
                    _keyword_value(call, "new_name")
                )
                record = models.pop(key, None)
                if record is None or not new_name:
                    continue
                if not record["explicit_db_table"]:
                    record["db_table"] = (
                        f"{app_label}_{new_name.lower()}"
                    )
                record["model_name"] = new_name
                record["migration_path"] = _relative_path(path)
                models[(app_label, new_name.lower())] = record
    return sorted(
        models.values(),
        key=lambda item: (
            item["db_table"],
            item["app_label"],
            item["model_name"],
        ),
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"JSON object가 필요합니다: {_relative_path(path)}")
    return document


def collect_contract_evidence() -> dict[str, Any]:
    manifest = _read_json_object(MANIFEST_PATH)
    schema = _read_json_object(SCHEMA_PATH)
    physical_contract = _read_json_object(PHYSICAL_CONTRACT_PATH)
    tables = schema.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("watercare_schema_v3.json의 tables가 object가 아닙니다.")
    expected_count = manifest.get("expected_counts", {}).get("tables")
    inherits = physical_contract.get("inherits", {})
    if not isinstance(inherits, dict):
        inherits = {}
    return {
        "manifest_path": _relative_path(MANIFEST_PATH),
        "schema_path": _relative_path(SCHEMA_PATH),
        "physical_contract_path": _relative_path(PHYSICAL_CONTRACT_PATH),
        "manifest_expected_table_count": expected_count,
        "contract_table_count": len(tables),
        "contract_status": physical_contract.get("status"),
        "contract_confirmation_status": physical_contract.get(
            "confirmation_status"
        ),
        "completion_review_status": physical_contract.get(
            "completion_review_status"
        ),
        "contract_snapshot": inherits.get("snapshot"),
        "contract_snapshot_immutable": (
            inherits.get("immutable_snapshot") is True
        ),
        "tables": tables,
    }


def _app_model_modules(app_directories: Iterable[Path]) -> list[Path]:
    modules: set[Path] = set()
    for app_dir in app_directories:
        models_module = app_dir / "models.py"
        if models_module.is_file():
            modules.add(models_module)
        models_dir = app_dir / "models"
        if models_dir.is_dir():
            modules.update(
                path
                for path in models_dir.rglob("*.py")
                if path.name != "__init__.py"
            )
    return sorted(modules)


def collect_static_evidence() -> dict[str, Any]:
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    from config.env import load_backend_env

    load_backend_env()
    app_directories = sorted(
        path
        for path in BACKEND_APPS_DIR.iterdir()
        if path.is_dir() and (path / "apps.py").is_file()
    )
    model_modules = _app_model_modules(app_directories)
    migration_files = sorted(
        path
        for app_dir in app_directories
        for path in (app_dir / "migrations").glob("[0-9][0-9][0-9][0-9]_*.py")
    )
    model_declarations = [
        declaration
        for path in model_modules
        for declaration in collect_model_declarations(path)
    ]
    migration_declarations = collect_migration_declarations(migration_files)
    model_modules_with_classes = {
        declaration["module_path"]
        for declaration in model_declarations
    }
    placeholder_model_modules = sorted(
        _relative_path(path)
        for path in model_modules
        if _relative_path(path) not in model_modules_with_classes
    )
    postgres_env_keys_present = sorted(
        key
        for key in REQUIRED_POSTGRES_ENV_KEYS
        if (os.getenv(key) or "").strip()
    )

    return {
        "app_skeleton_count": len(app_directories),
        "model_module_count": len(model_modules),
        "model_class_count": len(model_declarations),
        "model_declarations": model_declarations,
        "placeholder_model_modules": placeholder_model_modules,
        "numbered_migration_count": len(migration_files),
        "migration_declarations": migration_declarations,
        "docker_compose_configured": (
            COMPOSE_PATH.is_file() and COMPOSE_PATH.stat().st_size > 0
        ),
        "postgres_env_keys_present": postgres_env_keys_present,
        "postgres_env_complete": (
            set(postgres_env_keys_present) == REQUIRED_POSTGRES_ENV_KEYS
        ),
    }


def collect_django_evidence(
    settings_module: str,
) -> dict[str, Any]:
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    os.environ["DJANGO_SETTINGS_MODULE"] = settings_module

    import django
    from django.apps import apps

    django.setup()
    local_app_configs = [
        app_config
        for app_config in apps.get_app_configs()
        if Path(app_config.path).is_relative_to(BACKEND_APPS_DIR)
    ]
    registered_models = sorted(
        (
            {
                "label": model._meta.label,
                "db_table": model._meta.db_table,
                "module": model.__module__,
            }
            for app_config in local_app_configs
            for model in app_config.get_models()
        ),
        key=lambda item: (item["db_table"], item["label"]),
    )
    return {
        "settings_module": settings_module,
        "registered_local_apps": sorted(
            app_config.name
            for app_config in local_app_configs
        ),
        "registered_model_count": len(registered_models),
        "registered_models": registered_models,
    }


def _group_by_table(
    records: Iterable[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        table = record.get("db_table")
        if not isinstance(table, str) or not table:
            continue
        grouped.setdefault(table, []).append(record)
    return grouped


def build_table_mapping(
    *,
    contract_tables: dict[str, Any],
    model_declarations: Iterable[dict[str, Any]],
    registered_models: Iterable[dict[str, Any]],
    migration_declarations: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """계약 테이블별 Model 선언·등록·Migration 상태를 대조한다."""

    declared_by_table = _group_by_table(model_declarations)
    registered_by_table = _group_by_table(registered_models)
    migrated_by_table = _group_by_table(migration_declarations)
    expected_tables = set(contract_tables)
    table_results = []

    for table_name in sorted(expected_tables):
        table_contract = contract_tables.get(table_name)
        if not isinstance(table_contract, dict):
            table_contract = {}
        declarations = declared_by_table.get(table_name, [])
        registrations = registered_by_table.get(table_name, [])
        migrations = migrated_by_table.get(table_name, [])
        model_declared = bool(declarations)
        model_registered = bool(registrations)
        migration_created = bool(migrations)

        if model_registered and migration_created:
            status = "IMPLEMENTED"
        elif model_declared and not model_registered and migration_created:
            status = "MODEL_NOT_REGISTERED"
        elif model_registered and not migration_created:
            status = "MIGRATION_MISSING"
        elif model_declared and not model_registered:
            status = "MODEL_NOT_REGISTERED_AND_MIGRATION_MISSING"
        elif migration_created:
            status = "MODEL_MISSING"
        else:
            status = "MISSING"

        table_results.append(
            {
                "table": table_name,
                "domain": table_contract.get("domain"),
                "owner": table_contract.get("owner"),
                "status": status,
                "model_declared": model_declared,
                "model_registered": model_registered,
                "migration_created": migration_created,
                "model_classes": sorted(
                    declaration["class_name"]
                    for declaration in declarations
                ),
                "model_modules": sorted(
                    declaration["module_path"]
                    for declaration in declarations
                ),
                "registered_model_labels": sorted(
                    registration["label"]
                    for registration in registrations
                ),
                "migration_files": sorted(
                    {
                        migration["migration_path"]
                        for migration in migrations
                    }
                ),
            }
        )

    declared_tables = set(declared_by_table)
    registered_tables = set(registered_by_table)
    migrated_tables = set(migrated_by_table)
    approved_runtime_tables = set(APPROVED_RUNTIME_SUPPORT_TABLES)
    outside_contract_model_tables = (
        declared_tables | registered_tables
    ) - expected_tables
    outside_contract_migration_tables = (
        migrated_tables - expected_tables
    )
    fully_implemented = {
        item["table"]
        for item in table_results
        if item["status"] == "IMPLEMENTED"
    }
    return {
        "summary": {
            "contract_table_count": len(expected_tables),
            "declared_contract_model_count": len(
                expected_tables & declared_tables
            ),
            "registered_contract_model_count": len(
                expected_tables & registered_tables
            ),
            "migration_contract_table_count": len(
                expected_tables & migrated_tables
            ),
            "fully_implemented_contract_table_count": len(
                fully_implemented
            ),
        },
        "implemented_tables": sorted(fully_implemented),
        "missing_model_tables": sorted(expected_tables - declared_tables),
        "unregistered_model_tables": sorted(
            (expected_tables & declared_tables) - registered_tables
        ),
        "missing_migration_tables": sorted(
            expected_tables - migrated_tables
        ),
        "approved_runtime_support_model_tables": sorted(
            outside_contract_model_tables & approved_runtime_tables
        ),
        "approved_runtime_support_migration_tables": sorted(
            outside_contract_migration_tables & approved_runtime_tables
        ),
        "unknown_model_tables": sorted(
            outside_contract_model_tables - approved_runtime_tables
        ),
        "unknown_migration_tables": sorted(
            outside_contract_migration_tables - approved_runtime_tables
        ),
        "tables": table_results,
    }


def audit_readiness(
    settings_module: str = "config.settings.test",
) -> dict[str, Any]:
    contract = collect_contract_evidence()
    static = collect_static_evidence()
    django_evidence = collect_django_evidence(settings_module)
    mapping = build_table_mapping(
        contract_tables=contract["tables"],
        model_declarations=static["model_declarations"],
        registered_models=django_evidence["registered_models"],
        migration_declarations=static["migration_declarations"],
    )
    contract_public = {
        key: value
        for key, value in contract.items()
        if key != "tables"
    }
    approved_runtime_support_tables = [
        {
            "table": table_name,
            "reason": reason,
            "model_present": (
                table_name
                in mapping["approved_runtime_support_model_tables"]
            ),
            "migration_present": (
                table_name
                in mapping["approved_runtime_support_migration_tables"]
            ),
        }
        for table_name, reason in sorted(
            APPROVED_RUNTIME_SUPPORT_TABLES.items()
        )
    ]
    evidence = {
        **static,
        **django_evidence,
        "contract": contract_public,
        "approved_runtime_support_tables": (
            approved_runtime_support_tables
        ),
        "implementation_mapping": mapping,
    }
    blockers = []

    if (
        contract["manifest_expected_table_count"]
        != contract["contract_table_count"]
    ):
        blockers.append("CONTRACT_TABLE_COUNT_MISMATCH")
    if (
        contract["contract_snapshot"] != SCHEMA_PATH.name
        or not contract["contract_snapshot_immutable"]
    ):
        blockers.append("PHYSICAL_CONTRACT_SNAPSHOT_MISMATCH")
    if contract["contract_status"] != "OWNER_BASELINE":
        blockers.append("PHYSICAL_CONTRACT_OWNER_BASELINE_INVALID")
    if contract["contract_confirmation_status"] != "CONFIRMED":
        blockers.append("PHYSICAL_CONTRACT_NOT_CONFIRMED")
    if mapping["missing_model_tables"]:
        blockers.append("CONTRACT_MODEL_DECLARATIONS_INCOMPLETE")
    if mapping["unregistered_model_tables"]:
        blockers.append("CONTRACT_MODELS_NOT_REGISTERED")
    if mapping["missing_migration_tables"]:
        blockers.append("CONTRACT_MIGRATIONS_INCOMPLETE")
    if mapping["unknown_model_tables"]:
        blockers.append("MODEL_TABLES_OUTSIDE_CONTRACT")
    if mapping["unknown_migration_tables"]:
        blockers.append("MIGRATION_TABLES_OUTSIDE_CONTRACT")
    if static["model_class_count"] == 0:
        blockers.append("NO_DJANGO_MODEL_CLASSES")
    if static["numbered_migration_count"] == 0:
        blockers.append("NO_NUMBERED_MIGRATIONS")
    if not django_evidence["registered_local_apps"]:
        blockers.append("NO_LOCAL_APPS_REGISTERED")
    if django_evidence["registered_model_count"] == 0:
        blockers.append("NO_MODELS_REGISTERED")
    if not static["docker_compose_configured"]:
        blockers.append("DOCKER_COMPOSE_NOT_CONFIGURED")
    if not static["postgres_env_complete"]:
        blockers.append("POSTGRES_ENV_INCOMPLETE")

    return {
        "status": "READY" if not blockers else "NOT_READY",
        "scope": "T005_DJANGO_MODEL_MIGRATION_MAPPING",
        "evidence": evidence,
        "blockers": blockers,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--settings",
        default="config.settings.test",
        help="준비도 감사에 사용할 Django settings module",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="준비되지 않았으면 exit code 2를 반환한다.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    result = audit_readiness(arguments.settings)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if arguments.require_ready and result["status"] != "READY":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
