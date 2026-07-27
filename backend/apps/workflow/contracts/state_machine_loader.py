"""`contracts/state-machine` YAML 계약을 안전하게 읽는다."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CONTRACT_DIR = REPOSITORY_ROOT / "contracts" / "state-machine"
CONTRACT_FILES = {
    "states": "inquiry-states.yaml",
    "events": "inquiry-events.yaml",
    "transitions": "transition-rules.yaml",
    "guards": "transition-guards.yaml",
    "allowed_actions": "allowed-actions.yaml",
    "role_permissions": "role-permissions.yaml",
}


class StateMachineContractLoadError(ValueError):
    """계약 파일을 안전하게 읽을 수 없을 때 발생한다."""


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """중복 키를 조용히 덮어쓰지 않는 SafeLoader."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicated = key in result
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from exc
        if duplicated:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key ({key!r})",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    """YAML 파일 하나를 비어 있지 않은 mapping으로 읽는다."""

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise StateMachineContractLoadError(
            f"{path}: 계약 파일을 읽을 수 없습니다."
        ) from exc

    if not text.strip():
        raise StateMachineContractLoadError(
            f"{path}: 계약 파일이 비어 있습니다."
        )

    try:
        document = yaml.load(text, Loader=_UniqueKeySafeLoader)
    except yaml.YAMLError as exc:
        raise StateMachineContractLoadError(
            f"{path}: 올바른 YAML 문서가 아닙니다."
        ) from exc

    if not isinstance(document, dict) or not document:
        raise StateMachineContractLoadError(
            f"{path}: 최상위 값은 비어 있지 않은 mapping이어야 합니다."
        )
    if not all(isinstance(key, str) and key.strip() for key in document):
        raise StateMachineContractLoadError(
            f"{path}: 최상위 키는 비어 있지 않은 문자열이어야 합니다."
        )
    return document


def load_contract_documents(
    contract_dir: Path | str = DEFAULT_CONTRACT_DIR,
) -> dict[str, dict[str, Any]]:
    """필수 계약 파일을 모두 읽되 의미 검증은 수행하지 않는다."""

    directory = Path(contract_dir)
    if not directory.is_dir():
        raise StateMachineContractLoadError(
            f"{directory}: 계약 디렉터리가 없습니다."
        )

    return {
        contract_name: load_yaml_mapping(directory / filename)
        for contract_name, filename in CONTRACT_FILES.items()
    }


def load_state_machine_contract(
    contract_dir: Path | str = DEFAULT_CONTRACT_DIR,
) -> Mapping[str, Mapping[str, Any]]:
    """모든 계약을 읽고 구조와 교차 참조를 fail-closed로 검증한다."""

    documents = load_contract_documents(contract_dir)

    # 순환 import 없이 loader와 validator를 독립 테스트할 수 있게 한다.
    from .contract_validator import validate_contract_documents

    validate_contract_documents(documents)
    return documents
