"""Shared helpers for standalone contract validators."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator


try:
    import yaml as _pyyaml

    def _yaml_load(text: str) -> Any:
        return _pyyaml.safe_load(text)

    _YAML_ERRORS: tuple[type[BaseException], ...] = (_pyyaml.YAMLError,)
except ImportError:
    try:
        from ruamel.yaml import YAML as _RuamelYAML

        _ruamel_yaml = _RuamelYAML(typ="safe")

        def _yaml_load(text: str) -> Any:
            return _ruamel_yaml.load(text)

        _YAML_ERRORS = (Exception,)
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SystemExit(
            "PyYAML 또는 ruamel.yaml이 필요합니다. "
            "`python -m pip install PyYAML==6.0.3`으로 설치해 주세요."
        ) from exc


class ContractError(ValueError):
    """Raised when a machine-readable contract is inconsistent."""


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ContractError(f"계약 파일을 찾을 수 없습니다: {path}")
    try:
        document = _yaml_load(path.read_text(encoding="utf-8"))
    except _YAML_ERRORS as exc:
        raise ContractError(f"YAML 문법 오류: {path}\n{exc}") from exc
    if not isinstance(document, dict):
        raise ContractError(f"YAML 최상위 값은 객체여야 합니다: {path}")
    return document


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"JSON 객체에 중복 Key `{key}`가 있습니다.")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise ContractError(f"JSON 예시를 찾을 수 없습니다: {path}")
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractError(f"JSON 문법 오류: {path}\n{exc}") from exc


def require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"`{path}`는 객체여야 합니다.")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractError(f"`{path}`는 배열이어야 합니다.")
    return value


def require_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"`{path}`에는 비어 있지 않은 문자열이 필요합니다.")
    return value


def unique_text_list(value: Any, path: str) -> list[str]:
    raw_items = require_list(value, path)
    items = [require_text(item, f"{path}[{index}]") for index, item in enumerate(raw_items)]
    if len(items) != len(set(items)):
        raise ContractError(f"`{path}`에 중복 Code가 있습니다.")
    return items


def walk(
    value: Any, path: tuple[str | int, ...] = ()
) -> Iterator[tuple[tuple[str | int, ...], Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from walk(item, (*path, str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk(item, (*path, index))
