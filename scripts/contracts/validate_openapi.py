#!/usr/bin/env python3
"""Validate local OpenAPI references, paths, operations, and parameters."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Any

from validation_support import ContractError, load_yaml, require_mapping, require_text, walk


HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
PATH_PARAMETER = re.compile(r"\{([^{}]+)\}")


@dataclass(frozen=True)
class ValidationSummary:
    yaml_files: int
    references: int
    paths: int
    operations: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OpenAPI YAML의 Local Ref·Operation ID·Path Parameter를 검증합니다."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    return parser.parse_args()


def _json_pointer(document: Any, fragment: str, ref: str) -> Any:
    if not fragment:
        return document
    if not fragment.startswith("/"):
        raise ContractError(f"지원하지 않는 Ref Fragment입니다: {ref}")
    current = document
    for raw_token in fragment[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise ContractError(f"Ref Fragment를 찾을 수 없습니다: {ref}")
    return current


def _resolve_ref(
    api_dir: Path,
    source: Path,
    ref: str,
    cache: dict[Path, dict[str, Any]],
) -> tuple[Path, Any]:
    if "://" in ref:
        raise ContractError(f"Remote $ref는 허용하지 않습니다: {source}: {ref}")
    file_part, separator, fragment = ref.partition("#")
    target = source if not file_part else (source.parent / file_part).resolve()
    if not target.is_relative_to(api_dir.resolve()):
        raise ContractError(f"API 디렉토리 밖 $ref입니다: {source}: {ref}")
    if target.suffix.lower() not in {".yaml", ".yml"}:
        raise ContractError(f"YAML이 아닌 $ref입니다: {source}: {ref}")
    if target not in cache:
        cache[target] = load_yaml(target)
    return target, _json_pointer(cache[target], fragment if separator else "", ref)


def _parameter_names(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    names: set[str] = set()
    for item in items:
        if isinstance(item, dict) and item.get("in") == "path":
            name = item.get("name")
            if isinstance(name, str):
                if item.get("required") is not True:
                    raise ContractError(f"Path Parameter `{name}`는 required=true여야 합니다.")
                names.add(name)
    return names


def validate_repository(repo_root: Path) -> ValidationSummary:
    root = repo_root.resolve()
    api_dir = root / "contracts" / "api"
    root_path = api_dir / "openapi.yaml"
    yaml_paths = sorted(api_dir.rglob("*.yaml"))
    cache = {path.resolve(): load_yaml(path) for path in yaml_paths}
    openapi = cache[root_path.resolve()]

    if openapi.get("openapi") != "3.1.0":
        raise ContractError("OpenAPI Version은 3.1.0이어야 합니다.")
    info = require_mapping(openapi.get("info"), "openapi.info")
    require_text(info.get("title"), "openapi.info.title")
    require_text(info.get("version"), "openapi.info.version")

    reference_count = 0
    for source, document in cache.items():
        for node_path, value in walk(document):
            if node_path and node_path[-1] == "$ref":
                ref = require_text(value, f"{source}:$ref")
                _resolve_ref(api_dir, source, ref, cache)
                reference_count += 1

    root_paths = require_mapping(openapi.get("paths"), "openapi.paths")
    operation_ids: dict[str, str] = {}
    operation_count = 0
    for route, raw_path_item in root_paths.items():
        if not isinstance(route, str) or not route.startswith("/"):
            raise ContractError(f"유효하지 않은 OpenAPI Path입니다: {route!r}")
        path_item = require_mapping(raw_path_item, f"paths.{route}")
        if "$ref" in path_item:
            _, resolved = _resolve_ref(
                api_dir, root_path.resolve(), require_text(path_item["$ref"], route), cache
            )
            path_item = require_mapping(resolved, f"resolved paths.{route}")
        path_parameters = _parameter_names(path_item.get("parameters"))
        route_parameters = set(PATH_PARAMETER.findall(route))
        route_methods = 0
        for method, raw_operation in path_item.items():
            normalized_method = str(method).lower()
            if normalized_method not in HTTP_METHODS:
                continue
            operation = require_mapping(raw_operation, f"paths.{route}.{method}")
            operation_id = require_text(
                operation.get("operationId"), f"paths.{route}.{method}.operationId"
            )
            if operation_id in operation_ids:
                raise ContractError(
                    f"중복 operationId `{operation_id}`: "
                    f"{operation_ids[operation_id]}, {normalized_method.upper()} {route}"
                )
            operation_ids[operation_id] = f"{normalized_method.upper()} {route}"
            responses = require_mapping(
                operation.get("responses"), f"paths.{route}.{method}.responses"
            )
            if not responses:
                raise ContractError(f"응답이 없는 Operation입니다: {operation_id}")
            operation_parameters = _parameter_names(operation.get("parameters"))
            missing = route_parameters - path_parameters - operation_parameters
            if missing:
                raise ContractError(
                    f"{operation_id}: 선언되지 않은 Path Parameter가 있습니다: {sorted(missing)}"
                )
            operation_count += 1
            route_methods += 1
        if route_methods == 0:
            raise ContractError(f"HTTP Operation이 없는 OpenAPI Path입니다: {route}")

    return ValidationSummary(
        yaml_files=len(yaml_paths),
        references=reference_count,
        paths=len(root_paths),
        operations=operation_count,
    )


def main() -> int:
    args = parse_args()
    try:
        result = validate_repository(args.repo_root)
    except (ContractError, OSError) as exc:
        print(f"OpenAPI validation FAILED: {exc}", file=sys.stderr)
        return 1
    print("OpenAPI validation PASSED")
    print(f"- YAML files: {result.yaml_files}")
    print(f"- resolved refs: {result.references}")
    print(f"- paths: {result.paths}")
    print(f"- operations: {result.operations}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
