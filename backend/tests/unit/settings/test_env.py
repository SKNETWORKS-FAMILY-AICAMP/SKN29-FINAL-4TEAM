"""로컬 ``.env`` 적재와 비밀값 비노출 규칙 검증."""

from pathlib import Path

import pytest

from config.env import (
    load_backend_env_lines,
    load_env_file,
    load_env_lines,
    requested_settings_module,
    should_load_env_file,
)


BACKEND_DIR = Path(__file__).resolve().parents[3]


def test_load_env_file_loads_missing_nonempty_keys_without_overriding_existing(
):
    environ = {"POSTGRES_HOST": "team-db.internal"}

    loaded = load_env_lines(
        [
            "# local only",
            "POSTGRES_HOST=127.0.0.1",
            'DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1"',
            "DJANGO_DEBUG='true'",
            "POSTGRES_PASSWORD=",
        ],
        environ=environ,
    )

    assert loaded == {"DJANGO_ALLOWED_HOSTS", "DJANGO_DEBUG"}
    assert environ == {
        "POSTGRES_HOST": "team-db.internal",
        "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
        "DJANGO_DEBUG": "true",
    }


def test_load_env_file_is_optional():
    environ: dict[str, str] = {}

    assert load_env_file(
        Path(__file__).with_name("missing.env"),
        environ=environ,
    ) == set()
    assert environ == {}


@pytest.mark.parametrize(
    "invalid_line",
    [
        "INVALID-KEY=must-not-appear",
        "POSTGRES_PASSWORD must-not-appear",
    ],
)
def test_load_env_file_error_does_not_expose_value(invalid_line: str):
    secret_value = "must-not-appear"

    with pytest.raises(ValueError) as exc_info:
        load_env_lines([invalid_line], environ={})

    assert "line=1" in str(exc_info.value)
    assert secret_value not in str(exc_info.value)


@pytest.mark.parametrize(
    ("argv", "environ", "expected"),
    [
        (
            ["manage.py", "check", "--settings=config.settings.test"],
            {},
            "config.settings.test",
        ),
        (
            ["manage.py", "check", "--settings", "config.settings.local"],
            {},
            "config.settings.local",
        ),
        (
            ["manage.py", "check", "--settings=config.settings.local"],
            {"DJANGO_SETTINGS_MODULE": "config.settings.production"},
            "config.settings.local",
        ),
    ],
)
def test_requested_settings_module(
    argv: list[str],
    environ: dict[str, str],
    expected: str,
):
    assert requested_settings_module(
        argv,
        environ=environ,
    ) == expected


def test_test_settings_do_not_load_personal_env_file():
    assert should_load_env_file("config.settings.test") is False
    assert should_load_env_file("config.settings.local") is True
    assert should_load_env_file(None) is True


def test_env_selected_test_settings_loads_only_settings_module():
    environ: dict[str, str] = {}

    loaded = load_backend_env_lines(
        [
            "DJANGO_SETTINGS_MODULE=config.settings.test",
            "DJANGO_LOG_FILE=must-not-be-loaded.log",
            "POSTGRES_PASSWORD=must-not-be-loaded",
        ],
        environ=environ,
    )

    assert loaded == {"DJANGO_SETTINGS_MODULE"}
    assert environ == {
        "DJANGO_SETTINGS_MODULE": "config.settings.test",
    }


def test_explicit_test_settings_ignores_all_personal_env_values():
    environ: dict[str, str] = {}

    loaded = load_backend_env_lines(
        [
            "DJANGO_SETTINGS_MODULE=config.settings.local",
            "DJANGO_LOG_LEVEL=DEBUG",
            "POSTGRES_PASSWORD missing-separator-must-be-ignored",
        ],
        settings_module="config.settings.test",
        environ=environ,
    )

    assert loaded == set()
    assert environ == {}


@pytest.mark.parametrize(
    "relative_path",
    ["manage.py", "config/asgi.py", "config/wsgi.py"],
)
def test_runtime_entrypoints_load_env_before_setting_default(
    relative_path: str,
):
    source = (BACKEND_DIR / relative_path).read_text(encoding="utf-8")

    assert source.index("load_backend_env(") < source.index(
        'setdefault("DJANGO_SETTINGS_MODULE"'
    )
