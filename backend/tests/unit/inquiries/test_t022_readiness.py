"""T-022 구현 준비도와 완료 승인 게이트를 검증한다."""

from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest
import yaml


BACKEND_DIR = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = BACKEND_DIR.parent
SCRIPT = BACKEND_DIR / "apps" / "inquiries" / "readiness.py"
INQUIRY_CONTRACT = (
    REPOSITORY_ROOT / "contracts" / "api" / "paths" / "inquiries.yaml"
)
OPENAPI_CONTRACT = REPOSITORY_ROOT / "contracts" / "api" / "openapi.yaml"
COMPLETION_EVIDENCE_EXAMPLE = (
    REPOSITORY_ROOT
    / "docs"
    / "handoffs"
    / "t022_completion_evidence.example.json"
)
POSTGRES_ENV = {
    "POSTGRES_DB": "db",
    "POSTGRES_USER": "user",
    "POSTGRES_PASSWORD": "password",
    "POSTGRES_HOST": "host",
    "POSTGRES_PORT": "5432",
}
POSTGRES_PASSED = {
    "connection_status": "CONNECTED",
    "makemigrations_status": "PASSED",
    "migration_status": "PASSED",
}


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "t022_readiness",
        SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit_owner_ready(
    module: ModuleType,
    *,
    completion_evidence: dict | None = None,
) -> dict:
    settings_path = MagicMock()
    settings_path.is_file.return_value = True
    settings_path.read_text.return_value = (
        "apps.inquiries.apps.InquiriesConfig"
    )
    with (
        patch.object(module, "SETTINGS_PATH", settings_path),
        patch.object(
            module,
            "substantive_statement_count",
            return_value=1,
        ),
        patch.object(module, "model_class_count", return_value=1),
        patch.object(
            module,
            "substantive_migration_count",
            return_value=1,
        ),
        patch.object(module, "python_file_issues", return_value={}),
        patch.object(
            module,
            "included_modules",
            return_value={"apps.inquiries.api.urls"},
        ),
        patch.object(
            module,
            "inspect_api_contract",
            return_value={
                "defined": True,
                "confirmed": True,
                "operation_statuses": ["CONFIRMED"],
                "operations": [
                    {
                        "path": "/inquiries",
                        "method": "post",
                        "status": "CONFIRMED",
                    }
                ],
            },
        ),
        patch.object(module, "runtime_test_files", return_value=[SCRIPT]),
        patch.object(module, "test_function_count", return_value=1),
    ):
        return module.audit_readiness(
            environ=POSTGRES_ENV,
            runtime_test_exit_code=0,
            postgresql_verification=POSTGRES_PASSED,
            completion_evidence=completion_evidence,
        )


def test_missing_postgresql_configuration_keeps_owner_partial():
    result = load_module().audit_readiness(environ={})

    assert result["status"] == "PARTIAL"
    assert "POSTGRESQL_NOT_CONFIGURED" in result["owner_blockers"]
    assert result["completion_blockers"] == ["TEAM_REVIEWED"]
    assert result["completion_gates"]["owner_implementation_ready"] is False


def test_common_base_model_is_counted():
    model_file = (
        BACKEND_DIR
        / "apps"
        / "accounts"
        / "models"
        / "customer_profile.py"
    )

    assert load_module().model_class_count(model_file) == 1


def test_missing_or_malformed_sources_fail_closed():
    module = load_module()
    missing = SCRIPT.parent / "__missing_readiness_source__.py"

    assert module.substantive_statement_count(missing) == 0
    assert module.has_http_operation(
        SCRIPT.parent / "__missing_contract__.yaml"
    ) is False
    assert module.python_file_issues((missing,)) == {
        str(missing.relative_to(REPOSITORY_ROOT)).replace(
            "\\",
            "/",
        ): "MISSING",
    }
    with (
        patch.object(Path, "is_file", return_value=True),
        patch.object(Path, "read_text", return_value="def broken(:\n"),
    ):
        assert module.substantive_statement_count(missing) == 0


