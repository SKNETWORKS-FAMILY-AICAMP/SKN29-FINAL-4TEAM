"""상담사 합성 Dashboard와 방문 기사 선택 Source 계약을 검증한다."""

from pathlib import Path

from jsonschema import Draft202012Validator
import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_DIR = REPOSITORY_ROOT / "contracts" / "api"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_consultant_dashboard_contract_is_confirmed_synthetic_runtime():
    root = load_yaml(OPENAPI_DIR / "openapi.yaml")
    paths = load_yaml(OPENAPI_DIR / "paths" / "operations.yaml")
    operation = paths["/consultant/dashboard"]["get"]

    assert root["paths"]["/consultant/dashboard"]["$ref"] == (
        "./paths/operations.yaml#/~1consultant~1dashboard"
    )
    assert operation["operationId"] == "getConsultantDashboard"
    assert operation["x-contract-status"] == "CONFIRMED"
    assert operation["x-runtime-status"] == "IMPLEMENTED"
    assert operation["x-permission-scope"] == (
        "CONSULTANT_SYNTHETIC_DASHBOARD"
    )
    assert set(operation["responses"]) == {
        "200",
        "401",
        "403",
        "422",
        "500",
    }


def test_dashboard_technician_id_is_the_visit_schedule_input_contract():
    schema = load_yaml(
        OPENAPI_DIR
        / "components"
        / "schemas"
        / "operations"
        / "ConsultantDashboardData.yaml"
    )
    Draft202012Validator.check_schema(schema)

    assert set(schema["required"]) == {
        "data_classification",
        "generated_at",
        "summary",
        "notices",
        "consultants",
        "technicians",
        "inquiries",
    }
    assert schema["properties"]["data_classification"] == {
        "type": "string",
        "const": "synthetic",
    }
    technician = schema["$defs"]["technician"]
    assert set(technician["required"]) == {
        "user_id",
        "name",
        "branch",
        "phone",
        "email",
    }
    assert technician["properties"]["user_id"]["format"] == "uuid"
    assert technician["properties"]["user_id"][
        "x-visit-schedule-request-field"
    ] == "synthetic_technician_id"
    assert "employee_no" not in technician["properties"]


def test_visit_schedule_contract_consumes_synthetic_technician_uuid():
    visit_schema = load_yaml(
        OPENAPI_DIR
        / "components"
        / "schemas"
        / "visit"
        / "UpdateVisitScheduleRequest.yaml"
    )

    assert "synthetic_technician_id" in visit_schema["required"]
    assert visit_schema["properties"]["synthetic_technician_id"] == {
        "type": "string",
        "format": "uuid",
        "description": "가상 방문기사 공개 UUID",
    }
