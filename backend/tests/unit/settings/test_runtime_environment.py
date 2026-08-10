"""로컬·배포 설정의 비밀값 없는 fail-fast 검증."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings.base import require_environment_variables


BACKEND_DIR = Path(__file__).resolve().parents[3]
TEST_CA_PATH = (
    BACKEND_DIR / "tests" / "fixtures" / "team_integration" / "test-ca.pem"
)
PRODUCTION_ENV = {
    "DJANGO_SETTINGS_MODULE": "config.settings.production",
    "DJANGO_SECRET_KEY": "test-production-secret",
    "DJANGO_TIME_ZONE": "UTC",
    "DJANGO_ALLOWED_HOSTS": "backend.internal",
    "DJANGO_CORS_ALLOWED_ORIGINS": "https://web.internal",
    "AI_SERVICE_BASE_URL": "https://ai.internal",
    "POSTGRES_DB": "waterbridge_team_integration",
    "POSTGRES_USER": "waterbridge_ti_runtime",
    "POSTGRES_PASSWORD": "must-not-appear",
    "POSTGRES_HOST": "database.internal",
    "POSTGRES_PORT": "5432",
}


def test_required_environment_reports_names_without_values(monkeypatch):
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("AI_SERVICE_BASE_URL", raising=False)

    with pytest.raises(ImproperlyConfigured) as exc_info:
        require_environment_variables(
            "POSTGRES_PASSWORD",
            "AI_SERVICE_BASE_URL",
        )

    message = str(exc_info.value)
    assert "AI_SERVICE_BASE_URL" in message
    assert "POSTGRES_PASSWORD" in message
    assert "secret" not in message.lower()


def test_required_environment_rejects_whitespace_only_values(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "   ")
    monkeypatch.setenv("POSTGRES_PASSWORD", "\t")

    with pytest.raises(ImproperlyConfigured) as exc_info:
        require_environment_variables(
            "DJANGO_SECRET_KEY",
            "POSTGRES_PASSWORD",
        )

    message = str(exc_info.value)
    assert "DJANGO_SECRET_KEY" in message
    assert "POSTGRES_PASSWORD" in message
    assert "   " not in message


def run_production_import(extra_env: dict[str, str]):
    environ = os.environ.copy()
    environ.update(PRODUCTION_ENV)
    environ.update(extra_env)
    return subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json; "
                "from config.settings.production import DATABASES; "
                "print(json.dumps(DATABASES['default']['OPTIONS']))"
            ),
        ],
        cwd=BACKEND_DIR,
        env=environ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def test_production_settings_reject_non_verified_tls():
    result = run_production_import({"POSTGRES_SSLMODE": "require"})
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "must-not-appear" not in output
    assert "database.internal" not in output


def test_production_settings_use_verify_full_ca():
    result = run_production_import(
        {
            "POSTGRES_SSLMODE": "verify-full",
            "POSTGRES_SSLROOTCERT": str(TEST_CA_PATH),
        }
    )

    assert result.returncode == 0, result.stderr
    options = json.loads(result.stdout.strip())
    assert options == {
        "connect_timeout": 5,
        "sslmode": "verify-full",
        "sslrootcert": str(TEST_CA_PATH.resolve()),
    }
