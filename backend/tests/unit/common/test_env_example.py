"""환경변수 예시 파일의 키 존재와 비밀값 비노출 검증."""

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[3]
ENV_EXAMPLE_PATH = BACKEND_DIR / ".env.example"
REQUIRED_KEYS = {
    "DJANGO_SETTINGS_MODULE",
    "DJANGO_SECRET_KEY",
    "DJANGO_DEBUG",
    "DJANGO_TIME_ZONE",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_LOG_LEVEL",
    "DJANGO_LOG_FILE",
    "DJANGO_DEMO_LOGIN_ENABLED",
    "DJANGO_DEMO_LOGIN_CODES",
    "JWT_ACCESS_TTL_MINUTES",
    "JWT_REFRESH_TTL_HOURS",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_CONNECT_TIMEOUT",
    "POSTGRES_SSLMODE",
    "POSTGRES_SSLROOTCERT",
    "DJANGO_CORS_ALLOWED_ORIGINS",
    "AI_SERVICE_BASE_URL",
    "AI_HANDOFF_INTERNAL_TOKEN",
}

SAFE_PUBLIC_DEFAULTS = {
    "DJANGO_SETTINGS_MODULE": "config.settings.local",
    "DJANGO_DEBUG": "true",
    "DJANGO_TIME_ZONE": "Asia/Seoul",
    "DJANGO_LOG_LEVEL": "INFO",
    "DJANGO_LOG_FILE": ".runtime/logs/backend.jsonl",
    "DJANGO_DEMO_LOGIN_ENABLED": "false",
    "JWT_ACCESS_TTL_MINUTES": "60",
    "JWT_REFRESH_TTL_HOURS": "168",
    "AI_SERVICE_BASE_URL": "http://127.0.0.1:8001",
    "POSTGRES_DB": "waterbridge",
    "POSTGRES_USER": "watercare_app",
    "POSTGRES_HOST": "127.0.0.1",
    "POSTGRES_PORT": "5432",
    "POSTGRES_CONNECT_TIMEOUT": "5",
    "POSTGRES_SSLMODE": "disable",
}


def load_env_example() -> dict[str, str]:
    entries: dict[str, str] = {}

    for raw_line in ENV_EXAMPLE_PATH.read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        key, separator, value = line.partition("=")
        assert separator == "=", f"환경변수 형식이 아닙니다: {raw_line}"
        assert key not in entries, f"환경변수 키가 중복됩니다: {key}"
        entries[key] = value

    return entries


def test_env_example_contains_required_backend_keys():
    entries = load_env_example()

    assert REQUIRED_KEYS <= set(entries)


def test_env_example_contains_safe_project_defaults():
    entries = load_env_example()

    assert entries
    assert all(entries[key] == value for key, value in SAFE_PUBLIC_DEFAULTS.items())


def test_env_example_uses_non_secret_replacement_markers():
    entries = load_env_example()

    assert entries["DJANGO_SECRET_KEY"].startswith("replace-with-")
    assert entries["POSTGRES_PASSWORD"].startswith("replace-with-")
    assert entries["AI_HANDOFF_INTERNAL_TOKEN"].startswith("replace-with-")
    assert entries["POSTGRES_SSLROOTCERT"] == ""
