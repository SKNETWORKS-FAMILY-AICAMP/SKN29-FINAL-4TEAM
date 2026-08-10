#!/usr/bin/env python3
"""Validate the State Machine Action–OpenAPI–Runtime crosswalk."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any


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


HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}
CLASSIFICATIONS = {
    "RUNTIME_IMPLEMENTED",
    "OPENAPI_CONFIRMED",
    "CONTRACT_ONLY",
    "DEFERRED",
}
EXPECTED_SOURCES = {
    "action_registry": "../codes/workflow-actions.yaml",
    "allowed_actions": "../state-machine/allowed-actions.yaml",
    "inquiry_events": "../state-machine/inquiry-events.yaml",
    "openapi": "./openapi.yaml",
}


class ContractError(ValueError):
    """Raised when the crosswalk and its source contracts are inconsistent."""


@dataclass(frozen=True)
class Operation:
    operation_id: str
    method: str
    path: str
    contract_status: str | None
    runtime_status: str | None
    event: str | None
    source: Path


@dataclass(frozen=True)
class ValidationSummary:
    total_actions: int
    classifications: dict[str, int]
    confirmed_operations: int
    runtime_implemented: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Action 23개의 Registry·State Machine·OpenAPI·Runtime 연결을 검증합니다."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="저장소 루트. 기본값은 스크립트 위치를 기준으로 자동 탐색합니다.",
    )
    return parser.parse_args()


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


def unique_index(
    items: list[Any], key: str, path: str
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for position, raw_item in enumerate(items):
        item = require_mapping(raw_item, f"{path}[{position}]")
        value = require_text(item.get(key), f"{path}[{position}].{key}")
        if value in index:
            raise ContractError(f"`{path}`에 중복 `{value}`가 있습니다.")
        index[value] = item
    return index


def _add_operations(
    inventory: dict[str, Operation], document: dict[str, Any], source: Path
) -> None:
    paths = document.get("paths", document)
    if not isinstance(paths, dict):
        return
    for route, raw_path_item in paths.items():
        if not isinstance(route, str) or not route.startswith("/"):
            continue
        if not isinstance(raw_path_item, dict):
            continue
        for method, raw_operation in raw_path_item.items():
            normalized_method = str(method).lower()
            if normalized_method not in HTTP_METHODS or not isinstance(
                raw_operation, dict
            ):
                continue
            operation_id = raw_operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                continue
            if operation_id in inventory:
                previous = inventory[operation_id]
                raise ContractError(
                    f"중복 OpenAPI operationId `{operation_id}`: "
                    f"{previous.source}, {source}"
                )
            state_machine = raw_operation.get("x-state-machine")
            event = state_machine.get("event") if isinstance(state_machine, dict) else None
            inventory[operation_id] = Operation(
                operation_id=operation_id,
                method=normalized_method.upper(),
                path=route,
                contract_status=raw_operation.get("x-contract-status"),
                runtime_status=raw_operation.get("x-runtime-status"),
                event=event if isinstance(event, str) else None,
                source=source,
            )


def load_openapi_inventory(repo_root: Path) -> dict[str, Operation]:
    api_dir = repo_root / "contracts" / "api"
    inventory: dict[str, Operation] = {}
    openapi_path = api_dir / "openapi.yaml"
    _add_operations(inventory, load_yaml(openapi_path), openapi_path)
    for path_file in sorted((api_dir / "paths").glob("*.yaml")):
        _add_operations(inventory, load_yaml(path_file), path_file)
    return inventory


def load_repository_documents(
    repo_root: Path,
) -> tuple[
    Path,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Operation],
]:
    crosswalk_path = repo_root / "contracts" / "api" / "action-operation-crosswalk.yaml"
    return (
        crosswalk_path,
        load_yaml(crosswalk_path),
        load_yaml(repo_root / "contracts" / "codes" / "workflow-actions.yaml"),
        load_yaml(repo_root / "contracts" / "state-machine" / "allowed-actions.yaml"),
        load_yaml(repo_root / "contracts" / "state-machine" / "inquiry-events.yaml"),
        load_openapi_inventory(repo_root),
    )


def _validate_evidence_paths(
    repo_root: Path,
    crosswalk_path: Path,
    action: str,
    runtime: dict[str, Any],
    require_evidence: bool,
) -> None:
    repo_root = repo_root.resolve()
    source_evidence = require_list(
        runtime.get("source_evidence"), f"actions.{action}.runtime.source_evidence"
    )
    test_evidence = require_list(
        runtime.get("test_evidence"), f"actions.{action}.runtime.test_evidence"
    )
    if require_evidence and (not source_evidence or not test_evidence):
        raise ContractError(
            f"{action}: RUNTIME_IMPLEMENTED에는 Source와 Test 증거가 모두 필요합니다."
        )
    if not require_evidence and (source_evidence or test_evidence):
        raise ContractError(
            f"{action}: Runtime 미구현 Action에는 Runtime 증거를 기록할 수 없습니다."
        )
    for raw_path in [*source_evidence, *test_evidence]:
        evidence = require_text(raw_path, f"actions.{action}.runtime.evidence")
        resolved = (crosswalk_path.parent / evidence).resolve()
        if not resolved.is_relative_to(repo_root):
            raise ContractError(f"{action}: 저장소 밖 증거 경로입니다: {evidence}")
        if not resolved.is_file():
            raise ContractError(f"{action}: 증거 파일을 찾을 수 없습니다: {evidence}")


def validate_documents(
    *,
    repo_root: Path,
    crosswalk_path: Path,
    crosswalk: dict[str, Any],
    registry: dict[str, Any],
    allowed_actions: dict[str, Any],
    inquiry_events: dict[str, Any],
    operations: dict[str, Operation],
) -> ValidationSummary:
    contract = require_mapping(crosswalk.get("contract"), "contract")
    version = require_text(contract.get("version"), "contract.version")
    repository_version = (repo_root / "contracts" / "VERSION").read_text(
        encoding="utf-8"
    ).strip()
    if version != repository_version:
        raise ContractError(
            f"Crosswalk Version `{version}`이 contracts/VERSION `{repository_version}`과 다릅니다."
        )

    sources = require_mapping(contract.get("sources"), "contract.sources")
    if sources != EXPECTED_SOURCES:
        raise ContractError(
            f"contract.sources가 승인 Source와 다릅니다: {sources!r}"
        )
    for source in sources.values():
        if not (crosswalk_path.parent / source).resolve().is_file():
            raise ContractError(f"Crosswalk Source를 찾을 수 없습니다: {source}")

    allowed_classifications = set(
        require_list(
            contract.get("allowed_classifications"),
            "contract.allowed_classifications",
        )
    )
    if allowed_classifications != CLASSIFICATIONS:
        raise ContractError(
            "allowed_classifications는 RUNTIME_IMPLEMENTED, OPENAPI_CONFIRMED, "
            "CONTRACT_ONLY, DEFERRED 전체와 정확히 일치해야 합니다."
        )

    registry_codes = require_list(registry.get("codes"), "workflow-actions.codes")
    action_items = require_list(crosswalk.get("actions"), "actions")
    action_by_code = unique_index(action_items, "action", "actions")
    if list(action_by_code) != registry_codes:
        raise ContractError(
            "Crosswalk Action 목록과 workflow-actions Registry의 집합·순서가 다릅니다."
        )

    allowed_by_code = unique_index(
        require_list(allowed_actions.get("action_catalog"), "action_catalog"),
        "code",
        "action_catalog",
    )
    event_by_code = unique_index(
        require_list(inquiry_events.get("events"), "events"), "code", "events"
    )
    if set(allowed_by_code) != set(registry_codes):
        raise ContractError("allowed-actions Action 집합이 Workflow Registry와 다릅니다.")

    classifications: Counter[str] = Counter()
    confirmed_operations = 0
    runtime_implemented = 0

    for action, item in action_by_code.items():
        event = require_text(item.get("event"), f"actions.{action}.event")
        operation_id = require_text(
            item.get("operation_id"), f"actions.{action}.operation_id"
        )
        classification = require_text(
            item.get("classification"), f"actions.{action}.classification"
        )
        if event != action:
            raise ContractError(f"{action}: event `{event}`가 Action Code와 다릅니다.")
        if classification not in CLASSIFICATIONS:
            raise ContractError(f"{action}: 허용되지 않은 분류 `{classification}`입니다.")
        classifications[classification] += 1

        allowed_operation = allowed_by_code[action].get("operation_id")
        if allowed_operation != operation_id:
            raise ContractError(
                f"{action}: allowed-actions operation_id `{allowed_operation}`와 "
                f"Crosswalk `{operation_id}`가 다릅니다."
            )
        event_item = event_by_code.get(event)
        if event_item is None:
            raise ContractError(f"{action}: inquiry-events에 Event가 없습니다.")
        external_action = require_mapping(
            event_item.get("external_action"), f"events.{event}.external_action"
        )
        if external_action.get("exposed") is not True:
            raise ContractError(f"{action}: 외부 Action Event가 exposed=true가 아닙니다.")
        if external_action.get("operation_id") != operation_id:
            raise ContractError(
                f"{action}: inquiry-events operation_id가 Crosswalk와 다릅니다."
            )

        openapi = require_mapping(item.get("openapi"), f"actions.{action}.openapi")
        runtime = require_mapping(item.get("runtime"), f"actions.{action}.runtime")
        confirmed = openapi.get("confirmed")
        implemented = runtime.get("implemented")
        if not isinstance(confirmed, bool) or not isinstance(implemented, bool):
            raise ContractError(f"{action}: confirmed와 implemented는 boolean이어야 합니다.")

        requires_openapi = classification in {
            "RUNTIME_IMPLEMENTED",
            "OPENAPI_CONFIRMED",
        }
        if confirmed is not requires_openapi:
            raise ContractError(
                f"{action}: `{classification}`과 openapi.confirmed 값이 맞지 않습니다."
            )
        if implemented is not (classification == "RUNTIME_IMPLEMENTED"):
            raise ContractError(
                f"{action}: `{classification}`과 runtime.implemented 값이 맞지 않습니다."
            )

        operation = operations.get(operation_id)
        if requires_openapi:
            confirmed_operations += 1
            if operation is None:
                raise ContractError(
                    f"{action}: OpenAPI operationId `{operation_id}`가 없습니다."
                )
            expected_method = require_text(
                openapi.get("method"), f"actions.{action}.openapi.method"
            )
            expected_path = require_text(
                openapi.get("path"), f"actions.{action}.openapi.path"
            )
            if (operation.method, operation.path) != (expected_method, expected_path):
                raise ContractError(
                    f"{action}: HTTP 연결이 실제 OpenAPI와 다릅니다. "
                    f"expected={expected_method} {expected_path}, "
                    f"actual={operation.method} {operation.path}"
                )
            if openapi.get("contract_status") != operation.contract_status:
                raise ContractError(f"{action}: OpenAPI 계약 상태가 실제 정의와 다릅니다.")
            if operation.event is not None and operation.event != event:
                raise ContractError(
                    f"{action}: OpenAPI x-state-machine Event `{operation.event}`가 다릅니다."
                )
            if classification == "OPENAPI_CONFIRMED" and (
                operation.runtime_status != "NOT_IMPLEMENTED"
            ):
                raise ContractError(
                    f"{action}: OPENAPI_CONFIRMED Operation은 "
                    "x-runtime-status=NOT_IMPLEMENTED여야 합니다."
                )
            if classification == "RUNTIME_IMPLEMENTED" and (
                operation.runtime_status == "NOT_IMPLEMENTED"
            ):
                raise ContractError(
                    f"{action}: Runtime 구현 증거와 OpenAPI NOT_IMPLEMENTED가 충돌합니다."
                )
        else:
            if operation is not None:
                raise ContractError(
                    f"{action}: 정확한 OpenAPI Operation이 있는데 `{classification}`로 분류됐습니다."
                )
            if openapi.get("method") is not None or openapi.get("path") is not None:
                raise ContractError(f"{action}: 미확정 OpenAPI의 Method·Path는 null이어야 합니다.")
            if openapi.get("contract_status") != "MISSING_EXACT_OPERATION":
                raise ContractError(
                    f"{action}: 미확정 OpenAPI 상태는 MISSING_EXACT_OPERATION이어야 합니다."
                )

        if implemented:
            runtime_implemented += 1
        _validate_evidence_paths(
            repo_root,
            crosswalk_path,
            action,
            runtime,
            require_evidence=implemented,
        )

    actual_counts = {name: classifications[name] for name in CLASSIFICATIONS}
    summary = require_mapping(crosswalk.get("summary"), "summary")
    if summary.get("total_actions") != len(action_by_code):
        raise ContractError("summary.total_actions가 실제 Action 수와 다릅니다.")
    for name, count in actual_counts.items():
        if summary.get(name) != count:
            raise ContractError(f"summary.{name}이 실제 분류 수 `{count}`와 다릅니다.")

    return ValidationSummary(
        total_actions=len(action_by_code),
        classifications=actual_counts,
        confirmed_operations=confirmed_operations,
        runtime_implemented=runtime_implemented,
    )


def validate_repository(repo_root: Path) -> ValidationSummary:
    root = repo_root.resolve()
    (
        crosswalk_path,
        crosswalk,
        registry,
        allowed_actions,
        inquiry_events,
        operations,
    ) = load_repository_documents(root)
    return validate_documents(
        repo_root=root,
        crosswalk_path=crosswalk_path,
        crosswalk=crosswalk,
        registry=registry,
        allowed_actions=allowed_actions,
        inquiry_events=inquiry_events,
        operations=operations,
    )


def main() -> int:
    args = parse_args()
    try:
        result = validate_repository(args.repo_root)
    except (ContractError, OSError) as exc:
        print(f"Contract Crosswalk validation FAILED: {exc}", file=sys.stderr)
        return 1

    print("Contract Crosswalk validation PASSED")
    print(f"- total actions: {result.total_actions}")
    for classification in sorted(CLASSIFICATIONS):
        print(f"- {classification}: {result.classifications[classification]}")
    print(f"- confirmed OpenAPI operations: {result.confirmed_operations}")
    print(f"- runtime implemented: {result.runtime_implemented}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
