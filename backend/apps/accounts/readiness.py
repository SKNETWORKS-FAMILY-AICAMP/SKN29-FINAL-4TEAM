"""T-017 인증·권한 구현 준비도와 실제 실행 증거를 감사한다."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]
MANAGE_PATH = BACKEND_DIR / "manage.py"
POSTGRESQL_CHECK_PATH = (
    REPOSITORY_ROOT
    / "scripts"
    / "database"
    / "check_postgresql_connection.py"
)
ACCOUNTS_DIR = BACKEND_DIR / "apps" / "accounts"
API_SPEC_PATH = REPOSITORY_ROOT / "docs" / "planning" / "md" / "API명세서.md"
JWT_POLICY_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "adr"
    / "0009-t017-jwt-rbac-owner-baseline.md"
)
ROLE_CONTRACT_PATH = (
    REPOSITORY_ROOT / "contracts" / "codes" / "user-roles.yaml"
)
AUTH_PATH_CONTRACT = (
    REPOSITORY_ROOT / "contracts" / "api" / "paths" / "auth.yaml"
)
AUTH_SCHEMA_DIR = (
    REPOSITORY_ROOT
    / "contracts"
    / "api"
    / "components"
    / "schemas"
    / "auth"
)
ROLE_PERMISSION_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "state-machine"
    / "role-permissions.yaml"
)
SETTINGS_PATH = BACKEND_DIR / "config" / "settings" / "base.py"
API_URLS_PATH = BACKEND_DIR / "config" / "api_urls.py"
AUTH_RUNTIME_FILES = (
    ACCOUNTS_DIR / "models" / "user.py",
    ACCOUNTS_DIR / "models" / "customer_profile.py",
    ACCOUNTS_DIR / "models" / "account_audit_event.py",
    ACCOUNTS_DIR / "models" / "contract_email_contact.py",
    ACCOUNTS_DIR / "models" / "customer_account_link.py",
    ACCOUNTS_DIR / "models" / "p1_auth.py",
    ACCOUNTS_DIR / "repositories" / "account_repository.py",
    ACCOUNTS_DIR / "repositories" / "account_audit_repository.py",
    ACCOUNTS_DIR / "services" / "authentication_service.py",
    ACCOUNTS_DIR / "services" / "account_lifecycle_service.py",
    ACCOUNTS_DIR / "services" / "account_service.py",
    ACCOUNTS_DIR / "services" / "contract_email_protection.py",
    ACCOUNTS_DIR / "services" / "p1_auth_crypto.py",
    ACCOUNTS_DIR / "services" / "p1_auth_email_outbox_service.py",
    ACCOUNTS_DIR / "services" / "p1_auth_email_service.py",
    ACCOUNTS_DIR / "services" / "p1_auth_otp_cipher.py",
    ACCOUNTS_DIR / "services" / "p1_auth_target_service.py",
    ACCOUNTS_DIR / "services" / "p1_auth_service.py",
    ACCOUNTS_DIR / "account_admin_policy.py",
    ACCOUNTS_DIR / "account_admin_guards.py",
    ACCOUNTS_DIR / "api" / "serializers.py",
    ACCOUNTS_DIR / "api" / "views.py",
    ACCOUNTS_DIR / "api" / "urls.py",
    ACCOUNTS_DIR
    / "management"
    / "commands"
    / "process_p1_auth_email_outbox.py",
    ACCOUNTS_DIR / "permissions.py",
    BACKEND_DIR / "common" / "authentication" / "claims.py",
    BACKEND_DIR
    / "common"
    / "authentication"
    / "jwt_authentication.py",
)


def _yaml_list_values(text: str, key: str) -> set[str]:
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        return set()
    if not isinstance(document, dict):
        return set()
    values = document.get(key)
    if not isinstance(values, list):
        return set()
    return {
        value
        for value in values
        if isinstance(value, str)
        and re.fullmatch(r"[A-Z][A-Z0-9_]*", value)
    }


def _yaml_mapping_has_entries(text: str, key: str) -> bool:
    """YAML 최상위 mapping의 ``key``가 비어 있지 않은 mapping인지 본다."""

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        return False
    if not isinstance(document, dict):
        return False
    value = document.get(key)
    return isinstance(value, dict) and bool(value)


def _yaml_nested_mapping_has_nonempty_values(text: str, key: str) -> bool:
    """구 mapping 또는 rich-schema 역할 목록에 권한이 있는지 본다."""

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        return False
    if not isinstance(document, dict):
        return False
    values = document.get(key)
    if isinstance(values, dict):
        return any(
            isinstance(value, list) and bool(value)
            for value in values.values()
        )
    if isinstance(values, list):
        return any(
            isinstance(role, dict)
            and isinstance(role.get("allowed_events"), list)
            and bool(role["allowed_events"])
            for role in values
        )
    return False


def _yaml_has_http_operation(text: str) -> bool:
    """응답 계약이 있는 HTTP operation이 하나 이상인지 확인한다."""

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        return False
    if not isinstance(document, dict):
        return False
    methods = {"get", "post", "put", "patch", "delete", "options", "head"}
    path_items = [document]
    path_items.extend(
        value
        for key, value in document.items()
        if str(key).startswith("/") and isinstance(value, dict)
    )
    for path_item in path_items:
        for method, operation in path_item.items():
            if (
                str(method).lower() not in methods
                or not isinstance(operation, dict)
            ):
                continue
            responses = operation.get("responses")
            if isinstance(responses, dict) and responses:
                return True
    return False


def _substantive_statement_count(path: Path) -> int:
    if not path.is_file():
        return 0
    tree = ast.parse(path.read_text(encoding="utf-8"))
    statements = list(tree.body)
    if (
        statements
        and isinstance(statements[0], ast.Expr)
        and isinstance(statements[0].value, ast.Constant)
        and isinstance(statements[0].value.value, str)
    ):
        statements = statements[1:]
    return len(statements)


def _model_class_count(path: Path) -> int:
    if not path.is_file():
        return 0
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and any(
            (
                isinstance(base, ast.Attribute)
                and base.attr == "Model"
            )
            or (
                isinstance(base, ast.Name)
                and (
                    base.id.endswith("Model")
                    or base.id in {
                        "AbstractBaseUser",
                        "AbstractUser",
                    }
                )
            )
            for base in node.bases
        )
    )


def _assigned_string_values(path: Path, variable_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(
            isinstance(target, ast.Name) and target.id == variable_name
            for target in targets
        ):
            continue
        value = node.value
        if value is None:
            return set()
        return {
            constant.value
            for constant in ast.walk(value)
            if isinstance(constant, ast.Constant)
            and isinstance(constant.value, str)
        }
    return set()


def _module_string_values(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        constant.value
        for constant in ast.walk(tree)
        if isinstance(constant, ast.Constant)
        and isinstance(constant.value, str)
    }


def _included_module_values(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        function_name = None
        if isinstance(node.func, ast.Name):
            function_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            function_name = node.func.attr
        if function_name != "include":
            continue
        first_argument = node.args[0]
        if (
            isinstance(first_argument, ast.Constant)
            and isinstance(first_argument.value, str)
        ):
            values.add(first_argument.value)
    return values


def _dotted_class_exists(dotted_path: str) -> bool:
    if "." not in dotted_path:
        return False
    module_name, class_name = dotted_path.rsplit(".", 1)
    module_path = BACKEND_DIR.joinpath(*module_name.split(".")).with_suffix(
        ".py"
    )
    if not module_path.is_file():
        return False
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    return any(
        isinstance(node, ast.ClassDef) and node.name == class_name
        for node in tree.body
    )


def _test_function_count(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    )


def _auth_test_counts() -> dict[Path, int]:
    candidates = sorted(
        {
            path
            for pattern in ("*auth*.py", "*permission*.py")
            for path in (BACKEND_DIR / "tests").rglob(pattern)
        }
    )
    return {
        path: _test_function_count(path)
        for path in candidates
    }


def _run_declared_auth_tests(test_files: list[Path]) -> int | None:
    if not test_files:
        return None
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        *[
            str(path.relative_to(BACKEND_DIR))
            for path in test_files
        ],
    ]
    result = subprocess.run(
        command,
        cwd=BACKEND_DIR,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode


def _completion_evidence_gates(
    evidence: dict[str, Any] | None,
    *,
    postgresql_verification: dict[str, Any] | None = None,
) -> dict[str, bool]:
    evidence = evidence if isinstance(evidence, dict) else {}
    postgresql_verification = (
        postgresql_verification
        if isinstance(postgresql_verification, dict)
        else {}
    )
    team_review = evidence.get("team_review")
    return {
        "team_reviewed": (
            isinstance(team_review, dict)
            and team_review.get("status") == "APPROVED"
            and isinstance(team_review.get("reviewer"), str)
            and bool(team_review["reviewer"].strip())
            and team_review["reviewer"].strip() != "최지용"
            and isinstance(team_review.get("recorded_at"), str)
            and bool(team_review["recorded_at"].strip())
        ),
        "django_model_migration_parity_verified": (
            postgresql_verification.get("settings_module")
            == "config.settings.local"
            and postgresql_verification.get("makemigrations_status")
            == "PASSED"
        ),
        "postgresql_verified": (
            postgresql_verification.get("settings_module")
            == "config.settings.local"
            and postgresql_verification.get("database_vendor")
            == "PostgreSQL"
            and postgresql_verification.get("connection_status")
            == "CONNECTED"
            and postgresql_verification.get("migration_status")
            == "PASSED"
        ),
    }


def _run_verification_command(
    command: list[str],
    *,
    cwd: Path,
    environ: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=environ,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def verify_postgresql_runtime() -> dict[str, Any]:
    """실제 로컬 Django 설정과 PostgreSQL로 Migration 상태를 검증한다."""

    environ = os.environ.copy()
    environ["DJANGO_SETTINGS_MODULE"] = "config.settings.local"
    connection = _run_verification_command(
        [sys.executable, str(POSTGRESQL_CHECK_PATH)],
        cwd=REPOSITORY_ROOT,
        environ=environ,
    )
    connection_payload: dict[str, Any] = {}
    if connection.stdout:
        try:
            parsed = json.loads(connection.stdout)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            connection_payload = parsed

    result: dict[str, Any] = {
        "settings_module": "config.settings.local",
        "database_vendor": connection_payload.get("vendor"),
        "connection_status": (
            "CONNECTED"
            if (
                connection.returncode == 0
                and connection_payload.get("status") == "CONNECTED"
                and connection_payload.get("vendor") == "PostgreSQL"
            )
            else (
                "NOT_CONFIGURED"
                if connection.returncode == 2
                else "FAILED"
            )
        ),
        "makemigrations_status": "NOT_RUN",
        "migration_status": "NOT_RUN",
    }

    parity = _run_verification_command(
        [
            sys.executable,
            str(MANAGE_PATH),
            "makemigrations",
            "--check",
            "--dry-run",
            "--settings=config.settings.local",
        ],
        cwd=BACKEND_DIR,
        environ=environ,
    )
    result["makemigrations_status"] = (
        "PASSED" if parity.returncode == 0 else "FAILED"
    )
    if result["connection_status"] != "CONNECTED":
        return result

    migration = _run_verification_command(
        [
            sys.executable,
            str(MANAGE_PATH),
            "migrate",
            "--check",
            "--noinput",
            "--settings=config.settings.local",
        ],
        cwd=BACKEND_DIR,
        environ=environ,
    )
    result["migration_status"] = (
        "PASSED" if migration.returncode == 0 else "FAILED"
    )
    return result


def audit_readiness(
    *,
    auth_test_exit_code: int | None = None,
    completion_evidence: dict[str, Any] | None = None,
    postgresql_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    role_contract_text = ROLE_CONTRACT_PATH.read_text(encoding="utf-8")
    api_spec_text = API_SPEC_PATH.read_text(encoding="utf-8")
    jwt_policy_text = JWT_POLICY_PATH.read_text(encoding="utf-8")
    auth_path_text = AUTH_PATH_CONTRACT.read_text(encoding="utf-8")
    role_permission_text = ROLE_PERMISSION_PATH.read_text(encoding="utf-8")
    machine_roles = sorted(
        _yaml_list_values(role_contract_text, "codes")
    )
    model_role_tokens = sorted(
        set(machine_roles)
        & _module_string_values(ACCOUNTS_DIR / "models" / "user.py")
    )
    auth_schema_files = sorted(AUTH_SCHEMA_DIR.glob("*.yaml"))
    empty_auth_schemas = sorted(
        path.name
        for path in auth_schema_files
        if not _yaml_mapping_has_entries(
            path.read_text(encoding="utf-8"),
            "properties",
        )
    )
    runtime_statements = {
        str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/"):
        _substantive_statement_count(path)
        for path in AUTH_RUNTIME_FILES
    }
    migration_files = sorted(
        (ACCOUNTS_DIR / "migrations").glob("[0-9][0-9][0-9][0-9]_*.py")
    )
    auth_test_counts = _auth_test_counts()
    auth_test_files = sorted(
        path
        for path, count in auth_test_counts.items()
        if count > 0
    )
    model_classes = sum(
        _model_class_count(path)
        for path in (ACCOUNTS_DIR / "models").glob("*.py")
    )
    installed_apps = _assigned_string_values(
        SETTINGS_PATH,
        "INSTALLED_APPS",
    )
    rest_framework_values = _assigned_string_values(
        SETTINGS_PATH,
        "REST_FRAMEWORK",
    )
    api_url_values = _included_module_values(API_URLS_PATH)
    configured_authentication_classes = {
        value
        for value in rest_framework_values
        if value.endswith(".JWTAuthentication")
    }

    evidence = {
        "machine_roles": machine_roles,
        "role_contract_valid": bool(machine_roles),
        "model_role_tokens": model_role_tokens,
        "role_code_conflict": set(model_role_tokens) != set(machine_roles),
        "auth_path_defined": _yaml_has_http_operation(auth_path_text),
        "auth_schema_file_count": len(auth_schema_files),
        "empty_auth_schemas": empty_auth_schemas,
        "jwt_policy_open": (
            "OWNER_BASELINE_ACCEPTED" not in jwt_policy_text
        ),
        "state_machine_role_permissions_defined": (
            _yaml_nested_mapping_has_nonempty_values(
                role_permission_text,
                "roles",
            )
        ),
        "runtime_substantive_statements": runtime_statements,
        "runtime_implemented_file_count": sum(
            count > 0 for count in runtime_statements.values()
        ),
        "account_model_class_count": model_classes,
        "account_migration_count": len(migration_files),
        "accounts_app_registered": (
            "apps.accounts.apps.AccountsConfig" in installed_apps
        ),
        "authentication_class_configured": bool(
            configured_authentication_classes
        ) and all(
            _dotted_class_exists(value)
            for value in configured_authentication_classes
        ),
        "auth_routes_registered": (
            "apps.accounts.api.urls" in api_url_values
        ),
        "auth_test_files": [
            str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/")
            for path in auth_test_files
        ],
        "auth_test_function_count": sum(
            auth_test_counts[path]
            for path in auth_test_files
        ),
        "auth_test_execution_status": (
            "NOT_RUN"
            if auth_test_exit_code is None
            else "PASSED"
            if auth_test_exit_code == 0
            else "FAILED"
        ),
        "auth_test_exit_code": auth_test_exit_code,
    }

    owner_blockers = []
    if not evidence["role_contract_valid"]:
        owner_blockers.append("ROLE_CONTRACT_INVALID")
    if evidence["role_code_conflict"]:
        owner_blockers.append("ROLE_CODE_CONFLICT")
    if not evidence["auth_path_defined"]:
        owner_blockers.append("AUTH_PATH_EMPTY")
    if evidence["empty_auth_schemas"]:
        owner_blockers.append("AUTH_SCHEMAS_EMPTY")
    if evidence["jwt_policy_open"]:
        owner_blockers.append("JWT_POLICY_OPEN")
    if any(
        statement_count == 0
        for statement_count in evidence[
            "runtime_substantive_statements"
        ].values()
    ):
        owner_blockers.append("AUTH_RUNTIME_INCOMPLETE")
    if evidence["account_model_class_count"] == 0:
        owner_blockers.append("ACCOUNT_MODELS_MISSING")
    if evidence["account_migration_count"] == 0:
        owner_blockers.append("ACCOUNT_MIGRATIONS_MISSING")
    if not evidence["accounts_app_registered"]:
        owner_blockers.append("ACCOUNTS_APP_NOT_REGISTERED")
    if not evidence["authentication_class_configured"]:
        owner_blockers.append("JWT_AUTHENTICATION_NOT_CONFIGURED")
    if not evidence["auth_routes_registered"]:
        owner_blockers.append("AUTH_ROUTES_NOT_REGISTERED")
    if evidence["auth_test_function_count"] == 0:
        owner_blockers.append("AUTH_TESTS_MISSING")
    elif evidence["auth_test_execution_status"] == "NOT_RUN":
        owner_blockers.append("AUTH_TESTS_NOT_EXECUTED")
    elif evidence["auth_test_execution_status"] == "FAILED":
        owner_blockers.append("AUTH_TESTS_FAILED")

    evidence_gates = _completion_evidence_gates(
        completion_evidence,
        postgresql_verification=postgresql_verification,
    )
    completion_gates = {
        "owner_implementation_ready": not owner_blockers,
        "team_reviewed": evidence_gates["team_reviewed"],
        "django_model_migration_parity_verified": evidence_gates[
            "django_model_migration_parity_verified"
        ],
        "postgresql_verified": evidence_gates["postgresql_verified"],
    }
    completion_blockers = [
        gate.upper()
        for gate, complete in completion_gates.items()
        if gate != "owner_implementation_ready" and not complete
    ]
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
        "completion_evidence_supplied": (
            isinstance(completion_evidence, dict)
            and bool(completion_evidence)
        ),
        "postgresql_verification": (
            postgresql_verification
            if isinstance(postgresql_verification, dict)
            else {
                "settings_module": "config.settings.local",
                "database_vendor": None,
                "connection_status": "NOT_RUN",
                "makemigrations_status": "NOT_RUN",
                "migration_status": "NOT_RUN",
            }
        ),
        "owner_blockers": owner_blockers,
        "completion_blockers": completion_blockers,
        "blockers": owner_blockers + completion_blockers,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="T-017 실행 조건이 충족되지 않았으면 exit code 2를 반환한다.",
    )
    parser.add_argument(
        "--completion-evidence",
        type=Path,
        help="작성자 외 팀 리뷰 기록 JSON 경로",
    )
    parser.add_argument(
        "--verify-postgresql",
        action="store_true",
        help=(
            "config.settings.local로 실제 PostgreSQL 연결, "
            "Model/Migration parity, 미적용 Migration을 검증한다."
        ),
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
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
    test_counts = _auth_test_counts()
    test_files = sorted(
        path
        for path, count in test_counts.items()
        if count > 0
    )
    result = audit_readiness(
        auth_test_exit_code=_run_declared_auth_tests(test_files),
        completion_evidence=completion_evidence,
        postgresql_verification=(
            verify_postgresql_runtime()
            if arguments.verify_postgresql
            else None
        ),
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if arguments.require_ready and result["status"] != "READY":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
