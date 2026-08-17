"""Fail-closed readiness audit for T-028B EvidenceCardDTO Runtime."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPOSITORY_ROOT / "backend"
WEEK5_ENTRY_PATH = (
    REPOSITORY_ROOT / "docs" / "planning" / "week5-entry-criteria.md"
)
WBS_PATH = REPOSITORY_ROOT / "docs" / "planning" / "md" / "WBS.md"
EVIDENCE_API_CONTRACT = (
    REPOSITORY_ROOT / "contracts" / "api" / "paths" / "evidence.yaml"
)
CONTRACT_EXAMPLE = (
    REPOSITORY_ROOT
    / "contracts"
    / "api"
    / "preparation"
    / "evidence"
    / "evidence-card.contract-preparation.json"
)
RUNTIME_FILES = (
    BACKEND_DIR
    / "apps"
    / "evidence"
    / "repositories"
    / "evidence_repository.py",
    BACKEND_DIR
    / "apps"
    / "evidence"
    / "services"
    / "evidence_card_service.py",
    BACKEND_DIR
    / "apps"
    / "evidence"
    / "services"
    / "evidence_validation_service.py",
    BACKEND_DIR / "apps" / "evidence" / "api" / "serializers.py",
    BACKEND_DIR / "apps" / "evidence" / "api" / "views.py",
    BACKEND_DIR / "apps" / "evidence" / "api" / "urls.py",
)


def markdown_table_status(path: Path, item: str) -> str | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    escaped = re.escape(item)
    for line in text.splitlines():
        if not re.search(rf"`?{escaped}`?", line):
            continue
        cells = [
            cell.strip().strip("`")
            for cell in line.split("|")[1:-1]
        ]
        if not cells:
            continue
        if item == "W5-G04" and len(cells) >= 3:
            return cells[2]
        if item == "T-028A":
            for candidate in cells:
                if candidate in {"완료", "진행 중", "미착수", "차단"}:
                    return candidate
    return None


def yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return {}
    return document if isinstance(document, dict) else {}


def has_runtime_statements(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError):
        return False
    statements = list(tree.body)
    if (
        statements
        and isinstance(statements[0], ast.Expr)
        and isinstance(statements[0].value, ast.Constant)
        and isinstance(statements[0].value.value, str)
    ):
        statements = statements[1:]
    return bool(statements)


def contract_example_is_preparation_only(
    path: Path = CONTRACT_EXAMPLE,
) -> bool:
    if not path.is_file():
        return False
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return (
        isinstance(document, dict)
        and document.get("artifact_scope")
        == "NON_RUNTIME_CONTRACT_PREPARATION"
        and document.get("contract_status") == "PREPARATION_ONLY"
        and document.get("runtime_implemented") is False
        and isinstance(document.get("role_examples"), dict)
        and bool(document["role_examples"])
    )


def audit_readiness() -> dict[str, Any]:
    w5_g04_status = markdown_table_status(WEEK5_ENTRY_PATH, "W5-G04")
    t028a_status = markdown_table_status(WBS_PATH, "T-028A")
    api_contract = yaml_mapping(EVIDENCE_API_CONTRACT)
    runtime_files = {
        str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/"): (
            has_runtime_statements(path)
        )
        for path in RUNTIME_FILES
    }
    preparation_example = contract_example_is_preparation_only()

    blockers = []
    if w5_g04_status != "PASS":
        blockers.append("W5_G04_NOT_PASS")
    if t028a_status != "완료":
        blockers.append("T028A_NOT_COMPLETE")
    if not api_contract:
        blockers.append("EVIDENCE_API_CONTRACT_EMPTY")
    if not any(runtime_files.values()):
        blockers.append("EVIDENCE_RUNTIME_STUBS_ONLY")
    elif not all(runtime_files.values()):
        blockers.append("EVIDENCE_PUBLIC_RUNTIME_INCOMPLETE")
    if not preparation_example:
        blockers.append("CONTRACT_PREPARATION_EXAMPLE_MISSING")

    return {
        "status": "RUNTIME_READY" if not blockers else "PREPARATION_ONLY",
        "runtime_ready": not blockers,
        "evidence": {
            "w5_g04_status": w5_g04_status,
            "t028a_status": t028a_status,
            "api_contract_defined": bool(api_contract),
            "runtime_files": runtime_files,
            "contract_preparation_example_ready": preparation_example,
        },
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-runtime-ready", action="store_true")
    arguments = parser.parse_args()
    result = audit_readiness()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if arguments.require_runtime_ready and not result["runtime_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
