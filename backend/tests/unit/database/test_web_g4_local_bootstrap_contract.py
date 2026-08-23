"""Contract checks for the Web G4 isolated local bootstrap script."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
BOOTSTRAP = (
    REPOSITORY_ROOT / "scripts" / "development" / "bootstrap_web_g4_local.ps1"
)


def _content() -> str:
    return BOOTSTRAP.read_text(encoding="utf-8")


def test_missing_volume_probe_uses_non_erroring_cross_powershell_listing():
    content = _content()

    assert "$rawVolumeNames = @(& docker volume ls --quiet 2>$null)" in content
    assert "$volumeListExitCode = $LASTEXITCODE" in content
    assert "([string]$rawVolumeName).Trim()" in content
    assert "$volumeExists = $volumeNames -contains $volumeName" in content
    assert "Docker Volume 목록을 확인할 수 없습니다." in content
    assert "catch {" in content
    assert "docker volume inspect $volumeName" not in content


def test_bootstrap_preserves_dedicated_volume_and_fail_closed_boundaries():
    content = _content()
    lowered = content.lower()

    assert "waterbridge-web-g4-local-postgres-data" in content
    assert "waterbridge-web-g4-local-postgres" in content
    assert "if (-not $volumeExists)" in content
    assert "if ($volumeExists)" in content
    assert "Do not delete or reuse it automatically." in content
    assert "visits.0005=P1_HOLD_EXCLUDED" in content
    assert "docker volume rm" not in lowered
    assert "down -v" not in lowered


def test_apply_remains_explicit_and_requires_clean_exact_main():
    content = _content()

    assert "[switch]$Apply" in content
    assert "if (-not $Apply)" in content
    assert "$branch -ne 'main'" in content
    assert "$sourceSha -ne $originMain" in content
    assert "Apply requires a clean local main" in content
    assert "Apply requires a clean worktree" in content
