"""로컬·배포 설정의 비밀값 없는 fail-fast 검증."""

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings.base import require_environment_variables


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
