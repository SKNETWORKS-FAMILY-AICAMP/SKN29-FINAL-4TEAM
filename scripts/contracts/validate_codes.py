#!/usr/bin/env python3
"""Validate common Code Registry files and State Machine projections."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Any

from validation_support import (
    ContractError,
    load_yaml,
    require_list,
    require_mapping,
    require_text,
    unique_text_list,
)


SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
ALLOWED_EMPTY_REGISTRIES = {"allowed-use.yaml", "verification-statuses.yaml"}


@dataclass(frozen=True)
class ValidationSummary:
    registry_files: int
    code_entries: int
    inquiry_statuses: int
    workflow_actions: int
    user_roles: int
    visit_statuses: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="공통 Code Registry의 문법·중복·State Machine 정합성을 검증합니다."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    return parser.parse_args()


def _catalog_codes(document: dict[str, Any], key: str, path: str) -> list[str]:
    items = require_list(document.get(key), path)
    codes: list[str] = []
    for index, raw_item in enumerate(items):
        item = require_mapping(raw_item, f"{path}[{index}]")
        codes.append(require_text(item.get("code"), f"{path}[{index}].code"))
    if len(codes) != len(set(codes)):
        raise ContractError(f"`{path}`에 중복 Code가 있습니다.")
    return codes


def validate_repository(repo_root: Path) -> ValidationSummary:
    root = repo_root.resolve()
    codes_dir = root / "contracts" / "codes"
    registry_paths = sorted(codes_dir.glob("*.yaml"))
    if not registry_paths:
        raise ContractError("공통 Code Registry 파일이 없습니다.")

    registries: dict[str, list[str]] = {}
    total_entries = 0
    for path in registry_paths:
        document = load_yaml(path)
        codes = unique_text_list(document.get("codes"), f"{path.name}.codes")
        if not codes and path.name not in ALLOWED_EMPTY_REGISTRIES:
            raise ContractError(f"비어 있는 Code Registry입니다: {path.name}")
        version = document.get("version")
        status = document.get("status")
        if version is not None and not (
            isinstance(version, str) and SEMVER.fullmatch(version)
        ):
            raise ContractError(f"유효하지 않은 Version입니다: {path.name}={version!r}")
        if status is not None:
            require_text(status, f"{path.name}.status")
        if document.get("deprecated") is True:
            canonical = require_text(
                document.get("canonical_contract"),
                f"{path.name}.canonical_contract",
            )
            if not (codes_dir / canonical).is_file():
                raise ContractError(f"{path.name}: Canonical Registry가 없습니다: {canonical}")
        registries[path.name] = codes
        total_entries += len(codes)

    states = load_yaml(root / "contracts" / "state-machine" / "inquiry-states.yaml")
    allowed_actions = load_yaml(
        root / "contracts" / "state-machine" / "allowed-actions.yaml"
    )
    permissions = load_yaml(
        root / "contracts" / "state-machine" / "role-permissions.yaml"
    )
    state_codes = _catalog_codes(states, "states", "inquiry-states.states")
    action_codes = _catalog_codes(
        allowed_actions, "action_catalog", "allowed-actions.action_catalog"
    )
    role_codes = _catalog_codes(permissions, "roles", "role-permissions.roles")
    external_role_codes = [code for code in role_codes if code != "SYSTEM"]
    visit_codes = unique_text_list(
        states.get("visit_status_codes"), "inquiry-states.visit_status_codes"
    )

    expected = {
        "inquiry-statuses.yaml": state_codes,
        "workflow-actions.yaml": action_codes,
        "user-roles.yaml": external_role_codes,
        "visit-statuses.yaml": visit_codes,
    }
    for filename, expected_codes in expected.items():
        if registries.get(filename) != expected_codes:
            raise ContractError(
                f"{filename}이 State Machine Source의 집합·순서와 다릅니다."
            )

    return ValidationSummary(
        registry_files=len(registry_paths),
        code_entries=total_entries,
        inquiry_statuses=len(state_codes),
        workflow_actions=len(action_codes),
        user_roles=len(external_role_codes),
        visit_statuses=len(visit_codes),
    )


def main() -> int:
    args = parse_args()
    try:
        result = validate_repository(args.repo_root)
    except (ContractError, OSError) as exc:
        print(f"Code Registry validation FAILED: {exc}", file=sys.stderr)
        return 1
    print("Code Registry validation PASSED")
    print(f"- registry files: {result.registry_files}")
    print(f"- code entries: {result.code_entries}")
    print(f"- inquiry statuses: {result.inquiry_statuses}")
    print(f"- workflow actions: {result.workflow_actions}")
    print(f"- user roles: {result.user_roles}")
    print(f"- visit statuses: {result.visit_statuses}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
