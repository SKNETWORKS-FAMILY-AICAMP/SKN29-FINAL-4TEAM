"""T-022 문의 Runtime 착수 조건을 현재 저장소 증거로 감사한다."""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]
INQUIRIES_DIR = BACKEND_DIR / "apps" / "inquiries"
INQUIRY_CONTRACT = (
    REPOSITORY_ROOT / "contracts" / "api" / "paths" / "inquiries.yaml"
)
QUESTIONNAIRE_REQUEST_SCHEMA = (
    REPOSITORY_ROOT
    / "contracts"
    / "api"
    / "components"
    / "schemas"
    / "inquiry"
    / "InquiryQuestionnaireRequest.yaml"
)
SETTINGS_PATH = BACKEND_DIR / "config" / "settings" / "base.py"
API_URLS_PATH = BACKEND_DIR / "config" / "api_urls.py"
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
POSTGRESQL_NOT_RUN = {
    "connection_status": "NOT_RUN",
    "makemigrations_status": "NOT_RUN",
    "migration_status": "NOT_RUN",
}
TEAM_REVIEW_APPROVAL_STATUSES = {
    "APPROVED",
    "TEAM_APPROVED",
    "ACCEPTED",
}
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
CONFIRMED_CONTRACT_STATUSES = {"CONFIRMED"}
RUNTIME_FILES = (
    INQUIRIES_DIR / "models" / "inquiry.py",
    INQUIRIES_DIR / "models" / "symptom_entry.py",
    INQUIRIES_DIR / "models" / "followup_answer.py",
    INQUIRIES_DIR / "repositories" / "inquiry_repository.py",
    INQUIRIES_DIR / "services" / "inquiry_service.py",
    INQUIRIES_DIR / "services" / "inquiry_transition_service.py",
    INQUIRIES_DIR / "api" / "serializers" / "create_inquiry.py",
    INQUIRIES_DIR / "api" / "serializers" / "symptom_submission.py",
    INQUIRIES_DIR / "api" / "views.py",
    INQUIRIES_DIR / "api" / "urls.py",
    INQUIRIES_DIR / "permissions.py",
)


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


def inspect_api_contract(path: Path) -> dict[str, Any]:
    empty_result = {
        "defined": False,
        "confirmed": False,
        "operation_statuses": [],
        "operations": [],
    }
    if not path.is_file():
        return empty_result
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return empty_result
    if not isinstance(document, dict):
        return empty_result

    operations = []
    for contract_path, path_item in document.items():
        if (
            not isinstance(contract_path, str)
            or not contract_path.startswith("/")
            or not isinstance(path_item, dict)
        ):
            continue
        for method, operation in path_item.items():
            normalized_method = str(method).lower()
            if (
                normalized_method not in HTTP_METHODS
                or not isinstance(operation, dict)
                or not operation.get("responses")
            ):
                continue
            operations.append(
                {
                    "path": contract_path,
                    "method": normalized_method,
                    "status": operation.get("x-contract-status"),
                }
            )

    statuses = [operation["status"] for operation in operations]
    return {
        "defined": bool(operations),
        "confirmed": bool(operations)
        and all(
            status in CONFIRMED_CONTRACT_STATUSES
            for status in statuses
        ),
        "operation_statuses": statuses,
        "operations": operations,
    }


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return {}
    return document if isinstance(document, dict) else {}


def path_parameter_schema(
    path_item: dict[str, Any],
    parameter_name: str,
) -> dict[str, Any]:
    parameters = path_item.get("parameters", [])
    if not isinstance(parameters, list):
        return {}
    for parameter in parameters:
        if (
            isinstance(parameter, dict)
            and parameter.get("name") == parameter_name
            and parameter.get("in") == "path"
            and isinstance(parameter.get("schema"), dict)
        ):
            return parameter["schema"]
    return {}


def operation_declares_idempotency_key(
    path_item: dict[str, Any],
    method: str,
) -> bool:
    operation = path_item.get(method, {})
    if not isinstance(operation, dict):
        return False
    parameters = [
        *(path_item.get("parameters", []) or []),
        *(operation.get("parameters", []) or []),
    ]
    return any(
        isinstance(parameter, dict)
        and isinstance(parameter.get("$ref"), str)
        and parameter["$ref"].endswith("/IdempotencyKey.yaml")
        for parameter in parameters
    )


def schema_branch_is_typed(branch: Any) -> bool:
    if not isinstance(branch, dict) or not branch:
        return False
    if isinstance(branch.get("$ref"), str):
        return True
    if branch.get("type") == "array":
        return schema_branch_is_typed(branch.get("items"))
    if branch.get("type") == "object":
        properties = branch.get("properties")
        return (
            branch.get("additionalProperties") is False
            and isinstance(properties, dict)
            and bool(properties)
        )
    alternatives = branch.get("oneOf") or branch.get("anyOf")
    return (
        isinstance(alternatives, list)
        and bool(alternatives)
        and all(schema_branch_is_typed(item) for item in alternatives)
    )


