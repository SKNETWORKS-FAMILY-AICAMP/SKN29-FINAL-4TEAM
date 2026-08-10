"""백엔드 로컬 ``.env`` 파일을 process environment에 안전하게 적재한다."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = BACKEND_DIR / ".env"
ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TEST_SETTINGS_MODULE = "config.settings.test"
POSTGRES_SSL_MODES = frozenset(
    {"disable", "require", "verify-ca", "verify-full"}
)
POSTGRES_VERIFY_SSL_MODES = frozenset({"verify-ca", "verify-full"})
DEFAULT_POSTGRES_CONNECT_TIMEOUT = 5


class PostgresConnectionConfigurationError(ValueError):
    """값을 노출하지 않는 PostgreSQL 연결 옵션 오류."""

    def __init__(
        self,
        reason: str,
        *,
        missing_keys: Iterable[str] = (),
    ):
        super().__init__(
            "PostgreSQL connection configuration error: "
            f"reason={reason}"
        )
        self.reason = reason
        self.missing_keys = tuple(sorted(set(missing_keys)))


def build_postgres_connection_options(
    environ: Mapping[str, str],
    *,
    base_dir: Path = BACKEND_DIR,
    require_verify_full: bool = False,
) -> dict[str, str | int]:
    """Django와 psycopg가 공유하는 Timeout·TLS 옵션을 검증한다.

    로컬 환경은 SSL 키가 없어도 기존 동작을 유지한다. 원격 배포에서
    ``require_verify_full``을 사용하면 DNS·CA 검증 없는 연결을
    설정 단계에서 차단한다. 오류에는 입력값이나 인증서 경로를 넣지
    않는다.
    """

    raw_timeout = environ.get("POSTGRES_CONNECT_TIMEOUT", "").strip()
    if raw_timeout:
        try:
            connect_timeout = int(raw_timeout)
        except ValueError as exc:
            raise PostgresConnectionConfigurationError(
                "invalid_connect_timeout"
            ) from exc
        if connect_timeout <= 0:
            raise PostgresConnectionConfigurationError(
                "invalid_connect_timeout"
            )
    else:
        connect_timeout = DEFAULT_POSTGRES_CONNECT_TIMEOUT

    raw_sslmode = environ.get("POSTGRES_SSLMODE", "").strip()
    sslmode = raw_sslmode.lower()
    raw_rootcert = environ.get("POSTGRES_SSLROOTCERT", "").strip()

    if require_verify_full and sslmode != "verify-full":
        missing_keys = ()
        if not raw_sslmode:
            missing_keys = ("POSTGRES_SSLMODE",)
        raise PostgresConnectionConfigurationError(
            "verify_full_required",
            missing_keys=missing_keys,
        )

    if sslmode and sslmode not in POSTGRES_SSL_MODES:
        raise PostgresConnectionConfigurationError(
            "unsupported_sslmode"
        )

    if sslmode in POSTGRES_VERIFY_SSL_MODES and not raw_rootcert:
        raise PostgresConnectionConfigurationError(
            "sslrootcert_required",
            missing_keys=("POSTGRES_SSLROOTCERT",),
        )

    if raw_rootcert and sslmode not in POSTGRES_VERIFY_SSL_MODES:
        raise PostgresConnectionConfigurationError(
            "sslrootcert_unexpected"
        )

    options: dict[str, str | int] = {
        "connect_timeout": connect_timeout,
    }
    if sslmode:
        options["sslmode"] = sslmode
    if raw_rootcert:
        rootcert_path = Path(raw_rootcert)
        if not rootcert_path.is_absolute():
            rootcert_path = base_dir / rootcert_path
        rootcert_path = rootcert_path.resolve()
        if not rootcert_path.is_file():
            raise PostgresConnectionConfigurationError(
                "sslrootcert_not_found"
            )
        options["sslrootcert"] = str(rootcert_path)

    return options


def _parse_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_env_lines(
    lines: Iterable[str],
    *,
    environ: MutableMapping[str, str] | None = None,
) -> set[str]:
    """``.env`` 행을 기존 환경변수를 덮어쓰지 않고 적재한다.

    실제 값은 반환하거나 오류 메시지에 포함하지 않는다. 잘못된 행은
    줄 번호와 오류 종류만 알려 비밀값이 터미널·로그에 노출되지 않게
    한다.
    """

    target = os.environ if environ is None else environ
    loaded_keys: set[str] = set()
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        key, separator, raw_value = line.partition("=")
        key = key.strip()
        if separator != "=":
            raise ValueError(
                f".env 형식 오류: line={line_number}, reason=missing_separator"
            )
        if not ENV_KEY_PATTERN.fullmatch(key):
            raise ValueError(
                f".env 형식 오류: line={line_number}, reason=invalid_key"
            )

        value = _parse_value(raw_value)
        if value and key not in target:
            target[key] = value
            loaded_keys.add(key)

    return loaded_keys


def load_env_file(
    path: Path,
    *,
    environ: MutableMapping[str, str] | None = None,
) -> set[str]:
    """``path``가 있으면 읽고, 없으면 아무 작업 없이 반환한다."""

    if not path.is_file():
        return set()
    return load_env_lines(
        path.read_text(encoding="utf-8-sig").splitlines(),
        environ=environ,
    )


def requested_settings_module(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """process environment와 Django CLI에서 요청한 settings를 찾는다."""

    arguments = list(argv or ())
    for index, argument in enumerate(arguments):
        if argument.startswith("--settings="):
            return argument.partition("=")[2] or None
        if argument == "--settings" and index + 1 < len(arguments):
            return arguments[index + 1] or None

    source = os.environ if environ is None else environ
    return source.get("DJANGO_SETTINGS_MODULE") or None


def should_load_env_file(settings_module: str | None) -> bool:
    """자동 테스트 설정에는 개인 ``.env``를 섞지 않는다."""

    return settings_module != TEST_SETTINGS_MODULE


def load_backend_env_lines(
    lines: Iterable[str],
    *,
    settings_module: str | None = None,
    environ: MutableMapping[str, str] | None = None,
) -> set[str]:
    """백엔드 ``.env`` 행을 설정 모듈까지 판별한 뒤 선택적으로 합친다.

    ``.env`` 자체가 테스트 설정을 선택하면 ``DJANGO_SETTINGS_MODULE``만
    반영한다. 로그 경로·DB 접속값 같은 개인 환경값은 테스트 process에
    섞지 않는다.
    """

    target = os.environ if environ is None else environ
    explicit_settings = (
        settings_module
        or target.get("DJANGO_SETTINGS_MODULE")
    )
    if not should_load_env_file(explicit_settings):
        return set()

    file_values: dict[str, str] = {}
    load_env_lines(lines, environ=file_values)

    effective_settings = (
        explicit_settings
        or file_values.get("DJANGO_SETTINGS_MODULE")
    )
    if not should_load_env_file(effective_settings):
        if (
            "DJANGO_SETTINGS_MODULE" not in target
            and file_values.get("DJANGO_SETTINGS_MODULE")
            == TEST_SETTINGS_MODULE
        ):
            target["DJANGO_SETTINGS_MODULE"] = TEST_SETTINGS_MODULE
            return {"DJANGO_SETTINGS_MODULE"}
        return set()

    loaded_keys: set[str] = set()
    for key, value in file_values.items():
        if value and key not in target:
            target[key] = value
            loaded_keys.add(key)
    return loaded_keys


def load_backend_env(
    *,
    settings_module: str | None = None,
    environ: MutableMapping[str, str] | None = None,
    path: Path | None = None,
) -> set[str]:
    """백엔드 루트의 Git 제외 ``.env``를 선택적으로 적재한다."""

    target = os.environ if environ is None else environ
    explicit_settings = (
        settings_module
        or target.get("DJANGO_SETTINGS_MODULE")
    )
    if not should_load_env_file(explicit_settings):
        return set()

    env_path = DEFAULT_ENV_PATH if path is None else path
    if not env_path.is_file():
        return set()
    return load_backend_env_lines(
        env_path.read_text(encoding="utf-8-sig").splitlines(),
        settings_module=settings_module,
        environ=target,
    )
