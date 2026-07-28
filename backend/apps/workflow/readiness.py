"""T-023 Backend Workflow 구현과 PM 계약 준비도를 분리해 감사한다."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = BACKEND_DIR / "apps" / "workflow"
CONTRACT_DIR = REPOSITORY_ROOT / "contracts" / "state-machine"
SETTINGS_PATH = BACKEND_DIR / "config" / "settings" / "base.py"
API_URLS_PATH = BACKEND_DIR / "config" / "api_urls.py"
WORKFLOW_API_CONTRACT = (
    REPOSITORY_ROOT / "contracts" / "api" / "paths" / "workflow.yaml"
)
WORKFLOW_API_URLS_PATH = WORKFLOW_DIR / "api" / "urls.py"
INQUIRIES_API_URLS_PATH = (
    BACKEND_DIR / "apps" / "inquiries" / "api" / "urls.py"
)
MANAGE_PATH = BACKEND_DIR / "manage.py"
POSTGRESQL_CHECK_PATH = (
    REPOSITORY_ROOT
    / "scripts"
    / "database"
    / "check_postgresql_connection.py"
)
POSTGRES_KEYS = (
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
)
LOCAL_SETTINGS_MODULE = "config.settings.local"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
TEAM_APPROVED_CONTRACT_STATUSES = {
    "TEAM_APPROVED",
    "APPROVED",
    "ACCEPTED",
}
BACKEND_REVIEW_APPROVED_STATUSES = {
    "TEAM_APPROVED",
    "APPROVED",
    "ACCEPTED",
}
RUNTIME_FILES = (
    WORKFLOW_DIR / "contracts" / "state_machine_loader.py",
    WORKFLOW_DIR / "contracts" / "contract_validator.py",
    WORKFLOW_DIR / "engine" / "state_machine.py",
    WORKFLOW_DIR / "engine" / "guard_evaluator.py",
    WORKFLOW_DIR / "engine" / "allowed_action_resolver.py",
    WORKFLOW_DIR / "models" / "transition_history.py",
    WORKFLOW_DIR / "models" / "idempotency_record.py",
    WORKFLOW_DIR / "repositories" / "workflow_repository.py",
    WORKFLOW_DIR / "services" / "idempotency_service.py",
    WORKFLOW_DIR / "services" / "transition_history_service.py",
)


def completion_evidence_gates(evidence: dict | None) -> dict[str, bool]:
    if not isinstance(evidence, dict):
        evidence = {}
    team_review = evidence.get("team_review")
    backend_reviewed = (
        isinstance(team_review, dict)
        and team_review.get("status") in BACKEND_REVIEW_APPROVED_STATUSES
        and isinstance(team_review.get("reviewer"), str)
        and bool(team_review["reviewer"].strip())
        and team_review["reviewer"].strip() != "최지용"
        and isinstance(team_review.get("recorded_at"), str)
        and bool(team_review["recorded_at"].strip())
    )
    return {"backend_reviewed": backend_reviewed}


def readiness_status(
    owner_blockers: list[str],
    completion_blockers: list[str],
) -> str:
    if owner_blockers:
        return "PARTIAL"
    if completion_blockers:
        return "OWNER_IMPLEMENTATION_READY"
    return "READY"


def substantive_statement_count(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
        return 0
    statements = list(tree.body)
    if (
        statements
        and isinstance(statements[0], ast.Expr)
        and isinstance(statements[0].value, ast.Constant)
        and isinstance(statements[0].value.value, str)
    ):
        statements = statements[1:]
    return sum(
        (
            isinstance(
                statement,
                (
                    ast.ClassDef,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            or (
                isinstance(statement, (ast.Assign, ast.AnnAssign))
                and assignment_has_runtime_value(statement)
            )
        )
        for statement in statements
    )


def assignment_has_runtime_value(
    statement: ast.Assign | ast.AnnAssign,
) -> bool:
    value = statement.value
    if value is None:
        return False
    if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
        return bool(value.elts)
    if isinstance(value, ast.Dict):
        return bool(value.keys)
    return isinstance(
        value,
        (
            ast.Call,
            ast.ListComp,
            ast.SetComp,
            ast.DictComp,
            ast.GeneratorExp,
            ast.Lambda,
        ),
    )


def yaml_value(filename: str, key: str):
    path = CONTRACT_DIR / filename
    if not path.is_file():
        return None
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return None
    if not isinstance(document, dict):
        return None
    return document.get(key)


def inspect_state_machine_contract() -> dict:
    """현재 6개 rich-schema 계약을 실제 Runtime 검증기로 감사한다."""

    empty_result = {
        "valid": False,
        "sections": {
            "states": False,
            "events": False,
            "transitions": False,
            "guards": False,
            "allowed_actions": False,
            "role_permissions": False,
        },
        "counts": {
            "states": 0,
            "events": 0,
            "transitions": 0,
            "guards": 0,
            "allowed_actions": 0,
            "role_permissions": 0,
        },
        "statuses": {},
        "team_approved": False,
        "errors": [],
    }

    def load_contract_module(name: str, filename: str):
        path = WORKFLOW_DIR / "contracts" / filename
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    try:
        loader = load_contract_module(
            "workflow_state_machine_loader",
            "state_machine_loader.py",
        )
        validator = load_contract_module(
            "workflow_contract_validator",
            "contract_validator.py",
        )
    except (ImportError, OSError) as exc:
        empty_result["errors"] = [
            f"workflow contract validator import failed: {exc}"
        ]
        return empty_result

    try:
        documents = loader.load_contract_documents(CONTRACT_DIR)
    except loader.StateMachineContractLoadError as exc:
        empty_result["errors"] = [str(exc)]
        return empty_result

    states = documents["states"].get("states")
    events = documents["events"].get("events")
    transitions = documents["transitions"].get("transitions")
    guards = documents["guards"].get("guards")
    action_catalog = documents["allowed_actions"].get("action_catalog")
    state_role_actions = documents["allowed_actions"].get(
        "state_role_actions"
    )
    roles = documents["role_permissions"].get("roles")

    sections = {
        "states": isinstance(states, list) and bool(states),
        "events": isinstance(events, list) and bool(events),
        "transitions": isinstance(transitions, list) and bool(transitions),
        "guards": isinstance(guards, list) and bool(guards),
        "allowed_actions": (
            isinstance(action_catalog, list)
            and bool(action_catalog)
            and isinstance(state_role_actions, dict)
            and bool(state_role_actions)
        ),
        "role_permissions": (
            isinstance(roles, list)
            and bool(roles)
            and any(
                isinstance(role, dict)
                and isinstance(role.get("allowed_events"), list)
                and bool(role["allowed_events"])
                for role in roles
            )
        ),
    }
    counts = {
        "states": len(states) if isinstance(states, list) else 0,
        "events": len(events) if isinstance(events, list) else 0,
        "transitions": (
            len(transitions) if isinstance(transitions, list) else 0
        ),
        "guards": len(guards) if isinstance(guards, list) else 0,
        "allowed_actions": (
            len(action_catalog) if isinstance(action_catalog, list) else 0
        ),
        "role_permissions": len(roles) if isinstance(roles, list) else 0,
    }
    errors = list(validator.collect_contract_errors(documents))
    statuses = {
        name: document.get("contract", {}).get("status")
        for name, document in documents.items()
    }
    return {
        "valid": all(sections.values()) and not errors,
        "sections": sections,
        "counts": counts,
        "statuses": statuses,
        "team_approved": all(
            status in TEAM_APPROVED_CONTRACT_STATUSES
            for status in statuses.values()
        ),
        "errors": errors,
    }


def model_class_count(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
        return 0
    return sum(
        isinstance(node, ast.ClassDef)
        and any(
            (
                isinstance(base, ast.Attribute)
                and base.attr == "Model"
            )
            or (
                isinstance(base, ast.Name)
                and base.id.endswith("Model")
            )
            for base in node.bases
        )
        for node in ast.walk(tree)
    )


def substantive_migration_count(directory: Path) -> int:
    count = 0
    for path in directory.glob("[0-9][0-9][0-9][0-9]_*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeError):
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or node.name != "Migration":
                continue
            operations = next(
                (
                    child.value
                    for child in node.body
                    if isinstance(child, ast.Assign)
                    and any(
                        isinstance(target, ast.Name)
                        and target.id == "operations"
                        for target in child.targets
                    )
                ),
                None,
            )
            if isinstance(operations, (ast.List, ast.Tuple)) and operations.elts:
                count += 1
                break
    return count


def has_http_operation(path: Path) -> bool:
    return inspect_api_contract(path)["defined"]


def inspect_api_contract(path: Path) -> dict:
    if not path.is_file():
        return {
            "defined": False,
            "team_approved": False,
            "operation_statuses": [],
            "paths": [],
        }
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return {
            "defined": False,
            "team_approved": False,
            "operation_statuses": [],
            "paths": [],
        }
    if not isinstance(document, dict):
        return {
            "defined": False,
            "team_approved": False,
            "operation_statuses": [],
            "paths": [],
        }

    operations = []
    for contract_path, path_item in document.items():
        if (
            not isinstance(contract_path, str)
            or not contract_path.startswith("/")
            or not isinstance(path_item, dict)
        ):
            continue
        for method, operation in path_item.items():
            if (
                str(method).lower() not in HTTP_METHODS
                or not isinstance(operation, dict)
                or not operation.get("responses")
            ):
                continue
            operations.append(
                {
                    "path": contract_path,
                    "method": str(method).lower(),
                    "status": operation.get("x-contract-status"),
                }
            )

    statuses = [operation["status"] for operation in operations]
    return {
        "defined": bool(operations),
        "team_approved": bool(operations)
        and all(
            status in TEAM_APPROVED_CONTRACT_STATUSES
            for status in statuses
        ),
        "operation_statuses": statuses,
        "paths": sorted(
            {operation["path"] for operation in operations}
        ),
    }


def included_modules(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
        return set()
    values = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        function_name = (
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr
            if isinstance(node.func, ast.Attribute)
            else None
        )
        first_argument = node.args[0]
        if (
            function_name == "include"
            and isinstance(first_argument, ast.Constant)
            and isinstance(first_argument.value, str)
        ):
            values.add(first_argument.value)
    return values


def _assigned_urlpatterns_values(tree: ast.Module) -> list[ast.AST]:
    values = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue
        if value is not None and any(
            isinstance(target, ast.Name)
            and target.id == "urlpatterns"
            for target in targets
        ):
            values.append(value)
    return values


def meaningful_urlpatterns(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
        return False
    for value in _assigned_urlpatterns_values(tree):
        if any(
            isinstance(node, ast.Call)
            and (
                (
                    isinstance(node.func, ast.Name)
                    and node.func.id in {"path", "re_path"}
                )
                or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"path", "re_path"}
                )
            )
            for node in ast.walk(value)
        ):
            return True
    return False


def urlpatterns_included_modules(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
        return set()

    values = set()
    for assigned_value in _assigned_urlpatterns_values(tree):
        for node in ast.walk(assigned_value):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            function_name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else None
            )
            first_argument = node.args[0]
            if (
                function_name == "include"
                and isinstance(first_argument, ast.Constant)
                and isinstance(first_argument.value, str)
            ):
                values.add(first_argument.value)
    return values


def workflow_routes_registered(contract_paths: list[str]) -> bool:
    root_modules = urlpatterns_included_modules(API_URLS_PATH)
    if (
        "apps.workflow.api.urls" in root_modules
        and meaningful_urlpatterns(WORKFLOW_API_URLS_PATH)
    ):
        return True

    inquiry_scoped_contract = bool(contract_paths) and all(
        path == "/inquiries" or path.startswith("/inquiries/")
        for path in contract_paths
    )
    return (
        inquiry_scoped_contract
        and "apps.inquiries.api.urls" in root_modules
        and meaningful_urlpatterns(INQUIRIES_API_URLS_PATH)
    )


def python_file_issues(paths: tuple[Path, ...]) -> dict[str, str]:
    issues = {}
    for path in paths:
        try:
            key_path = path.relative_to(REPOSITORY_ROOT)
        except ValueError:
            key_path = path
        key = str(key_path).replace("\\", "/")
        if not path.is_file():
            issues[key] = "MISSING"
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeError):
            issues[key] = "MALFORMED"
    return issues


def runtime_test_files() -> list[Path]:
    candidates = {
        *(
            BACKEND_DIR / "tests" / "unit" / "workflow"
        ).glob("test_*.py"),
        *(BACKEND_DIR / "tests" / "api").glob("*workflow*.py"),
        *(BACKEND_DIR / "tests" / "api").glob("*transition*.py"),
        *(BACKEND_DIR / "tests" / "api").glob("*inquiry*.py"),
    }
    return sorted(
        path
        for path in candidates
        if path.name != "test_t023_readiness.py"
    )


def test_function_count(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
        return 0
    return sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
        for node in ast.walk(tree)
    )


def run_runtime_tests(files: list[Path]) -> int | None:
    if not files:
        return None
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *[
                str(path.relative_to(BACKEND_DIR))
                for path in files
            ],
        ],
        cwd=BACKEND_DIR,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.returncode


def verify_postgresql_runtime() -> dict[str, str]:
    command_environment = os.environ.copy()
    command_environment["DJANGO_SETTINGS_MODULE"] = LOCAL_SETTINGS_MODULE
    connection = subprocess.run(
        [sys.executable, str(POSTGRESQL_CHECK_PATH)],
        cwd=REPOSITORY_ROOT,
        env=command_environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if connection.returncode != 0:
        return {
            "connection_status": (
                "NOT_CONFIGURED"
                if connection.returncode == 2
                else "FAILED"
            ),
            "makemigrations_status": "NOT_RUN",
            "migration_status": "NOT_RUN",
        }
    model_migration = subprocess.run(
        [
            sys.executable,
            str(MANAGE_PATH),
            "makemigrations",
            "--check",
            "--dry-run",
            "--noinput",
            f"--settings={LOCAL_SETTINGS_MODULE}",
        ],
        cwd=BACKEND_DIR,
        env=command_environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    migration = subprocess.run(
        [
            sys.executable,
            str(MANAGE_PATH),
            "migrate",
            "--check",
            "--noinput",
            f"--settings={LOCAL_SETTINGS_MODULE}",
        ],
        cwd=BACKEND_DIR,
        env=command_environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return {
        "connection_status": "CONNECTED",
        "makemigrations_status": (
            "PASSED" if model_migration.returncode == 0 else "FAILED"
        ),
        "migration_status": (
            "PASSED" if migration.returncode == 0 else "FAILED"
        ),
    }


def audit_readiness(
    environ=None,
    *,
    runtime_test_exit_code: int | None = None,
    postgresql_verification: dict[str, str] | None = None,
    completion_evidence: dict | None = None,
) -> dict:
    source = os.environ if environ is None else environ
    if not isinstance(postgresql_verification, dict):
        postgresql_verification = {}
    postgresql_verification = {
        "connection_status": postgresql_verification.get(
            "connection_status",
            "NOT_RUN",
        ),
        "makemigrations_status": postgresql_verification.get(
            "makemigrations_status",
            "NOT_RUN",
        ),
        "migration_status": postgresql_verification.get(
            "migration_status",
            "NOT_RUN",
        ),
    }
    runtime_statements = {
        str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/"):
        substantive_statement_count(path)
        for path in RUNTIME_FILES
    }
    contract_inspection = inspect_state_machine_contract()
    contract_evidence = contract_inspection["sections"]
    model_count = sum(
        model_class_count(path)
        for path in (WORKFLOW_DIR / "models").glob("*.py")
    )
    migration_count = substantive_migration_count(
        WORKFLOW_DIR / "migrations"
    )
    settings_text = (
        SETTINGS_PATH.read_text(encoding="utf-8")
        if SETTINGS_PATH.is_file()
        else ""
    )
    missing_postgres_keys = [
        key
        for key in POSTGRES_KEYS
        if not source.get(key, "").strip()
    ]
    tests = runtime_test_files()
    test_count = sum(test_function_count(path) for path in tests)
    api_contract = inspect_api_contract(WORKFLOW_API_CONTRACT)
    root_route_modules = urlpatterns_included_modules(API_URLS_PATH)
    inquiry_scoped_contract = bool(api_contract["paths"]) and all(
        path == "/inquiries" or path.startswith("/inquiries/")
        for path in api_contract["paths"]
    )
    registered_route_modules = []
    if (
        "apps.workflow.api.urls" in root_route_modules
        and meaningful_urlpatterns(WORKFLOW_API_URLS_PATH)
    ):
        registered_route_modules.append("apps.workflow.api.urls")
    if (
        inquiry_scoped_contract
        and "apps.inquiries.api.urls" in root_route_modules
        and meaningful_urlpatterns(INQUIRIES_API_URLS_PATH)
    ):
        registered_route_modules.append("apps.inquiries.api.urls")
    evidence = {
        "contract_owner": "윤승혁(PM)",
        "backend_implementation_owner": "최지용",
        "qa_reviewer": "김은진",
        "contract": contract_evidence,
        "contract_counts": contract_inspection["counts"],
        "contract_statuses": contract_inspection["statuses"],
        "contract_team_approved": contract_inspection["team_approved"],
        "contract_validation_status": (
            "PASSED" if contract_inspection["valid"] else "FAILED"
        ),
        "contract_validation_errors": contract_inspection["errors"],
        "runtime_statements": runtime_statements,
        "runtime_implemented_file_count": sum(
            count > 0 for count in runtime_statements.values()
        ),
        "model_class_count": model_count,
        "substantive_migration_count": migration_count,
        "source_file_issues": python_file_issues(RUNTIME_FILES),
        "app_registered": (
            "apps.workflow.apps.WorkflowConfig" in settings_text
        ),
        "routes_registered": workflow_routes_registered(
            api_contract["paths"]
        ),
        "registered_route_modules": registered_route_modules,
        "api_contract_defined": api_contract["defined"],
        "api_contract_team_approved": api_contract["team_approved"],
        "api_contract_operation_statuses": api_contract[
            "operation_statuses"
        ],
        "api_structure_decision": (
            "TEAM_APPROVED"
            if api_contract["team_approved"]
            else "CONTRACT_REVIEW_PENDING"
            if api_contract["defined"]
            else "STRUCTURE_DECISION_PENDING"
        ),
        "runtime_test_function_count": test_count,
        "runtime_test_execution_status": (
            "NOT_RUN"
            if runtime_test_exit_code is None
            else "PASSED"
            if runtime_test_exit_code == 0
            else "FAILED"
        ),
        "missing_postgresql_keys": missing_postgres_keys,
        "postgresql_verification": postgresql_verification,
    }
    owner_blockers = []
    if not contract_inspection["valid"]:
        owner_blockers.append("PM_STATE_MACHINE_CONTRACT_INCOMPLETE")
    elif not contract_inspection["team_approved"]:
        owner_blockers.append("PM_STATE_MACHINE_CONTRACT_REVIEW_PENDING")
    if evidence["runtime_implemented_file_count"] != len(RUNTIME_FILES):
        owner_blockers.append("WORKFLOW_RUNTIME_INCOMPLETE")
    if model_count == 0:
        owner_blockers.append("WORKFLOW_MODELS_MISSING")
    if migration_count == 0:
        owner_blockers.append("WORKFLOW_MIGRATIONS_MISSING")
    if not evidence["app_registered"]:
        owner_blockers.append("WORKFLOW_APP_NOT_REGISTERED")
    if not evidence["routes_registered"]:
        owner_blockers.append("WORKFLOW_ROUTES_NOT_REGISTERED")
    if not api_contract["defined"]:
        owner_blockers.append("WORKFLOW_API_STRUCTURE_DECISION_PENDING")
    elif not api_contract["team_approved"]:
        owner_blockers.append("WORKFLOW_API_CONTRACT_REVIEW_PENDING")
    if test_count == 0:
        owner_blockers.append("WORKFLOW_RUNTIME_TESTS_MISSING")
    elif runtime_test_exit_code is None:
        owner_blockers.append("WORKFLOW_RUNTIME_TESTS_NOT_EXECUTED")
    elif runtime_test_exit_code != 0:
        owner_blockers.append("WORKFLOW_RUNTIME_TESTS_FAILED")
    if missing_postgres_keys:
        owner_blockers.append("POSTGRESQL_NOT_CONFIGURED")
    elif postgresql_verification.get("connection_status") != "CONNECTED":
        owner_blockers.append("POSTGRESQL_NOT_VERIFIED")
    elif (
        postgresql_verification.get("makemigrations_status")
        != "PASSED"
    ):
        owner_blockers.append("DJANGO_MODEL_MIGRATION_DRIFT")
    elif postgresql_verification.get("migration_status") != "PASSED":
        owner_blockers.append("POSTGRESQL_MIGRATION_NOT_VERIFIED")
    completion_gates = completion_evidence_gates(completion_evidence)
    completion_blockers = [
        gate.upper()
        for gate, complete in completion_gates.items()
        if not complete
    ]
    return {
        "status": readiness_status(
            owner_blockers,
            completion_blockers,
        ),
        "evidence": evidence,
        "completion_gates": completion_gates,
        "completion_evidence_supplied": bool(completion_evidence),
        "owner_blockers": owner_blockers,
        "completion_blockers": completion_blockers,
        "blockers": owner_blockers + completion_blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--run-runtime-tests", action="store_true")
    parser.add_argument("--verify-postgresql", action="store_true")
    parser.add_argument(
        "--completion-evidence",
        type=Path,
        help="작성자 외 Backend 검토 증거 JSON 경로",
    )
    arguments = parser.parse_args()
    completion_evidence = None
    if arguments.completion_evidence is not None:
        try:
            completion_evidence = json.loads(
                arguments.completion_evidence.read_text(encoding="utf-8")
            )
            if not isinstance(completion_evidence, dict):
                raise ValueError("completion evidence must be an object")
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            print(
                json.dumps(
                    {
                        "status": "INVALID_COMPLETION_EVIDENCE",
                        "path": str(arguments.completion_evidence),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    from config.env import load_backend_env

    load_backend_env()
    tests = runtime_test_files()
    result = audit_readiness(
        runtime_test_exit_code=(
            run_runtime_tests(tests)
            if arguments.run_runtime_tests
            else None
        ),
        postgresql_verification=(
            verify_postgresql_runtime()
            if arguments.verify_postgresql
            else None
        ),
        completion_evidence=completion_evidence,
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if arguments.require_ready and result["status"] != "READY":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