def inspect_deferred_runtime_contracts() -> dict[str, Any]:
    """T-022 공개 쓰기 Runtime 착수 전 미확정 계약을 fail-closed로 감사한다."""

    paths = load_yaml_mapping(INQUIRY_CONTRACT)
    questionnaire_schema = load_yaml_mapping(QUESTIONNAIRE_REQUEST_SCHEMA)
    questionnaire_path = paths.get("/inquiries/{id}/questionnaire", {})
    action_results_path = paths.get("/inquiries/{id}/action-results", {})
    if not isinstance(questionnaire_path, dict):
        questionnaire_path = {}
    if not isinstance(action_results_path, dict):
        action_results_path = {}

    questionnaire_id_schema = path_parameter_schema(
        questionnaire_path,
        "id",
    )
    action_results_id_schema = path_parameter_schema(
        action_results_path,
        "id",
    )
    questionnaire_properties = questionnaire_schema.get("properties", {})
    answers_schema = (
        questionnaire_properties.get("answers", {})
        if isinstance(questionnaire_properties, dict)
        else {}
    )

    operations = {
        "accumulateInquiryQuestionnaire": {
            "path_id_uuid": (
                questionnaire_id_schema.get("type") == "string"
                and questionnaire_id_schema.get("format") == "uuid"
            ),
            "idempotency_key_declared": (
                operation_declares_idempotency_key(
                    questionnaire_path,
                    "patch",
                )
            ),
            "answers_typed": schema_branch_is_typed(answers_schema),
        },
        "createInquiryActionResult": {
            "path_id_uuid": (
                action_results_id_schema.get("type") == "string"
                and action_results_id_schema.get("format") == "uuid"
            ),
            "idempotency_key_declared": (
                operation_declares_idempotency_key(
                    action_results_path,
                    "post",
                )
            ),
        },
    }
    blockers = []
    if not operations["accumulateInquiryQuestionnaire"]["path_id_uuid"]:
        blockers.append("QUESTIONNAIRE_PATH_ID_NOT_UUID")
    if not operations["accumulateInquiryQuestionnaire"][
        "idempotency_key_declared"
    ]:
        blockers.append("QUESTIONNAIRE_IDEMPOTENCY_KEY_UNDECLARED")
    if not operations["accumulateInquiryQuestionnaire"]["answers_typed"]:
        blockers.append("QUESTIONNAIRE_ANSWERS_UNTYPED")
    if not operations["createInquiryActionResult"]["path_id_uuid"]:
        blockers.append("ACTION_RESULTS_PATH_ID_NOT_UUID")
    if not operations["createInquiryActionResult"][
        "idempotency_key_declared"
    ]:
        blockers.append("ACTION_RESULTS_IDEMPOTENCY_KEY_UNDECLARED")

    return {
        "ready": not blockers,
        "operations": operations,
        "blockers": blockers,
        "scope": "OPENAPI_ONLY_RUNTIME_START",
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
            BACKEND_DIR / "tests" / "unit" / "inquiries"
        ).glob("test_*.py"),
        *(BACKEND_DIR / "tests" / "api").glob("*inquir*.py"),
    }
    return sorted(
        path
        for path in candidates
        if path.name != "test_t022_readiness.py"
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
    django_env = os.environ.copy()
    django_env["DJANGO_SETTINGS_MODULE"] = "config.settings.local"
    connection = subprocess.run(
        [sys.executable, str(POSTGRESQL_CHECK_PATH)],
        cwd=REPOSITORY_ROOT,
        env=django_env,
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
    makemigrations = subprocess.run(
        [
            sys.executable,
            str(MANAGE_PATH),
            "makemigrations",
            "--check",
            "--dry-run",
            "--settings=config.settings.local",
        ],
        cwd=BACKEND_DIR,
        env=django_env,
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
            "--settings=config.settings.local",
        ],
        cwd=BACKEND_DIR,
        env=django_env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return {
        "connection_status": "CONNECTED",
        "makemigrations_status": (
            "PASSED"
            if makemigrations.returncode == 0
            else "FAILED"
        ),
        "migration_status": (
            "PASSED" if migration.returncode == 0 else "FAILED"
        ),
    }


def completion_evidence_gates(
    completion_evidence: dict[str, Any] | None,
) -> dict[str, bool]:
    evidence = (
        completion_evidence
        if isinstance(completion_evidence, dict)
        else {}
    )
    team_review = evidence.get("team_review")
    if not isinstance(team_review, dict):
        return {"team_reviewed": False}

    status = team_review.get("status")
    reviewer = team_review.get("reviewer")
    recorded_at = team_review.get("recorded_at")
    return {
        "team_reviewed": (
            isinstance(status, str)
            and status.strip() in TEAM_REVIEW_APPROVAL_STATUSES
            and isinstance(reviewer, str)
            and bool(reviewer.strip())
            and reviewer.strip() != "최지용"
            and isinstance(recorded_at, str)
            and bool(recorded_at.strip())
        )
    }


def audit_readiness(
    environ=None,
    *,
    runtime_test_exit_code: int | None = None,
    postgresql_verification: dict[str, str] | None = None,
    completion_evidence: dict[str, Any] | None = None,
) -> dict:
    source = os.environ if environ is None else environ
    raw_postgresql_verification = (
        postgresql_verification
        if isinstance(postgresql_verification, dict)
        else {}
    )
    postgresql_verification = {
        key: raw_postgresql_verification.get(key, default)
        for key, default in POSTGRESQL_NOT_RUN.items()
    }
    runtime_statements = {
        str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/"):
        substantive_statement_count(path)
        for path in RUNTIME_FILES
    }
    model_count = sum(
        model_class_count(path)
        for path in (INQUIRIES_DIR / "models").glob("*.py")
    )
    migration_count = substantive_migration_count(
        INQUIRIES_DIR / "migrations"
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
    api_contract = inspect_api_contract(INQUIRY_CONTRACT)
    deferred_runtime_contracts = inspect_deferred_runtime_contracts()
    evidence = {
        "runtime_statements": runtime_statements,
        "runtime_implemented_file_count": sum(
            count > 0 for count in runtime_statements.values()
        ),
        "model_class_count": model_count,
        "substantive_migration_count": migration_count,
        "source_file_issues": python_file_issues(RUNTIME_FILES),
        "app_registered": (
            "apps.inquiries.apps.InquiriesConfig" in settings_text
        ),
        "routes_registered": (
            "apps.inquiries.api.urls" in included_modules(API_URLS_PATH)
        ),
        "api_contract_defined": api_contract["defined"],
        "api_contract_confirmed": api_contract["confirmed"],
        "api_contract_operation_statuses": api_contract[
            "operation_statuses"
        ],
        "api_contract_operations": api_contract["operations"],
        "api_contract_decision": (
            "CONFIRMED"
            if api_contract["confirmed"]
            else "DEFINED_NOT_CONFIRMED"
            if api_contract["defined"]
            else "CONTRACT_NOT_DEFINED"
        ),
        "deferred_runtime_contracts": deferred_runtime_contracts,
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
        "structure_baseline": "PROJECT_DIRECTORY_STRUCTURE",
        "structure_status": "BASELINE_APPLIED",
    }
    owner_blockers = []
    if evidence["runtime_implemented_file_count"] != len(RUNTIME_FILES):
        owner_blockers.append("INQUIRY_RUNTIME_INCOMPLETE")
    if model_count == 0:
        owner_blockers.append("INQUIRY_MODELS_MISSING")
    if migration_count == 0:
        owner_blockers.append("INQUIRY_MIGRATIONS_MISSING")
    if not evidence["app_registered"]:
        owner_blockers.append("INQUIRIES_APP_NOT_REGISTERED")
    if not evidence["routes_registered"]:
        owner_blockers.append("INQUIRY_ROUTES_NOT_REGISTERED")
    if not api_contract["defined"]:
        owner_blockers.append("INQUIRY_API_CONTRACT_EMPTY")
    if test_count == 0:
        owner_blockers.append("INQUIRY_RUNTIME_TESTS_MISSING")
    elif runtime_test_exit_code is None:
        owner_blockers.append("INQUIRY_RUNTIME_TESTS_NOT_EXECUTED")
    elif runtime_test_exit_code != 0:
        owner_blockers.append("INQUIRY_RUNTIME_TESTS_FAILED")
    if missing_postgres_keys:
        owner_blockers.append("POSTGRESQL_NOT_CONFIGURED")
    else:
        if (
            postgresql_verification.get("connection_status")
            != "CONNECTED"
        ):
            owner_blockers.append("POSTGRESQL_NOT_VERIFIED")
        if (
            postgresql_verification.get("makemigrations_status")
            != "PASSED"
        ):
            owner_blockers.append(
                "POSTGRESQL_MAKEMIGRATIONS_NOT_VERIFIED"
            )
        if postgresql_verification.get("migration_status") != "PASSED":
            owner_blockers.append(
                "POSTGRESQL_MIGRATION_NOT_VERIFIED"
            )

    review_gates = completion_evidence_gates(completion_evidence)
    completion_gates = {
        "owner_implementation_ready": not owner_blockers,
        "team_reviewed": review_gates["team_reviewed"],
    }
    completion_blockers = (
        [] if completion_gates["team_reviewed"] else ["TEAM_REVIEWED"]
    )
    if owner_blockers:
        status = "PARTIAL"
    elif completion_blockers:
        status = "OWNER_IMPLEMENTATION_READY"
    else:
        status = "READY"
    return {
        "status": status,
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
        "--require-deferred-runtime-contracts",
        action="store_true",
        help=(
            "OPENAPI_ONLY T-022 쓰기 Runtime의 계약 공백이 모두 해소된 "
            "경우에만 성공"
        ),
    )
    parser.add_argument(
        "--completion-evidence",
        type=Path,
        help="팀 검토 완료 증거 JSON 경로",
    )
    arguments = parser.parse_args()
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    from config.env import load_backend_env

    load_backend_env()
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
    if (
        arguments.require_deferred_runtime_contracts
        and not result["evidence"]["deferred_runtime_contracts"]["ready"]
    ):
        return 3
    if arguments.require_ready and result["status"] != "READY":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
