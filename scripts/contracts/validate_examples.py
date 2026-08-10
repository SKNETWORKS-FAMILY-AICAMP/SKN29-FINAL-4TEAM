#!/usr/bin/env python3
"""Validate JSON examples and their OpenAPI externalValue references."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Any
from uuid import UUID

from validation_support import (
    ContractError,
    load_json,
    load_yaml,
    require_list,
    require_mapping,
    walk,
)


JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")


@dataclass(frozen=True)
class ValidationSummary:
    api_examples: int
    referenced_examples: int
    integration_examples: int
    wrapped_responses: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="JSON 예시의 문법·OpenAPI 참조·공통 응답 Wrapper를 검증합니다."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    return parser.parse_args()


def _validate_response_wrapper(path: Path, payload: dict[str, Any]) -> bool:
    if "success" not in payload:
        return False
    expected_keys = {"success", "data", "error", "metadata"}
    if set(payload) != expected_keys:
        raise ContractError(f"공통 응답 Wrapper Key가 다릅니다: {path}")
    if not isinstance(payload["success"], bool):
        raise ContractError(f"success는 boolean이어야 합니다: {path}")
    metadata = require_mapping(payload["metadata"], f"{path}.metadata")
    correlation_id = metadata.get("correlation_id")
    try:
        UUID(str(correlation_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ContractError(f"유효하지 않은 correlation_id입니다: {path}") from exc
    if payload["success"]:
        if payload["data"] is None or payload["error"] is not None:
            raise ContractError(f"성공 응답의 data/error 조합이 잘못됐습니다: {path}")
    else:
        if payload["data"] is not None:
            raise ContractError(f"실패 응답 data는 null이어야 합니다: {path}")
        error = require_mapping(payload["error"], f"{path}.error")
        if set(error) != {"code", "message", "details"}:
            raise ContractError(f"실패 응답 error Key가 다릅니다: {path}")
    return True


def validate_repository(repo_root: Path) -> ValidationSummary:
    root = repo_root.resolve()
    api_dir = root / "contracts" / "api"
    api_examples_dir = api_dir / "examples"
    integration_dir = root / "contracts" / "examples"
    api_example_paths = sorted(api_examples_dir.rglob("*.json"))
    integration_paths = sorted(integration_dir.glob("*.json"))
    if not api_example_paths:
        raise ContractError("API JSON 예시가 없습니다.")

    referenced: set[Path] = set()
    for yaml_path in sorted(api_dir.rglob("*.yaml")):
        document = load_yaml(yaml_path)
        for node_path, value in walk(document):
            if node_path and node_path[-1] == "externalValue":
                if not isinstance(value, str) or not value.strip():
                    raise ContractError(f"비어 있는 externalValue입니다: {yaml_path}")
                target = (yaml_path.parent / value).resolve()
                if not target.is_relative_to(api_examples_dir.resolve()):
                    raise ContractError(
                        f"examples 밖 externalValue는 허용하지 않습니다: {yaml_path}: {value}"
                    )
                if not target.is_file():
                    raise ContractError(f"externalValue 대상이 없습니다: {yaml_path}: {value}")
                load_json(target)
                referenced.add(target)

    actual = {path.resolve() for path in api_example_paths}
    unreferenced = actual - referenced
    if unreferenced:
        names = sorted(path.relative_to(api_examples_dir).as_posix() for path in unreferenced)
        raise ContractError(f"OpenAPI에서 참조하지 않는 JSON 예시가 있습니다: {names}")

    wrapped_responses = 0
    for path in api_example_paths:
        raw_text = path.read_text(encoding="utf-8")
        if JWT_PATTERN.search(raw_text):
            raise ContractError(f"실제 JWT 형태 문자열이 포함된 예시입니다: {path}")
        payload = load_json(path)
        if not isinstance(payload, dict):
            raise ContractError(f"JSON 예시 최상위 값은 객체여야 합니다: {path}")
        if _validate_response_wrapper(path, payload):
            wrapped_responses += 1

    state_codes = set(
        item["code"]
        for item in require_list(
            load_yaml(root / "contracts" / "state-machine" / "inquiry-states.yaml").get("states"),
            "inquiry-states.states",
        )
    )
    action_codes = set(
        require_list(
            load_yaml(root / "contracts" / "codes" / "workflow-actions.yaml").get("codes"),
            "workflow-actions.codes",
        )
    )
    for path in integration_paths:
        payload = load_json(path)
        if not isinstance(payload, dict):
            raise ContractError(f"통합 예시 최상위 값은 객체여야 합니다: {path}")
        if "scenario" in payload:
            require_list(payload.get("steps"), f"{path}.steps")
        if path.name == "state-conflict.json":
            current = require_mapping(payload.get("current"), f"{path}.current")
            expected = require_mapping(
                payload.get("expected_response"), f"{path}.expected_response"
            )
            if current.get("status") not in state_codes:
                raise ContractError(f"미등록 현재 상태를 사용한 예시입니다: {path}")
            for action in require_list(current.get("allowed_actions"), f"{path}.allowed_actions"):
                if action not in action_codes:
                    raise ContractError(f"미등록 Action을 사용한 예시입니다: {path}: {action}")
            if expected.get("http_status") != 409:
                raise ContractError(f"상태 충돌 예시는 HTTP 409여야 합니다: {path}")

    return ValidationSummary(
        api_examples=len(api_example_paths),
        referenced_examples=len(referenced),
        integration_examples=len(integration_paths),
        wrapped_responses=wrapped_responses,
    )


def main() -> int:
    args = parse_args()
    try:
        result = validate_repository(args.repo_root)
    except (ContractError, OSError) as exc:
        print(f"Contract Example validation FAILED: {exc}", file=sys.stderr)
        return 1
    print("Contract Example validation PASSED")
    print(f"- API JSON examples: {result.api_examples}")
    print(f"- referenced examples: {result.referenced_examples}")
    print(f"- integration examples: {result.integration_examples}")
    print(f"- wrapped responses: {result.wrapped_responses}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
