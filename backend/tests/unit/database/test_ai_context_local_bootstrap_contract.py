"""Contract checks for the AI-owner local Context bootstrap runbook scripts."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
BOOTSTRAP = (
    REPOSITORY_ROOT / "scripts" / "development" / "bootstrap_ai_context_local.ps1"
)
BACKEND_STARTER = (
    REPOSITORY_ROOT
    / "scripts"
    / "development"
    / "start_ai_context_backend_local.ps1"
)
AI_LOADER = (
    REPOSITORY_ROOT / "scripts" / "development" / "load_ai_context_local_env.ps1"
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_bootstrap_defaults_to_plan_and_requires_clean_exact_main_for_apply():
    content = _text(BOOTSTRAP)

    assert "[switch]$Apply" in content
    assert "if (-not $Apply)" in content
    assert "mutates_local_environment = [bool]$Apply" in content
    assert "Apply requires a clean local main" in content
    assert "Apply requires a clean worktree, including untracked source files" in content
    assert "$branch -ne 'main'" in content
    assert "$sourceSha -ne $originMain" in content


def test_bootstrap_uses_only_dedicated_local_database_container_and_volume():
    content = _text(BOOTSTRAP)

    assert ".runtime\\ai-context-local" in content
    assert "waterbridge-ai-context-local-postgres" in content
    assert "waterbridge-ai-context-local-postgres-data" in content
    assert "waterbridge_team_integration" in content
    assert "127.0.0.1" in content
    assert "visits.0005=P1_HOLD_EXCLUDED" in content
    assert "--confirm-database', 'waterbridge_team_integration'" in content


def test_bootstrap_prepares_canonical_evidence_and_exact_five_cases():
    content = _text(BOOTSTRAP)

    assert "export_canonical_embedding_fixture" in content
    assert "import_ai_canonical_evidence" in content
    assert "sync_ai_canonical_crosswalk" in content
    assert "--evidence-profile', 'baseline'" in content
    assert "create_ai_context_e2e_fixture" in content
    for scenario_id in (
        "SYN-IAC425-101",
        "SYN-IAC425-108",
        "SYN-IAC606-101",
        "SYN-IAC606-107",
    ):
        assert scenario_id in content
    assert "AI_RAG_RUNTIME_PROFILE=mvp" in content
    assert "AI_RETRIEVAL_TRANSPORT=mcp" in content


def test_backend_and_ai_processes_load_separate_minimum_roles():
    backend_content = _text(BACKEND_STARTER)
    ai_content = _text(AI_LOADER)

    assert "-Role Runtime" in backend_content
    assert "-Role AI" in ai_content
    assert "Dot-source this script" in ai_content
    assert "AI_CONTEXT_LOCAL_ENV_LOADED" in ai_content
    assert "context_cases = '5/5_PASS'" in ai_content
    assert "PRESENT_NOT_PRINTED" in backend_content
    assert "PRESENT_NOT_PRINTED" in ai_content


def test_local_backend_allows_both_approved_synthetic_customer_login_codes():
    bootstrap_content = _text(BOOTSTRAP)
    backend_content = _text(BACKEND_STARTER)

    for content in (bootstrap_content, backend_content):
        assert "DJANGO_DEMO_LOGIN_CODES" in content
        assert "DEMO-CUSTOMER-001" in content
        assert "SYN-CUSTOMER-001" in content
        assert "'CUS-0001'" not in content


def test_local_scripts_do_not_offer_destructive_or_secret_printing_shortcuts():
    combined = "\n".join(_text(path) for path in (BOOTSTRAP, BACKEND_STARTER, AI_LOADER))
    lowered = combined.lower()

    for forbidden in (
        "docker compose down -v",
        "docker volume rm",
        "drop database",
        "git reset --hard",
        "git clean -fd",
    ):
        assert forbidden not in lowered
    assert "secret_values_printed = $false" in combined
    assert "AI_HANDOFF_INTERNAL_TOKEN=$Token" in combined
    assert "AI_HANDOFF_INTERNAL_TOKEN=$handoff.AI_HANDOFF_INTERNAL_TOKEN" not in combined
