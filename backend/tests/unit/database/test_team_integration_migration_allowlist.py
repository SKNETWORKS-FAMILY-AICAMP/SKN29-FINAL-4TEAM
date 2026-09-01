"""TEAM_INTEGRATION Migration Allowlist와 visits.0005 HOLD 검증."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader


BACKEND_DIR = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = BACKEND_DIR.parent
SCRIPT_PATH = (
    REPOSITORY_ROOT
    / "scripts"
    / "database"
    / "migrate_team_integration_allowlist.py"
)


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "team_integration_migration_allowlist",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def allowlist_module() -> ModuleType:
    return load_module()


@pytest.fixture
def migration_graph():
    return MigrationLoader(None, ignore_no_migrations=True).graph


def executor_for(graph, applied=()):
    executor = object.__new__(MigrationExecutor)
    executor.loader = SimpleNamespace(
        graph=graph,
        applied_migrations={node: object() for node in applied},
        replace_migrations=False,
    )
    return executor


def connection_for(
    *,
    database_name: str,
    database_user: str,
    host: str,
):
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _statement):
            return None

        def fetchone(self):
            return database_name, database_user

    return SimpleNamespace(
        vendor="postgresql",
        settings_dict={"HOST": host},
        cursor=lambda: Cursor(),
    )


def test_named_profiles_preserve_default_and_add_local_p1_scope(
    allowlist_module: ModuleType,
):
    default = allowlist_module.MIGRATION_PROFILES["team-integration"]
    p1 = allowlist_module.MIGRATION_PROFILES["p1-team-isolated"]

    assert allowlist_module.DEFAULT_PROFILE == "team-integration"
    assert default == {
        "database": "waterbridge_team_integration",
        "migrator_role": "waterbridge_ti_migrator",
        "local_only": False,
        "scope": "TEAM_INTEGRATION_MIGRATION_ALLOWLIST",
    }
    assert p1 == {
        "database": "waterbridge_p1_team_isolated",
        "migrator_role": "waterbridge_p1_migrator",
        "local_only": True,
        "scope": "P1_TEAM_ISOLATED_MIGRATION_ALLOWLIST",
    }
    assert allowlist_module.TARGET_DATABASE == default["database"]
    assert allowlist_module.MIGRATOR_ROLE == default["migrator_role"]


def test_cli_defaults_to_team_integration_profile(
    allowlist_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(allowlist_module.sys, "argv", ["migration-allowlist"])

    assert allowlist_module.parse_args().profile == "team-integration"


def test_internal_api_rejects_unnamed_migration_profile(
    allowlist_module: ModuleType,
):
    with pytest.raises(allowlist_module.AllowlistError) as exc_info:
        allowlist_module._resolve_profile(
            {
                "database": "unapproved_database",
                "migrator_role": "unapproved_role",
                "local_only": False,
                "scope": "UNAPPROVED",
            }
        )

    assert exc_info.value.reason == "migration_profile_invalid"


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_p1_profile_accepts_only_exact_database_role_and_local_host(
    allowlist_module: ModuleType,
    host: str,
):
    profile = allowlist_module.MIGRATION_PROFILES["p1-team-isolated"]
    connection = connection_for(
        database_name="waterbridge_p1_team_isolated",
        database_user="waterbridge_p1_migrator",
        host=host,
    )

    assert allowlist_module._database_identity(connection, profile) == (
        "waterbridge_p1_team_isolated",
        "waterbridge_p1_migrator",
    )


@pytest.mark.parametrize("host", ["", "10.0.0.10", "db.example.internal"])
def test_p1_profile_blocks_nonlocal_or_implicit_database_host(
    allowlist_module: ModuleType,
    host: str,
):
    profile = allowlist_module.MIGRATION_PROFILES["p1-team-isolated"]
    connection = connection_for(
        database_name="waterbridge_p1_team_isolated",
        database_user="waterbridge_p1_migrator",
        host=host,
    )

    with pytest.raises(allowlist_module.AllowlistError) as exc_info:
        allowlist_module._database_identity(connection, profile)

    assert exc_info.value.reason == "local_database_host_required"


@pytest.mark.parametrize(
    "database_name, database_user, expected_reason",
    [
        (
            "waterbridge_team_integration",
            "waterbridge_p1_migrator",
            "target_database_mismatch",
        ),
        (
            "waterbridge_p1_team_isolated",
            "waterbridge_ti_migrator",
            "migrator_role_required",
        ),
    ],
)
def test_p1_profile_blocks_wrong_database_or_migrator(
    allowlist_module: ModuleType,
    database_name: str,
    database_user: str,
    expected_reason: str,
):
    profile = allowlist_module.MIGRATION_PROFILES["p1-team-isolated"]
    connection = connection_for(
        database_name=database_name,
        database_user=database_user,
        host="127.0.0.1",
    )

    with pytest.raises(allowlist_module.AllowlistError) as exc_info:
        allowlist_module._database_identity(connection, profile)

    assert exc_info.value.reason == expected_reason


def test_p1_profile_plan_reuses_allowlist_and_excludes_visits_0005(
    allowlist_module: ModuleType,
    migration_graph,
):
    profile = allowlist_module.MIGRATION_PROFILES["p1-team-isolated"]
    plan = allowlist_module.build_plan(
        executor_for(migration_graph),
        database_name="waterbridge_p1_team_isolated",
        database_user="waterbridge_p1_migrator",
        profile=profile,
    )

    assert plan["profile"] == "p1-team-isolated"
    assert plan["scope"] == "P1_TEAM_ISOLATED_MIGRATION_ALLOWLIST"
    assert plan["database"] == {
        "name": "waterbridge_p1_team_isolated",
        "user": "waterbridge_p1_migrator",
    }
    assert all("visits.0005" not in node for node in plan["remaining_plan"])
    assert plan["expected_final"]["visits.0005"] == "NOT_APPLIED_P1_HOLD"


def test_p1_apply_requires_exact_p1_database_confirmation(
    allowlist_module: ModuleType,
):
    profile = allowlist_module.MIGRATION_PROFILES["p1-team-isolated"]
    source_state = {"sha": "a" * 40, "clean": True}
    arguments = argparse.Namespace(
        confirm_database="waterbridge_team_integration",
        confirm_hold=allowlist_module.HOLD_CONFIRMATION,
        confirm_source_sha=source_state["sha"],
    )

    with pytest.raises(allowlist_module.AllowlistError) as exc_info:
        allowlist_module._validate_apply_request(
            arguments,
            source_state,
            profile,
        )

    assert exc_info.value.reason == "database_confirmation_required"


def test_current_graph_matches_explicit_allowlist_and_excludes_visits_0005(
    allowlist_module: ModuleType,
    migration_graph,
):
    closure = allowlist_module.approved_closure(migration_graph)

    assert set(migration_graph.leaf_nodes()) == set(
        allowlist_module.EXPECTED_GRAPH_LEAVES
    )
    assert allowlist_module.FORBIDDEN_MIGRATION not in closure
    assert ("visits", "0004_visit_runtime_fields") in closure
    assert (
        "visits",
        "0004_visit_runtime_fields",
    ) in allowlist_module.APPROVED_TARGETS
    assert (
        "accounts",
        "0009_approved_test_contract_email",
    ) in closure
    assert (
        "accounts",
        "0009_approved_test_contract_email",
    ) in allowlist_module.APPROVED_TARGETS
    assert (
        "operations",
        "0003_product_expansion_import_profile",
    ) in closure
    assert (
        "operations",
        "0003_product_expansion_import_profile",
    ) in allowlist_module.APPROVED_TARGETS
    assert (
        "evidence",
        "0015_project_child_record_type_in_ai_view",
    ) in closure
    assert (
        "evidence",
        "0015_project_child_record_type_in_ai_view",
    ) in allowlist_module.APPROVED_TARGETS
    assert (
        "inquiries",
        "0017_consultationcauseledger",
    ) in closure
    assert (
        "inquiries",
        "0017_consultationcauseledger",
    ) in allowlist_module.APPROVED_TARGETS


def test_empty_database_plan_is_forward_only_and_has_explicit_target_order(
    allowlist_module: ModuleType,
    migration_graph,
):
    plan = allowlist_module.build_plan(
        executor_for(migration_graph),
        database_name=allowlist_module.TARGET_DATABASE,
        database_user=allowlist_module.MIGRATOR_ROLE,
    )

    assert plan["status"] == "PLAN_READY"
    assert plan["mutates_database"] is False
    assert plan["remaining_plan"]
    assert all("visits.0005" not in node for node in plan["remaining_plan"])
    assert len(plan["execution_targets"]) == len(
        allowlist_module.APPROVED_TARGETS
    )
    assert plan["expected_final"] == {
        "accounts.0009": "APPLIED",
        "evidence.0015": "APPLIED",
        "inquiries.0017": "APPLIED",
        "operations.0003": "APPLIED",
        "visits.0004": "APPLIED",
        "visits.0005": "NOT_APPLIED_P1_HOLD",
        "approved_targets": "APPLIED",
        "unexpected_migrations": 0,
        "remaining_approved_plan": 0,
    }


def test_plan_blocks_when_forbidden_migration_is_already_applied(
    allowlist_module: ModuleType,
    migration_graph,
):
    executor = executor_for(
        migration_graph,
        applied=(allowlist_module.FORBIDDEN_MIGRATION,),
    )

    with pytest.raises(allowlist_module.AllowlistError) as exc_info:
        allowlist_module.build_plan(
            executor,
            database_name=allowlist_module.TARGET_DATABASE,
            database_user=allowlist_module.MIGRATOR_ROLE,
        )

    assert exc_info.value.reason == "forbidden_migration_already_applied"


def test_graph_leaf_change_blocks_stale_allowlist(
    allowlist_module: ModuleType,
    migration_graph,
    monkeypatch: pytest.MonkeyPatch,
):
    original_leaf_nodes = migration_graph.leaf_nodes
    monkeypatch.setattr(
        migration_graph,
        "leaf_nodes",
        lambda app=None: [
            *original_leaf_nodes(app),
            ("inquiries", "9999_unreviewed"),
        ],
    )

    with pytest.raises(allowlist_module.AllowlistError) as exc_info:
        allowlist_module.approved_closure(migration_graph)

    assert exc_info.value.reason == "migration_graph_leaves_changed"


@pytest.mark.parametrize(
    "override, expected_reason",
    [
        (
            {"confirm_database": "waterbridge"},
            "database_confirmation_required",
        ),
        (
            {"confirm_hold": "visits.0005=APPLY"},
            "hold_confirmation_required",
        ),
        (
            {"confirm_source_sha": "f" * 40},
            "source_sha_confirmation_required",
        ),
    ],
)
def test_apply_requires_exact_database_sha_and_hold_confirmations(
    allowlist_module: ModuleType,
    override: dict[str, str],
    expected_reason: str,
):
    source_state = {"sha": "a" * 40, "clean": True}
    values = {
        "confirm_database": allowlist_module.TARGET_DATABASE,
        "confirm_hold": allowlist_module.HOLD_CONFIRMATION,
        "confirm_source_sha": source_state["sha"],
        **override,
    }

    with pytest.raises(allowlist_module.AllowlistError) as exc_info:
        allowlist_module._validate_apply_request(
            argparse.Namespace(**values),
            source_state,
        )

    assert exc_info.value.reason == expected_reason


def test_apply_requires_clean_worktree(allowlist_module: ModuleType):
    source_state = {"sha": "a" * 40, "clean": False}
    arguments = argparse.Namespace(
        confirm_database=allowlist_module.TARGET_DATABASE,
        confirm_hold=allowlist_module.HOLD_CONFIRMATION,
        confirm_source_sha=source_state["sha"],
    )

    with pytest.raises(allowlist_module.AllowlistError) as exc_info:
        allowlist_module._validate_apply_request(arguments, source_state)

    assert exc_info.value.reason == "clean_worktree_required"


def test_apply_runs_explicit_targets_and_verifies_exact_final_state(
    allowlist_module: ModuleType,
    migration_graph,
):
    empty_executor = executor_for(migration_graph)
    initial_plan = allowlist_module.build_plan(
        empty_executor,
        database_name=allowlist_module.TARGET_DATABASE,
        database_user=allowlist_module.MIGRATOR_ROLE,
    )
    closure = allowlist_module.approved_closure(migration_graph)
    final_executor = executor_for(migration_graph, applied=closure)
    calls: list[tuple[str, str]] = []

    result = allowlist_module.apply_allowlist(
        lambda: final_executor,
        lambda app, target: calls.append((app, target)),
        initial_plan,
    )

    assert result["status"] == "APPLIED_AND_VERIFIED"
    assert calls == [
        (target["app"], target["target"])
        for target in initial_plan["execution_targets"]
    ]
    assert result["verification"]["accounts.0009"] == "APPLIED"
    assert result["verification"]["evidence.0015"] == "APPLIED"
    assert result["verification"]["inquiries.0017"] == "APPLIED"
    assert result["verification"]["operations.0003"] == "APPLIED"
    assert result["verification"]["visits.0004"] == "APPLIED"
    assert (
        result["verification"]["visits.0005"]
        == "NOT_APPLIED_P1_HOLD"
    )
    assert result["verification"]["unexpected"] == []
    assert result["verification"]["blockers"] == []


def test_apply_does_not_rerun_targets_when_allowlist_is_already_complete(
    allowlist_module: ModuleType,
    migration_graph,
):
    closure = allowlist_module.approved_closure(migration_graph)
    complete_executor = executor_for(migration_graph, applied=closure)
    initial_plan = allowlist_module.build_plan(
        complete_executor,
        database_name=allowlist_module.TARGET_DATABASE,
        database_user=allowlist_module.MIGRATOR_ROLE,
    )
    calls: list[tuple[str, str]] = []

    result = allowlist_module.apply_allowlist(
        lambda: complete_executor,
        lambda app, target: calls.append((app, target)),
        initial_plan,
    )

    assert result["status"] == "ALREADY_APPLIED_AND_VERIFIED"
    assert calls == []
    assert result["verification"]["blockers"] == []


def test_migration_lock_blocks_concurrent_operator(
    allowlist_module: ModuleType,
):
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _statement, _parameters):
            return None

        def fetchone(self):
            return (False,)

    connection = SimpleNamespace(cursor=lambda: Cursor())

    with pytest.raises(allowlist_module.AllowlistError) as exc_info:
        with allowlist_module._migration_lock(connection):
            pytest.fail("unavailable lock must not enter apply section")

    assert exc_info.value.reason == "migration_lock_unavailable"


def test_migration_lock_is_released_after_apply_section(
    allowlist_module: ModuleType,
):
    statements: list[str] = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, statement, _parameters):
            statements.append(statement)

        def fetchone(self):
            return (True,)

    connection = SimpleNamespace(cursor=lambda: Cursor())

    with allowlist_module._migration_lock(connection):
        statements.append("APPLY_SECTION")

    assert statements == [
        "SELECT pg_try_advisory_lock(%s)",
        "APPLY_SECTION",
        "SELECT pg_advisory_unlock(%s)",
    ]


def test_source_has_no_fake_or_migration_recorder_mutation_path():
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert '"--fake"' not in source
    assert "MigrationRecorder" not in source
    assert "django_migrations SET" not in source
    assert "DELETE FROM django_migrations" not in source
    assert "DROP DATABASE" not in source
    assert "DROP ROLE" not in source
    assert "clean_worktree_required" in source
    assert "pg_try_advisory_lock" in source
