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
