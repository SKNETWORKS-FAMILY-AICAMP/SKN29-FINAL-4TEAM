"""T-023 계약 담당과 Backend 구현 담당을 분리해 검증한다."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "apps"
    / "workflow"
    / "readiness.py"
)
REPOSITORY_ROOT = SCRIPT.parents[3]


def load_module():
    spec = importlib.util.spec_from_file_location(
        "t023_readiness",
        SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configure_owner_ready(module, monkeypatch):
    settings_path = Mock()
    settings_path.is_file.return_value = True
    settings_path.read_text.return_value = (
        '"apps.workflow.apps.WorkflowConfig"'
    )

    monkeypatch.setattr(module, "SETTINGS_PATH", settings_path)
    monkeypatch.setattr(
        module,
        "substantive_statement_count",
        lambda _path: 1,
    )
    monkeypatch.setattr(
        module,
        "inspect_state_machine_contract",
        lambda: {
            "valid": True,
            "sections": {
                "states": True,
                "events": True,
                "transitions": True,
                "guards": True,
                "allowed_actions": True,
                "role_permissions": True,
            },
            "counts": {
                "states": 1,
                "events": 1,
                "transitions": 1,
                "guards": 1,
                "allowed_actions": 1,
                "role_permissions": 1,
            },
            "statuses": {
                "states": "TEAM_APPROVED",
                "events": "TEAM_APPROVED",
                "transitions": "TEAM_APPROVED",
                "guards": "TEAM_APPROVED",
                "allowed_actions": "TEAM_APPROVED",
                "role_permissions": "TEAM_APPROVED",
            },
            "team_approved": True,
            "errors": [],
        },
    )
    monkeypatch.setattr(module, "model_class_count", lambda _path: 1)
    monkeypatch.setattr(
        module,
        "substantive_migration_count",
        lambda _directory: 1,
    )
    monkeypatch.setattr(
        module,
        "inspect_api_contract",
        lambda _path: {
            "defined": True,
            "team_approved": True,
            "operation_statuses": ["TEAM_APPROVED"],
            "paths": ["/inquiries/{inquiry_id}/events"],
        },
    )
    monkeypatch.setattr(
        module,
        "workflow_routes_registered",
        lambda _paths: True,
    )
    monkeypatch.setattr(module, "python_file_issues", lambda _paths: {})
    monkeypatch.setattr(module, "runtime_test_files", lambda: [Mock()])
    monkeypatch.setattr(module, "test_function_count", lambda _path: 1)


def test_current_contract_and_runtime_files_are_present_but_owner_gates_remain():
    result = load_module().audit_readiness(environ={})

    assert result["status"] == "PARTIAL"
    assert result["evidence"]["contract_owner"] == "윤승혁(PM)"
    assert result["evidence"]["backend_implementation_owner"] == "최지용"
    assert result["evidence"]["model_class_count"] == 2
    assert result["evidence"]["contract"]["states"] is True
    assert result["evidence"]["contract"]["events"] is True
    assert result["evidence"]["contract"]["transitions"] is True
    assert result["evidence"]["contract"]["guards"] is True
    assert result["evidence"]["contract"]["allowed_actions"] is True
    assert result["evidence"]["contract"]["role_permissions"] is True
    assert result["evidence"]["contract_validation_status"] == "PASSED"
    assert result["evidence"]["contract_validation_errors"] == []
    assert result["evidence"]["contract_counts"] == {
        "states": 13,
        "events": 33,
        "transitions": 37,
        "guards": 42,
        "allowed_actions": 24,
        "role_permissions": 5,
    }
    assert "PM_STATE_MACHINE_CONTRACT_INCOMPLETE" not in result["blockers"]
    assert result["evidence"]["contract_team_approved"] is True
    assert (
        "PM_STATE_MACHINE_CONTRACT_REVIEW_PENDING"
        not in result["blockers"]
    )
    assert result["evidence"]["runtime_implemented_file_count"] == 10
    assert "WORKFLOW_RUNTIME_INCOMPLETE" not in result["blockers"]
    assert "WORKFLOW_ROUTES_NOT_REGISTERED" not in result["blockers"]
    assert "WORKFLOW_RUNTIME_TESTS_MISSING" not in result["blockers"]
    assert result["evidence"]["api_structure_decision"] == (
        "CONTRACT_REVIEW_PENDING"
    )
    assert "WORKFLOW_API_CONTRACT_REVIEW_PENDING" in result["blockers"]
    assert "BACKEND_REVIEWED" in result["completion_blockers"]


def test_common_base_model_is_counted():
    model_file = (
        Path(__file__).resolve().parents[3]
        / "apps"
        / "accounts"
        / "models"
        / "customer_profile.py"
    )

    assert load_module().model_class_count(model_file) == 1


def test_missing_or_malformed_contracts_fail_closed(monkeypatch):
    module = load_module()
    missing = SCRIPT.parent / "__missing_readiness_source__.py"
    missing_contract_dir = SCRIPT.parent / "__missing_contracts__"
    monkeypatch.setattr(module, "CONTRACT_DIR", missing_contract_dir)

    assert module.substantive_statement_count(missing) == 0
    assert module.yaml_value("missing.yaml", "states") is None
    inspection = module.inspect_state_machine_contract()
    assert inspection["valid"] is False
    assert inspection["errors"]
    assert module.has_http_operation(
        missing_contract_dir / "missing.yaml"
    ) is False


def test_owner_proposal_contract_remains_review_pending(
    monkeypatch,
):
    module = load_module()
    contract = (
        Path(__file__).resolve().parents[4]
        / "contracts"
        / "api"
        / "paths"
        / "auth.yaml"
    )
    monkeypatch.setattr(module, "WORKFLOW_API_CONTRACT", contract)

    result = module.audit_readiness(environ={})

    assert result["evidence"]["api_structure_decision"] == (
        "CONTRACT_REVIEW_PENDING"
    )
    assert "WORKFLOW_API_STRUCTURE_DECISION_PENDING" not in result["blockers"]
    assert "WORKFLOW_API_CONTRACT_REVIEW_PENDING" in result["blockers"]


def test_only_team_approved_contract_statuses_clear_review_gate():
    module = load_module()

    for approved_status in ("TEAM_APPROVED", "APPROVED", "ACCEPTED"):
        contract = Mock()
        contract.is_file.return_value = True
        contract.read_text.return_value = f"""