def test_owner_contract_is_confirmed_independently_of_runtime():
    module = load_module()

    contract = module.inspect_api_contract(INQUIRY_CONTRACT)

    assert contract["defined"] is True
    assert contract["confirmed"] is True
    assert contract["operation_statuses"]
    assert set(contract["operation_statuses"]) == {"CONFIRMED"}


def test_confirmed_operation_status_marks_contract_confirmed():
    module = load_module()
    contract = Mock()
    contract.is_file.return_value = True
    contract.read_text.return_value = f"""
/inquiries:
  post:
    x-contract-status: CONFIRMED
    responses:
      "201":
        description: created
"""

    result = module.inspect_api_contract(contract)

    assert result["defined"] is True
    assert result["confirmed"] is True


@pytest.mark.parametrize(
    "status_line",
    [
        "",
        "    x-contract-status: PM_REVIEW_PENDING\n",
        "    x-contract-status: OWNER_PROPOSAL_REVIEW_PENDING\n",
    ],
)
def test_missing_or_pending_contract_status_is_not_confirmed(status_line):
    module = load_module()
    contract = Mock()
    contract.is_file.return_value = True
    contract.read_text.return_value = f"""
/inquiries:
  post:
{status_line}    responses:
      "201":
        description: created
"""

    result = module.inspect_api_contract(contract)

    assert result["defined"] is True
    assert result["confirmed"] is False


def test_one_pending_operation_keeps_the_whole_contract_unconfirmed():
    module = load_module()
    contract = Mock()
    contract.is_file.return_value = True
    contract.read_text.return_value = """
/inquiries:
  post:
    x-contract-status: CONFIRMED
    responses:
      "201":
        description: created
/inquiries/{id}/questionnaire:
  patch:
    x-contract-status: OWNER_PROPOSAL_REVIEW_PENDING
    responses:
      "200":
        description: accumulated
"""

    result = module.inspect_api_contract(contract)

    assert result["defined"] is True
    assert result["confirmed"] is False


def test_defined_unconfirmed_contract_is_evidence_not_owner_blocker():
    module = load_module()
    proposal = {
        "defined": True,
        "confirmed": False,
        "operation_statuses": ["OWNER_PROPOSAL_REVIEW_PENDING"],
        "operations": [
            {
                "path": "/inquiries",
                "method": "post",
                "status": "OWNER_PROPOSAL_REVIEW_PENDING",
            }
        ],
    }

    with patch.object(
        module,
        "inspect_api_contract",
        return_value=proposal,
    ):
        result = module.audit_readiness(environ={})

    assert result["evidence"]["api_contract_decision"] == (
        "DEFINED_NOT_CONFIRMED"
    )
    assert "INQUIRY_API_CONTRACT_EMPTY" not in result["owner_blockers"]
    assert "INQUIRY_API_CONTRACT_REVIEW_PENDING" not in result[
        "owner_blockers"
    ]


