"""TEAM_INTEGRATION 승인 Migration만 Fail-closed로 계획·적용한다.

기본 실행은 비변경 Plan이다. 실제 적용은 정확한 DB·Source SHA·
``visits.0005`` HOLD 확인을 모두 제공하고 Clean Worktree에서만 허용한다.
Migration Graph의 Leaf가 바뀌거나 금지 Migration이 의존성으로 유입되면
적용 전에 중단한다.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPOSITORY_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


MigrationKey = tuple[str, str]

TARGET_DATABASE = "waterbridge_team_integration"
MIGRATOR_ROLE = "waterbridge_ti_migrator"
FORBIDDEN_MIGRATION: MigrationKey = (
    "visits",
    "0005_replace_visit_result_assignment_fk",
)
HOLD_CONFIRMATION = "visits.0005=P1_HOLD_EXCLUDED"
ADVISORY_LOCK_KEY = 870_429_002

EXPECTED_GRAPH_LEAVES: tuple[MigrationKey, ...] = (
    ("accounts", "0005_account_lifecycle_and_audit"),
    ("admin", "0003_logentry_add_action_flag_choices"),
    ("audit", "0005_airun_analyze_symptom_task"),
    ("auth", "0012_alter_user_first_name_max_length"),
    ("care", "0002_add_imported_care_fields"),
    ("common_codes", "0002_common_code"),
    ("consultations", "0002_consultation_runtime_fields"),
    ("contenttypes", "0002_remove_content_type_name"),
    ("evidence", "0011_cast_chunk_embedding_vector_dimensions"),
    ("inquiries", "0013_inquiry_priority_code"),
    ("operations", "0002_consultant_dashboard_projection"),
    ("products", "0001_initial"),
    ("questionnaires", "0003_questionnaire_answers_allow_blank"),
    ("sessions", "0001_initial"),
    ("subscriptions", "0002_add_synthetic_projection_fields"),
    ("token_blacklist", "0013_alter_blacklistedtoken_options_and_more"),
    FORBIDDEN_MIGRATION,
    ("workflow", "0005_status_history_contract_names_indexes"),
)

APPROVED_TARGETS: tuple[MigrationKey, ...] = tuple(
    ("visits", "0004_visit_runtime_fields")
    if target == FORBIDDEN_MIGRATION
    else target
    for target in EXPECTED_GRAPH_LEAVES
)


class AllowlistError(RuntimeError):
    """비밀값 없이 외부에 보고할 Fail-closed 오류."""

    def __init__(
        self,
        reason: str,
        *,
        nodes: tuple[MigrationKey, ...] = (),
    ) -> None:
        super().__init__(f"TEAM_INTEGRATION migration blocked: {reason}")
        self.reason = reason
        self.nodes = tuple(sorted(set(nodes)))


def _node_list(nodes: set[MigrationKey] | tuple[MigrationKey, ...]) -> list[str]:
    return [f"{app}.{name}" for app, name in sorted(nodes)]


def _node_sequence(nodes: tuple[MigrationKey, ...]) -> list[str]:
    return [f"{app}.{name}" for app, name in nodes]


def _migration_key(migration: Any) -> MigrationKey:
    return migration.app_label, migration.name


def approved_closure(graph: Any) -> set[MigrationKey]:
    leaves = set(graph.leaf_nodes())
    expected = set(EXPECTED_GRAPH_LEAVES)
    if leaves != expected:
        raise AllowlistError(
            "migration_graph_leaves_changed",
            nodes=tuple(leaves.symmetric_difference(expected)),
        )

    closure: set[MigrationKey] = set()
    for target in APPROVED_TARGETS:
        if target not in graph.nodes:
            raise AllowlistError("approved_target_missing", nodes=(target,))
        closure.update(graph.forwards_plan(target))

    if FORBIDDEN_MIGRATION in closure:
        raise AllowlistError(
            "forbidden_migration_required_by_approved_target",
            nodes=(FORBIDDEN_MIGRATION,),
        )
    return closure


def _ordered_targets(executor: Any) -> tuple[MigrationKey, ...]:
    full_plan = executor.migration_plan(
        list(APPROVED_TARGETS),
        clean_start=True,
    )
    positions: dict[MigrationKey, int] = {}
    for index, (migration, backwards) in enumerate(full_plan):
        if backwards:
            raise AllowlistError("backward_operation_in_clean_plan")
        positions[_migration_key(migration)] = index

    missing = tuple(target for target in APPROVED_TARGETS if target not in positions)
    if missing:
        raise AllowlistError("approved_target_missing_from_plan", nodes=missing)
    return tuple(sorted(APPROVED_TARGETS, key=positions.__getitem__))


def build_plan(
    executor: Any,
    *,
    database_name: str,
    database_user: str,
) -> dict[str, Any]:
    graph = executor.loader.graph
    closure = approved_closure(graph)
    applied = set(executor.loader.applied_migrations)

    if FORBIDDEN_MIGRATION in applied:
        raise AllowlistError(
            "forbidden_migration_already_applied",
            nodes=(FORBIDDEN_MIGRATION,),
        )
    unexpected = applied - closure
    if unexpected:
        raise AllowlistError(
            "unexpected_applied_migrations",
            nodes=tuple(unexpected),
        )

    raw_plan = executor.migration_plan(list(APPROVED_TARGETS))
    backwards = tuple(
        _migration_key(migration)
        for migration, is_backwards in raw_plan
        if is_backwards
    )
    if backwards:
        raise AllowlistError("backward_operation_required", nodes=backwards)

    remaining = tuple(_migration_key(migration) for migration, _ in raw_plan)
    forbidden = tuple(node for node in remaining if node == FORBIDDEN_MIGRATION)
    if forbidden:
        raise AllowlistError("forbidden_migration_in_plan", nodes=forbidden)
    outside = tuple(node for node in remaining if node not in closure)
    if outside:
        raise AllowlistError("unapproved_migration_in_plan", nodes=outside)

    ordered_targets = _ordered_targets(executor)
    return {
        "status": "PLAN_READY" if remaining else "ALREADY_APPLIED",
        "scope": "TEAM_INTEGRATION_MIGRATION_ALLOWLIST",
        "mutates_database": False,
        "database": {
            "name": database_name,
            "user": database_user,
        },
        "forbidden_migration": "visits.0005_replace_visit_result_assignment_fk",
        "hold": HOLD_CONFIRMATION,
        "approved_targets": [
            {"app": app, "target": target}
            for app, target in APPROVED_TARGETS
        ],
        "execution_targets": [
            {"app": app, "target": target}
            for app, target in ordered_targets
        ],
        "remaining_plan": _node_sequence(remaining),
        "applied_count": len(applied),
        "expected_final": {
            "operations.0002": "APPLIED",
            "visits.0004": "APPLIED",
            "visits.0005": "NOT_APPLIED_P1_HOLD",
            "approved_targets": "APPLIED",
            "unexpected_migrations": 0,
            "remaining_approved_plan": 0,
        },
    }


def verify_final(executor: Any) -> dict[str, Any]:
    closure = approved_closure(executor.loader.graph)
    applied = set(executor.loader.applied_migrations)
    missing = closure - applied
    unexpected = applied - closure
    remaining = executor.migration_plan(list(APPROVED_TARGETS))

    blockers: list[str] = []
    if FORBIDDEN_MIGRATION in applied:
        blockers.append("FORBIDDEN_MIGRATION_APPLIED")
    if missing:
        blockers.append("APPROVED_MIGRATIONS_MISSING")
    if unexpected:
        blockers.append("UNEXPECTED_MIGRATIONS_APPLIED")
    if remaining:
        blockers.append("APPROVED_PLAN_REMAINS")

    return {
        "status": "VERIFIED" if not blockers else "BLOCKED",
        "operations.0002": (
            "APPLIED"
            if (
                "operations",
                "0002_consultant_dashboard_projection",
            )
            in applied
            else "MISSING"
        ),
        "visits.0004": (
            "APPLIED"
            if ("visits", "0004_visit_runtime_fields") in applied
            else "MISSING"
        ),
        "visits.0005": (
            "APPLIED_FORBIDDEN"
            if FORBIDDEN_MIGRATION in applied
            else "NOT_APPLIED_P1_HOLD"
        ),
        "approved_migration_count": len(closure),
        "applied_approved_count": len(applied & closure),
        "missing": _node_list(missing),
        "unexpected": _node_list(unexpected),
        "remaining_plan_count": len(remaining),
        "blockers": blockers,
    }


def apply_allowlist(
    executor_factory: Callable[[], Any],
    migrate_runner: Callable[[str, str], None],
    initial_plan: dict[str, Any],
) -> dict[str, Any]:
    if initial_plan["status"] == "ALREADY_APPLIED":
        verification = verify_final(executor_factory())
        if verification["status"] != "VERIFIED":
            raise AllowlistError("post_apply_verification_failed")
        return {
            "status": "ALREADY_APPLIED_AND_VERIFIED",
            "scope": "TEAM_INTEGRATION_MIGRATION_ALLOWLIST",
            "verification": verification,
            "next_action": (
                "Rerun provision_team_integration.py to reconcile grants."
            ),
        }

    for target in initial_plan["execution_targets"]:
        migrate_runner(target["app"], target["target"])

    verification = verify_final(executor_factory())
    if verification["status"] != "VERIFIED":
        raise AllowlistError("post_apply_verification_failed")
    return {
        "status": "APPLIED_AND_VERIFIED",
        "scope": "TEAM_INTEGRATION_MIGRATION_ALLOWLIST",
        "verification": verification,
        "next_action": (
            "Rerun provision_team_integration.py to reconcile grants."
        ),
    }


def _source_state() -> dict[str, Any]:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise AllowlistError("git_source_state_unavailable") from exc
    if len(sha) != 40:
        raise AllowlistError("git_source_sha_invalid")
    return {"sha": sha, "clean": not bool(dirty)}


def _validate_apply_request(
    arguments: argparse.Namespace,
    source_state: dict[str, Any],
) -> None:
    if arguments.confirm_database != TARGET_DATABASE:
        raise AllowlistError("database_confirmation_required")
    if arguments.confirm_hold != HOLD_CONFIRMATION:
        raise AllowlistError("hold_confirmation_required")
    if arguments.confirm_source_sha != source_state["sha"]:
        raise AllowlistError("source_sha_confirmation_required")
    if not source_state["clean"]:
        raise AllowlistError("clean_worktree_required")


def _database_identity(connection: Any) -> tuple[str, str]:
    if connection.vendor != "postgresql":
        raise AllowlistError("postgresql_required")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user")
        database_name, database_user = cursor.fetchone()
    if database_name != TARGET_DATABASE:
        raise AllowlistError("target_database_mismatch")
    if database_user != MIGRATOR_ROLE:
        raise AllowlistError("migrator_role_required")
    return database_name, database_user


@contextmanager
def _migration_lock(connection: Any):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_try_advisory_lock(%s)",
            (ADVISORY_LOCK_KEY,),
        )
        if cursor.fetchone()[0] is not True:
            raise AllowlistError("migration_lock_unavailable")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_unlock(%s)",
                (ADVISORY_LOCK_KEY,),
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="승인 Allowlist를 실제 적용한다. 기본은 Plan-only다.",
    )
    parser.add_argument("--confirm-database")
    parser.add_argument("--confirm-source-sha")
    parser.add_argument("--confirm-hold")
    parser.add_argument(
        "--settings",
        default="config.settings.local",
    )
    parser.add_argument("--verbosity", type=int, choices=(0, 1, 2), default=1)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    source_state: dict[str, Any] | None = None
    try:
        source_state = _source_state()
        if arguments.apply:
            _validate_apply_request(arguments, source_state)

        os.environ["DJANGO_SETTINGS_MODULE"] = arguments.settings
        from config.env import load_backend_env

        load_backend_env(settings_module=arguments.settings)

        import django

        django.setup()
        from django.core.management import call_command
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        database_name, database_user = _database_identity(connection)

        def executor_factory() -> MigrationExecutor:
            return MigrationExecutor(connection)

        if not arguments.apply:
            initial_plan = build_plan(
                executor_factory(),
                database_name=database_name,
                database_user=database_user,
            )
            initial_plan["source"] = source_state
            result = initial_plan
        else:
            def migrate_runner(app: str, target: str) -> None:
                call_command(
                    "migrate",
                    app,
                    target,
                    database="default",
                    interactive=False,
                    verbosity=arguments.verbosity,
                )

            with _migration_lock(connection):
                initial_plan = build_plan(
                    executor_factory(),
                    database_name=database_name,
                    database_user=database_user,
                )
                result = apply_allowlist(
                    executor_factory,
                    migrate_runner,
                    initial_plan,
                )
            result["source"] = source_state
            result["database"] = {
                "name": database_name,
                "user": database_user,
            }
    except AllowlistError as exc:
        result = {
            "status": "BLOCKED",
            "scope": "TEAM_INTEGRATION_MIGRATION_ALLOWLIST",
            "reason": exc.reason,
            "nodes": _node_list(set(exc.nodes)),
            "source": source_state,
            "message": "비밀번호·Host·DSN·CA는 출력하지 않습니다.",
        }
        exit_code = 3
    except Exception as exc:  # noqa: BLE001 - Secret-free CLI 결과
        result = {
            "status": "FAILED",
            "scope": "TEAM_INTEGRATION_MIGRATION_ALLOWLIST",
            "error_type": type(exc).__name__,
            "message": "실행에 실패했습니다. 연결 정보는 출력하지 않습니다.",
        }
        exit_code = 1
    else:
        exit_code = 0

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