/inquiries/{{inquiry_id}}/events:
  post:
    x-contract-status: {approved_status}
    responses:
      "200":
        description: ok
"""

        evidence = module.inspect_api_contract(contract)

        assert evidence["defined"] is True
        assert evidence["team_approved"] is True


def test_missing_or_pending_operation_status_is_not_team_approved():
    module = load_module()

    for pending_status_line in (
        "",
        "    x-contract-status: PM_REVIEW_PENDING\n",
        "    x-contract-status: OWNER_PROPOSAL_REVIEW_PENDING\n",
    ):
        contract = Mock()
        contract.is_file.return_value = True
        contract.read_text.return_value = f"""
/inquiries/{{inquiry_id}}/events:
  post:
{pending_status_line}    responses:
      "200":
        description: ok
"""

        evidence = module.inspect_api_contract(contract)

        assert evidence["defined"] is True
        assert evidence["team_approved"] is False


def test_meaningful_urlpatterns_requires_a_real_route_assignment():
    module = load_module()
    url_file = Mock()
    url_file.is_file.return_value = True
    url_file.read_text.return_value = """
from django.urls import path
urlpatterns = [path("events", object())]
"""

    assert module.meaningful_urlpatterns(url_file) is True

    url_file.read_text.return_value = "urlpatterns = []"
    assert module.meaningful_urlpatterns(url_file) is False


def test_workflow_routes_allow_direct_or_inquiry_nested_registration(
    monkeypatch,
):
    module = load_module()

    monkeypatch.setattr(
        module,
        "urlpatterns_included_modules",
        lambda _path: {"apps.workflow.api.urls"},
    )
    monkeypatch.setattr(
        module,
        "meaningful_urlpatterns",
        lambda path: path == module.WORKFLOW_API_URLS_PATH,
    )
    assert module.workflow_routes_registered(["/workflow/events"]) is True

    monkeypatch.setattr(
        module,
        "urlpatterns_included_modules",
        lambda _path: {"apps.inquiries.api.urls"},
    )
    monkeypatch.setattr(
        module,
        "meaningful_urlpatterns",
        lambda path: path == module.INQUIRIES_API_URLS_PATH,
    )
    assert module.workflow_routes_registered(
        ["/inquiries/{inquiry_id}/events"]
    ) is True
    assert module.workflow_routes_registered(["/workflow/events"]) is False


def test_postgresql_env_names_are_not_verification():
    environ = {
        "POSTGRES_DB": "db",
        "POSTGRES_USER": "user",
        "POSTGRES_PASSWORD": "password",
        "POSTGRES_HOST": "host",
        "POSTGRES_PORT": "5432",
    }

    result = load_module().audit_readiness(environ=environ)

    assert "POSTGRESQL_NOT_CONFIGURED" not in result["blockers"]
    assert "POSTGRESQL_NOT_VERIFIED" in result["blockers"]


def test_postgresql_verification_forces_local_settings_and_three_checks(
    monkeypatch,
):
    module = load_module()
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.test")
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module.verify_postgresql_runtime()

    assert result == {
        "connection_status": "CONNECTED",
        "makemigrations_status": "PASSED",
        "migration_status": "PASSED",
    }
    assert len(calls) == 3
    assert all(
        kwargs["env"]["DJANGO_SETTINGS_MODULE"]
        == "config.settings.local"
        for _, kwargs in calls
    )
    assert calls[1][0][2:6] == [
        "makemigrations",
        "--check",
        "--dry-run",
        "--noinput",
    ]
    assert "--settings=config.settings.local" in calls[1][0]
    assert calls[2][0][2:5] == ["migrate", "--check", "--noinput"]
    assert "--settings=config.settings.local" in calls[2][0]


def test_malformed_postgresql_evidence_fails_closed():
    module = load_module()
    environ = {
        "POSTGRES_DB": "db",
        "POSTGRES_USER": "user",
        "POSTGRES_PASSWORD": "password",
        "POSTGRES_HOST": "host",
        "POSTGRES_PORT": "5432",
    }

    missing_status = module.audit_readiness(
        environ=environ,
        postgresql_verification={"connection_status": "CONNECTED"},
    )
    invalid_type = module.audit_readiness(
        environ=environ,
        postgresql_verification="not-a-dict",
    )

    assert "DJANGO_MODEL_MIGRATION_DRIFT" in (
        missing_status["blockers"]
    )
    assert "POSTGRESQL_NOT_VERIFIED" in invalid_type["blockers"]


def test_all_postgresql_statuses_are_required_to_clear_database_gate():
    module = load_module()
    environ = {
        "POSTGRES_DB": "db",
        "POSTGRES_USER": "user",
        "POSTGRES_PASSWORD": "password",
        "POSTGRES_HOST": "host",
        "POSTGRES_PORT": "5432",
    }

    result = module.audit_readiness(
        environ=environ,
        postgresql_verification={
            "connection_status": "CONNECTED",
            "makemigrations_status": "PASSED",
            "migration_status": "PASSED",
        },
    )

    assert not any(
        blocker.startswith("POSTGRESQL_")
        for blocker in result["blockers"]
    )


def test_owner_completion_waits_for_non_author_backend_review(monkeypatch):
    module = load_module()
    configure_owner_ready(module, monkeypatch)
    environ = {
        "POSTGRES_DB": "db",
        "POSTGRES_USER": "user",
        "POSTGRES_PASSWORD": "password",
        "POSTGRES_HOST": "host",
        "POSTGRES_PORT": "5432",
    }

    result = module.audit_readiness(
        environ=environ,
        runtime_test_exit_code=0,
        postgresql_verification={
            "connection_status": "CONNECTED",
            "makemigrations_status": "PASSED",
            "migration_status": "PASSED",
        },
    )

    assert result["status"] == "OWNER_IMPLEMENTATION_READY"
    assert result["owner_blockers"] == []
    assert result["completion_blockers"] == ["BACKEND_REVIEWED"]


def test_non_author_backend_review_allows_final_ready(monkeypatch):
    module = load_module()
    configure_owner_ready(module, monkeypatch)
    environ = {
        "POSTGRES_DB": "db",
        "POSTGRES_USER": "user",
        "POSTGRES_PASSWORD": "password",
        "POSTGRES_HOST": "host",
        "POSTGRES_PORT": "5432",
    }

    for approved_status in ("TEAM_APPROVED", "APPROVED", "ACCEPTED"):
        result = module.audit_readiness(
            environ=environ,
            runtime_test_exit_code=0,
            postgresql_verification={
                "connection_status": "CONNECTED",
                "makemigrations_status": "PASSED",
                "migration_status": "PASSED",
            },
            completion_evidence={
                "team_review": {
                    "status": approved_status,
                    "reviewer": "김은진",
                    "recorded_at": "2026-07-27T11:00:00+09:00",
                }
            },
        )

        assert result["status"] == "READY"
        assert result["completion_blockers"] == []


def test_author_cannot_approve_own_backend_completion(monkeypatch):
    module = load_module()
    configure_owner_ready(module, monkeypatch)
    environ = {
        "POSTGRES_DB": "db",
        "POSTGRES_USER": "user",
        "POSTGRES_PASSWORD": "password",
        "POSTGRES_HOST": "host",
        "POSTGRES_PORT": "5432",
    }

    result = module.audit_readiness(
        environ=environ,
        runtime_test_exit_code=0,
        postgresql_verification={
            "connection_status": "CONNECTED",
            "makemigrations_status": "PASSED",
            "migration_status": "PASSED",
        },
        completion_evidence={
            "team_review": {
                "status": "APPROVED",
                "reviewer": "최지용",
                "recorded_at": "2026-07-27T11:00:00+09:00",
            }
        },
    )

    assert result["status"] == "OWNER_IMPLEMENTATION_READY"
    assert result["completion_blockers"] == ["BACKEND_REVIEWED"]


def test_t023_completion_example_is_safe_and_pending():
    module = load_module()
    example = json.loads(
        (
            REPOSITORY_ROOT
            / "docs"
            / "handoffs"
            / "t023_completion_evidence.example.json"
        ).read_text(encoding="utf-8")
    )

    assert module.completion_evidence_gates(example) == {
        "backend_reviewed": False
    }