def test_inquiry_contract_local_refs_exist_and_yaml_load():
    document = yaml.safe_load(INQUIRY_CONTRACT.read_text(encoding="utf-8"))
    assert isinstance(document, dict)

    refs = []

    def collect_refs(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "$ref" and isinstance(child, str):
                    refs.append(child)
                else:
                    collect_refs(child)
        elif isinstance(value, list):
            for child in value:
                collect_refs(child)

    collect_refs(document)
    assert refs
    for reference in refs:
        file_reference = reference.split("#", maxsplit=1)[0]
        assert file_reference
        target = (INQUIRY_CONTRACT.parent / file_reference).resolve()
        assert target.is_file(), reference
        assert yaml.safe_load(target.read_text(encoding="utf-8")) is not None


def test_root_openapi_exposes_all_confirmed_inquiry_paths():
    root_contract = yaml.safe_load(
        OPENAPI_CONTRACT.read_text(encoding="utf-8")
    )

    assert root_contract["paths"]["/inquiries"]["$ref"] == (
        "./paths/inquiries.yaml#/~1inquiries"
    )
    assert root_contract["paths"]["/inquiries/{id}/questionnaire"]["$ref"] == (
        "./paths/inquiries.yaml#/~1inquiries~1{id}~1questionnaire"
    )
    assert root_contract["paths"]["/inquiries/{id}/action-results"]["$ref"] == (
        "./paths/inquiries.yaml#/~1inquiries~1{id}~1action-results"
    )
    assert root_contract["paths"]["/inquiries/{id}/submit"]["$ref"] == (
        "./paths/inquiries.yaml#/~1inquiries~1{id}~1submit"
    )


def test_urlpatterns_assignment_requires_a_meaningful_value():
    module = load_module()
    empty_assignment = ast.parse("urlpatterns = []").body[0]
    meaningful_assignment = ast.parse(
        'urlpatterns = [path("inquiries/", inquiry_view)]'
    ).body[0]

    assert module.assignment_has_runtime_value(empty_assignment) is False
    assert (
        module.assignment_has_runtime_value(meaningful_assignment)
        is True
    )


def test_postgresql_env_names_are_not_verification():
    result = load_module().audit_readiness(environ=POSTGRES_ENV)

    assert "POSTGRESQL_NOT_CONFIGURED" not in result["owner_blockers"]
    assert "POSTGRESQL_NOT_VERIFIED" in result["owner_blockers"]
    assert (
        "POSTGRESQL_MAKEMIGRATIONS_NOT_VERIFIED"
        in result["owner_blockers"]
    )
    assert (
        "POSTGRESQL_MIGRATION_NOT_VERIFIED"
        in result["owner_blockers"]
    )


def test_all_three_postgresql_statuses_clear_database_gate():
    result = load_module().audit_readiness(
        environ=POSTGRES_ENV,
        postgresql_verification=POSTGRES_PASSED,
    )

    assert not any(
        blocker.startswith("POSTGRESQL_")
        for blocker in result["owner_blockers"]
    )


@pytest.mark.parametrize(
    "malformed_verification",
    [
        {"connection_status": "CONNECTED"},
        {"makemigrations_status": "PASSED"},
        [],
    ],
)
def test_malformed_postgresql_verification_fails_closed(
    malformed_verification,
):
    result = load_module().audit_readiness(
        environ=POSTGRES_ENV,
        postgresql_verification=malformed_verification,
    )

    assert result["status"] == "PARTIAL"
    assert any(
        blocker.startswith("POSTGRESQL_")
        for blocker in result["owner_blockers"]
    )


def test_postgresql_verifier_forces_local_settings_and_runs_all_checks():
    module = load_module()
    completed = [
        SimpleNamespace(returncode=0),
        SimpleNamespace(returncode=0),
        SimpleNamespace(returncode=0),
    ]

    with patch.object(
        module.subprocess,
        "run",
        side_effect=completed,
    ) as run:
        result = module.verify_postgresql_runtime()

    assert result == POSTGRES_PASSED
    assert run.call_count == 3
    commands = [call.args[0] for call in run.call_args_list]
    assert commands[1][2:] == [
        "makemigrations",
        "--check",
        "--dry-run",
        "--settings=config.settings.local",
    ]
    assert commands[2][2:] == [
        "migrate",
        "--check",
        "--noinput",
        "--settings=config.settings.local",
    ]
    assert all(
        call.kwargs["env"]["DJANGO_SETTINGS_MODULE"]
        == "config.settings.local"
        for call in run.call_args_list
    )


def test_migrate_check_still_runs_when_makemigrations_check_fails():
    module = load_module()
    completed = [
        SimpleNamespace(returncode=0),
        SimpleNamespace(returncode=1),
        SimpleNamespace(returncode=0),
    ]

    with patch.object(
        module.subprocess,
        "run",
        side_effect=completed,
    ) as run:
        result = module.verify_postgresql_runtime()

    assert run.call_count == 3
    assert result == {
        "connection_status": "CONNECTED",
        "makemigrations_status": "FAILED",
        "migration_status": "PASSED",
    }


def test_failed_connection_returns_all_three_postgresql_statuses():
    module = load_module()

    with patch.object(
        module.subprocess,
        "run",
        return_value=SimpleNamespace(returncode=2),
    ) as run:
        result = module.verify_postgresql_runtime()

    assert run.call_count == 1
    assert result == {
        "connection_status": "NOT_CONFIGURED",
        "makemigrations_status": "NOT_RUN",
        "migration_status": "NOT_RUN",
    }


def test_owner_implementation_is_not_final_ready_without_review():
    result = audit_owner_ready(load_module())

    assert result["status"] == "OWNER_IMPLEMENTATION_READY"
    assert result["owner_blockers"] == []
    assert result["completion_blockers"] == ["TEAM_REVIEWED"]
    assert result["completion_gates"] == {
        "owner_implementation_ready": True,
        "team_reviewed": False,
    }


@pytest.mark.parametrize(
    "status",
    ["APPROVED", "TEAM_APPROVED", "ACCEPTED"],
)
def test_external_team_review_approval_allows_final_ready(status):
    result = audit_owner_ready(
        load_module(),
        completion_evidence={
            "team_review": {
                "status": status,
                "reviewer": "김은진",
                "recorded_at": "2026-07-27T09:00:00+09:00",
            }
        },
    )

    assert result["status"] == "READY"
    assert result["completion_blockers"] == []
    assert result["completion_evidence_supplied"] is True


@pytest.mark.parametrize(
    "team_review",
    [
        {
            "status": "APPROVED",
            "reviewer": "최지용",
            "recorded_at": "2026-07-27T09:00:00+09:00",
        },
        {
            "status": "PENDING",
            "reviewer": "김은진",
            "recorded_at": "2026-07-27T09:00:00+09:00",
        },
        {
            "status": "APPROVED",
            "reviewer": "김은진",
            "recorded_at": "",
        },
        "malformed",
        {},
    ],
)
def test_review_evidence_fails_closed(team_review):
    result = audit_owner_ready(
        load_module(),
        completion_evidence={"team_review": team_review},
    )

    assert result["status"] == "OWNER_IMPLEMENTATION_READY"
    assert result["completion_blockers"] == ["TEAM_REVIEWED"]


def test_completion_example_is_safe_and_not_approved():
    example = json.loads(
        COMPLETION_EVIDENCE_EXAMPLE.read_text(encoding="utf-8")
    )

    result = audit_owner_ready(
        load_module(),
        completion_evidence=example,
    )

    assert result["status"] == "OWNER_IMPLEMENTATION_READY"
    assert result["completion_blockers"] == ["TEAM_REVIEWED"]


def test_cli_accepts_completion_evidence_path():
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--completion-evidence",
            str(COMPLETION_EVIDENCE_EXAMPLE),
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    result = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert result["completion_evidence_supplied"] is True
    assert result["completion_blockers"] == ["TEAM_REVIEWED"]


def test_deferred_t022_runtime_contract_gaps_fail_closed():
    result = load_module().inspect_deferred_runtime_contracts()

    assert result["ready"] is False
    assert result["blockers"] == [
        "ACTION_RESULTS_PATH_ID_NOT_UUID",
        "ACTION_RESULTS_IDEMPOTENCY_KEY_UNDECLARED",
    ]
    assert result["operations"] == {
        "submitFollowUpAnswers": {
            "path_id_uuid": True,
            "idempotency_key_declared": True,
            "answers_typed": True,
        },
        "createInquiryActionResult": {
            "path_id_uuid": False,
            "idempotency_key_declared": False,
        },
    }


def test_deferred_t022_runtime_contract_gate_is_reported_separately():
    result = load_module().audit_readiness(environ={})

    gate = result["evidence"]["deferred_runtime_contracts"]
    assert gate["ready"] is False
    assert gate["blockers"]
    assert not any(
        blocker in result["owner_blockers"]
        for blocker in gate["blockers"]
    )


def test_cli_can_require_deferred_t022_runtime_contracts():
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--require-deferred-runtime-contracts",
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    result = json.loads(completed.stdout)
    assert completed.returncode == 3
    assert result["evidence"]["deferred_runtime_contracts"][
        "ready"
    ] is False
