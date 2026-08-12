"""Contract CI가 로컬 계약 Gate를 약화하지 않는지 검증한다."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "contracts-ci.yml"

EXPECTED_TRIGGER_PATHS = {
    "contracts/**",
    "scripts/contracts/**",
    "tests/contract/**",
    ".github/workflows/contracts-ci.yml",
}

EXPECTED_GATE_COMMANDS = [
    "python -B scripts/contracts/validate_state_machine.py",
    "python -B scripts/contracts/render_state_machine.py --check",
    "python -B scripts/contracts/validate_codes.py",
    "python -B scripts/contracts/validate_openapi.py",
    "python -B scripts/contracts/validate_examples.py",
    "python -B scripts/contracts/validate_contract_crosswalk.py",
    "python -B -m pytest tests/contract -q -p no:cacheprovider",
]


def _workflow() -> dict[str, Any]:
    return yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def _contains_key(value: Any, target: str) -> bool:
    if isinstance(value, dict):
        return target in value or any(_contains_key(item, target) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, target) for item in value)
    return False


def test_contract_ci_has_complete_triggers_and_read_only_permissions() -> None:
    workflow = _workflow()
    triggers = workflow["on"]

    assert "workflow_dispatch" in triggers
    for event in ("pull_request", "push"):
        assert set(triggers[event]["paths"]) == EXPECTED_TRIGGER_PATHS
    assert workflow["permissions"] == {"contents": "read"}


def test_contract_ci_pins_runtime_and_minimal_dependencies() -> None:
    workflow = _workflow()
    job = workflow["jobs"]["verify-contracts"]
    steps = job["steps"]
    python_step = next(step for step in steps if step.get("uses") == "actions/setup-python@v5")
    install_step = next(step for step in steps if step.get("name") == "Install contract gate dependencies")

    assert job["runs-on"] == "ubuntu-latest"
    assert job["timeout-minutes"] == "10"
    assert python_step["with"]["python-version"] == "3.13.13"
    install_command = " ".join(install_step["run"].split())
    for expected in (
        "--constraint backend/requirements/constraints-py313.txt",
        "PyYAML==6.0.3",
        "jsonschema==4.26.0",
        "pytest==9.1.1",
    ):
        assert expected in install_command


def test_contract_ci_runs_all_seven_gates_without_failure_suppression() -> None:
    workflow = _workflow()
    steps = workflow["jobs"]["verify-contracts"]["steps"]
    commands = [step["run"] for step in steps if step.get("run") in EXPECTED_GATE_COMMANDS]

    assert commands == EXPECTED_GATE_COMMANDS
    assert not _contains_key(workflow, "continue-on-error")
