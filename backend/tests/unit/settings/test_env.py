"""로컬 ``.env`` 적재와 비밀값 비노출 규칙 검증."""

from pathlib import Path

import pytest

from config.env import (
    PostgresConnectionConfigurationError,
    build_postgres_connection_options,
    load_backend_env_lines,
    load_env_file,
    load_env_lines,
    requested_settings_module,
    should_load_env_file,
)


BACKEND_DIR = Path(__file__).resolve().parents[3]
TEST_CA_PATH = (
    BACKEND_DIR / "tests" / "fixtures" / "team_integration" / "test-ca.pem"
)


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


def test_manage_entrypoint_loads_env_before_local_default():
    source = (BACKEND_DIR / "manage.py").read_text(encoding="utf-8")

    assert source.index("load_backend_env(") < source.index(
        'setdefault("DJANGO_SETTINGS_MODULE"'
    )


@pytest.mark.parametrize("relative_path", ["config/asgi.py", "config/wsgi.py"])
def test_server_entrypoints_force_production_before_loading_env(
    relative_path: str,
):
    source = (BACKEND_DIR / relative_path).read_text(encoding="utf-8")

    assert source.index('os.environ["DJANGO_SETTINGS_MODULE"]') < source.index(
        "load_backend_env("
    )
    assert "PRODUCTION_SETTINGS_MODULE" in source
    assert "setdefault" not in source


def test_postgres_connection_options_keep_local_compatibility():
    assert build_postgres_connection_options({}) == {
        "connect_timeout": 5,
    }
    assert build_postgres_connection_options(
        {
            "POSTGRES_CONNECT_TIMEOUT": "7",
            "POSTGRES_SSLMODE": "disable",
        }
    ) == {
        "connect_timeout": 7,
        "sslmode": "disable",
    }


@pytest.mark.parametrize("sslmode", ["verify-ca", "verify-full"])
def test_postgres_verify_mode_resolves_existing_ca(
    sslmode: str,
):
    options = build_postgres_connection_options(
        {
            "POSTGRES_SSLMODE": sslmode,
            "POSTGRES_SSLROOTCERT": str(TEST_CA_PATH),
        },
    )

    assert options == {
        "connect_timeout": 5,
        "sslmode": sslmode,
        "sslrootcert": str(TEST_CA_PATH.resolve()),
    }


@pytest.mark.parametrize(
    ("environ", "reason"),
    [
        ({"POSTGRES_CONNECT_TIMEOUT": "0"}, "invalid_connect_timeout"),
        ({"POSTGRES_CONNECT_TIMEOUT": "none"}, "invalid_connect_timeout"),
        ({"POSTGRES_SSLMODE": "prefer"}, "unsupported_sslmode"),
        ({"POSTGRES_SSLMODE": "allow"}, "unsupported_sslmode"),
        ({"POSTGRES_SSLMODE": "verify-full"}, "sslrootcert_required"),
        (
            {
                "POSTGRES_SSLMODE": "disable",
                "POSTGRES_SSLROOTCERT": "must-not-appear.pem",
            },
            "sslrootcert_unexpected",
        ),
    ],
)
def test_postgres_connection_options_fail_closed_without_value_exposure(
    environ: dict[str, str],
    reason: str,
):
    with pytest.raises(PostgresConnectionConfigurationError) as exc_info:
        build_postgres_connection_options(environ)

    message = str(exc_info.value)
    assert exc_info.value.reason == reason
    assert "must-not-appear" not in message
    assert "prefer" not in message
    assert "allow" not in message


def test_postgres_verify_full_requires_ca_file():
    missing_path = TEST_CA_PATH.with_name("must-not-appear.pem")

    with pytest.raises(PostgresConnectionConfigurationError) as exc_info:
        build_postgres_connection_options(
            {
                "POSTGRES_SSLMODE": "verify-full",
                "POSTGRES_SSLROOTCERT": str(missing_path),
            }
        )

    assert exc_info.value.reason == "sslrootcert_not_found"
    assert str(missing_path) not in str(exc_info.value)


@pytest.mark.parametrize(
    "environ",
    [
        {},
        {"POSTGRES_SSLMODE": "disable"},
        {"POSTGRES_SSLMODE": "require"},
        {"POSTGRES_SSLMODE": "verify-ca"},
    ],
)
def test_production_postgres_requires_verify_full(environ: dict[str, str]):
    with pytest.raises(PostgresConnectionConfigurationError) as exc_info:
        build_postgres_connection_options(
            environ,
            require_verify_full=True,
        )

    assert exc_info.value.reason == "verify_full_required"
