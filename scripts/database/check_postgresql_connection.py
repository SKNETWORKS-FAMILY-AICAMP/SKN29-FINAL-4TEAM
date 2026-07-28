"""환경변수 기반 PostgreSQL 연결을 읽기 전용으로 점검한다."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import psycopg


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPOSITORY_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config.env import load_backend_env


REQUIRED_ENV_KEYS = (
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
)
READ_ONLY_QUERIES = (
    ("select_one", "SELECT 1"),
    ("server_version", "SHOW server_version"),
    ("server_version_num", "SHOW server_version_num"),
    ("database_timezone", "SHOW TimeZone"),
    (
        "default_transaction_read_only",
        "SHOW default_transaction_read_only",
    ),
)


class ConfigurationError(ValueError):
    """연결 시도 전에 발견한 환경 설정 오류."""

    def __init__(self, missing_keys: list[str] | None = None):
        super().__init__("PostgreSQL environment is not configured")
        self.missing_keys = missing_keys or []


def load_connection_options(
    environ: Mapping[str, str],
) -> dict[str, Any]:
    missing_keys = [
        key
        for key in REQUIRED_ENV_KEYS
        if not environ.get(key, "").strip()
    ]
    if missing_keys:
        raise ConfigurationError(missing_keys)

    try:
        port = int(environ["POSTGRES_PORT"])
    except ValueError as exc:
        raise ConfigurationError() from exc
    if not 1 <= port <= 65535:
        raise ConfigurationError()

    return {
        "dbname": environ["POSTGRES_DB"],
        "user": environ["POSTGRES_USER"],
        "password": environ["POSTGRES_PASSWORD"],
        "host": environ["POSTGRES_HOST"],
        "port": port,
        "connect_timeout": 5,
        "options": "-c default_transaction_read_only=on",
    }


def inspect_postgresql(
    connection_options: dict[str, Any],
    connect: Callable[..., Any],
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    with connect(**connection_options) as connection:
        with connection.cursor() as cursor:
            for key, query in READ_ONLY_QUERIES:
                cursor.execute(query)
                values[key] = cursor.fetchone()[0]

    return {
        "status": "CONNECTED",
        "vendor": "PostgreSQL",
        **values,
    }


def run_check(
    environ: Mapping[str, str],
    connect: Callable[..., Any] = psycopg.connect,
) -> tuple[dict[str, Any], int]:
    try:
        connection_options = load_connection_options(environ)
    except ConfigurationError as exc:
        return (
            {
                "status": "NOT_CONFIGURED",
                "missing_keys": exc.missing_keys,
                "message": (
                    "필수 PostgreSQL 환경변수를 확인하세요. "
                    "비밀값은 출력하지 않습니다."
                ),
            },
            2,
        )

    try:
        return inspect_postgresql(connection_options, connect), 0
    except Exception as exc:  # noqa: BLE001 - CLI 진단 결과로 변환한다.
        return (
            {
                "status": "CONNECTION_FAILED",
                "error_type": type(exc).__name__,
                "message": (
                    "PostgreSQL 연결 또는 읽기 전용 조회에 실패했습니다. "
                    "비밀값·DSN·접속 주소는 출력하지 않습니다."
                ),
            },
            1,
        )


def main() -> int:
    load_backend_env()
    result, exit_code = run_check(os.environ)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
