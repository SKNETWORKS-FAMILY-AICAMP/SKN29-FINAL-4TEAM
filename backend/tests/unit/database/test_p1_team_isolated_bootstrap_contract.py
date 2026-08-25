"""P1 팀 로컬 격리 Runtime Bootstrap의 안전 계약 검증."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
BOOTSTRAP = (
    REPOSITORY_ROOT
    / "scripts"
    / "development"
    / "bootstrap_p1_team_isolated_local.ps1"
)
ENV_LOADER = (
    REPOSITORY_ROOT
    / "scripts"
    / "development"
    / "import_p1_team_isolated_env.ps1"
)
BACKEND_STARTER = (
    REPOSITORY_ROOT
    / "scripts"
    / "development"
    / "start_p1_team_isolated_backend.ps1"
)
OTP_WORKER = (
    REPOSITORY_ROOT
    / "scripts"
    / "development"
    / "start_p1_auth_email_worker.ps1"
)


def _content(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_bootstrap_defaults_to_non_mutating_plan_and_dedicated_runtime():
    content = _content(BOOTSTRAP)

    assert "[switch]$Apply" in content
    assert "if (-not $Apply)" in content
    assert ".runtime\\p1-team-isolated" in content
    assert "waterbridge_p1_team_isolated" in content
    assert "waterbridge-p1-team-isolated-postgres-data" in content
    assert "waterbridge-p1-team-isolated-postgres" in content
    assert "approved-test-synthetic-only" in content
    assert "AI_SERVICE_BASE_URL=http://127.0.0.1:8001" in content
    assert "ai_runtime_8001 = 'OUT_OF_SCOPE'" in content


def test_bootstrap_fail_closes_source_volume_and_secret_boundaries():
    content = _content(BOOTSTRAP)
    lowered = content.lower()

    assert "Apply requires HEAD to exactly match its origin tracking branch." in content
    assert "Apply requires a clean worktree" in content
    assert "RuntimeRoot must stay inside the repository workspace." in content
    assert "ApprovedCustomerInput must stay under backend/.runtime." in content
    assert "Do not delete or reuse it automatically." in content
    assert "secret_values_printed = $false" in content
    assert "docker volume rm" not in lowered
    assert "down -v" not in lowered
    assert "drop database" not in lowered
    assert "drop role" not in lowered


def test_bootstrap_uses_profiles_hold_gate_and_minimum_seed_order():
    content = _content(BOOTSTRAP)

    migration_position = content.index("$migrationRunner")
    common_codes_position = content.index("'seed_common_codes'")
    consultant_position = content.index("'seed_p1_team_consultant'")
    customers_position = content.index("'seed_p1_approved_test_customers'")

    assert "--profile', $profileName" in content
    assert "$profileName = 'p1-team-isolated'" in content
    assert "visits.0005=P1_HOLD_EXCLUDED" in content
    assert "manage.py migrate" not in content
    assert "'--fake'" not in content
    assert migration_position < common_codes_position
    assert common_codes_position < consultant_position < customers_position
    assert "seed_demo_accounts" not in content
    assert "seed_demo_products" not in content
    assert "seed_demo_subscriptions" not in content
    assert "seed_consultant_dashboard" not in content
    assert "prepare_p1_team_isolated_runtime" not in content


def test_bootstrap_proves_replay_and_ai_free_draft_inquiry_contract():
    content = _content(BOOTSTRAP)

    assert "$customerReplay" in content
    assert "$customerReplay.customers_created -ne 0" in content
    assert "$customerReplay.contacts_created -ne 0" in content
    assert "$customerReplay.subscriptions_created -ne 0" in content
    assert "'verify_p1_team_isolated_e2e'" in content
    assert "$contractE2E.inquiry_status -ne 'DRAFT'" in content
    assert "$contractE2E.inquiry_state_version -ne 1" in content
    assert "$contractE2E.ai_called" in content
    assert "PASS_ROLLBACK_PRESERVED" in content


def test_reuse_never_reseeds_or_resets_runtime():
    content = _content(BOOTSTRAP)

    assert "$bootstrapPending" in content
    assert "NOT_RERUN_ON_REUSE" in content
    assert "Existing P1 Runtime source identity differs" in content
    assert "Reuse was requested, but the P1 Runtime does not exist." in content
    assert "new or incomplete" in content
    assert "resumed_incomplete_runtime" in content
    assert "docker volume rm" not in content.lower()
    assert "source-sha.txt" in content
    assert "source-branch.txt" in content


def test_runtime_consumers_load_same_db_and_stable_django_environment():
    loader = _content(ENV_LOADER)
    starter = _content(BACKEND_STARTER)
    worker = _content(OTP_WORKER)

    assert "runtime.env" in loader
    assert "DJANGO_SECRET_KEY" in loader
    assert "$Role -eq 'Admin'" in loader
    assert "TEAM_INTEGRATION_MIGRATOR_PASSWORD" in loader
    assert "waterbridge_p1_migrator" in loader
    assert "waterbridge_p1_runtime" in loader
    assert "RuntimeRoot must stay inside the repository workspace." in loader
    assert "import_p1_team_isolated_env.ps1" in starter
    assert "--profile p1-team-isolated" in starter
    assert "manage.py migrate --check" not in starter
    assert "--operational" in starter
    assert "import_p1_team_isolated_env.ps1" in worker
    assert "process_p1_auth_email_outbox" in worker
    assert "--once" in worker
