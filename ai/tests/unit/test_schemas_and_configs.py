"""Pydantic 스키마 및 안전 규칙 YAML 로딩 단위 테스트."""

import json
import os
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, RefResolver
import yaml
import pytest
from ai.app.schemas.common import RiskLevel, UsageGuidanceStatus, TraceContext
from ai.app.schemas.symptom import StructuredSymptom
from ai.app.schemas.safety import SafetyAssessment
from ai.app.schemas.guidance import UsageGuidance
from ai.app.schemas.pipeline import SymptomAnalysisResult
from pydantic import ValidationError
from ai.app.interfaces.http.request_models import SymptomAnalysisApiRequest
from ai.app.interfaces.http.response_models import ApiErrorResponse
from ai.app.schemas.retrieval import EvidenceReference
from ai.app.schemas.consultation_summary import ConsultationSummaryRequest, ConsultationSummaryResult
from ai.app.schemas.technician_report import TechnicianReportRequest, TechnicianReportResult


def test_pydantic_common_schemas():
    """공통 스키마 및 Enum 생성 검증"""
    assert RiskLevel.GENERAL.value == "general"
    assert UsageGuidanceStatus.TOTAL_STOP.value == "TOTAL_STOP"

    trace = TraceContext(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b307",
        correlation_id="test-corr-id-123",
        ai_request_id="ai-req-001",
        state_version=1,
    )
    assert str(trace.inquiry_id) == "018f2f9b-7c30-7981-b541-1a987c88b307"
    assert trace.correlation_id == "test-corr-id-123"


def test_symptom_analysis_result_schema():
    """통합 분석 응답 모델 객체 생성 검증"""
    result = SymptomAnalysisResult(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b308",
        correlation_id="corr-002",
        ai_request_id="ai-req-002",
        state_version=1,
        structured_symptom=StructuredSymptom(
            symptom_type="누수",
            accompanying_symptoms=["전원 불빛 깜빡임"],
            actions_taken=["밸브 잠금"]
        ),
        missing_fields=[],
        followup_questions=[],
        safety_assessment=SafetyAssessment(
            risk_level=RiskLevel.DANGER,
            priority="priority_consultation",
            requires_consultation=True,
            detected_risks=["제품 하부 누수"],
            safety_reason="전원 주변 누수 감지"
        ),
        usage_guidance=UsageGuidance(
            guidance_status=UsageGuidanceStatus.TOTAL_STOP,
            message="제품 하부 누수로 인해 정수기 사용을 즉시 중지하세요.",
            restricted_functions=["전체 출수 기능 중지"],
            next_actions=["원수 밸브 잠그기", "전원 차단"]
        ),
        evidence_references=[],
    )

    assert result.safety_assessment.risk_level == RiskLevel.DANGER
    assert result.usage_guidance.guidance_status == UsageGuidanceStatus.TOTAL_STOP
    schema_path = Path("contracts/ai/responses/SymptomAnalysisResponse.schema.json")
    _validator(schema_path).validate(result.model_dump(mode="json"))


def test_load_safety_rules_config():
    """safety_rules.yaml 로딩 및 검증"""
    config_path = os.path.join("ai", "configs", "safety_rules.yaml")
    assert os.path.exists(config_path)

    with open(config_path, "r", encoding="utf-8") as f:
        rules_yaml = yaml.safe_load(f)

    assert "rules" in rules_yaml
    assert "leak_danger" in rules_yaml["rules"]
    assert rules_yaml["rules"]["leak_danger"]["usage_guidance_status"] == "TOTAL_STOP"


def test_load_prohibited_expressions_config():
    """prohibited_expressions.yaml 로딩 및 검증"""
    config_path = os.path.join("ai", "configs", "prohibited_expressions.yaml")
    assert os.path.exists(config_path)

    with open(config_path, "r", encoding="utf-8") as f:
        prohibited_yaml = yaml.safe_load(f)

    assert "prohibited_diagnosis_phrases" in prohibited_yaml
    assert "prohibited_guarantee_phrases" in prohibited_yaml
    assert "고장이 확실합니다" in prohibited_yaml["prohibited_diagnosis_phrases"]


def _validator(schema_path: Path) -> Draft202012Validator:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft202012Validator(
        schema,
        resolver=RefResolver(base_uri=schema_path.resolve().as_uri(), referrer=schema),
        format_checker=FormatChecker(),
    )


@pytest.mark.parametrize("example_name", ["general-guidance.json", "danger-detected.json", "no-evidence.json"])
def test_ai_contract_examples_json_schema(example_name):
    """대표 요청과 응답을 실제 Draft 2020-12 JSON Schema로 검증한다."""
    contract_root = Path("contracts/ai")
    example = json.loads((contract_root / "examples/symptom-analysis" / example_name).read_text(encoding="utf-8"))
    _validator(contract_root / "requests/SymptomAnalysisRequest.schema.json").validate(example["request"])
    _validator(contract_root / "responses/SymptomAnalysisResponse.schema.json").validate(example["response"])


@pytest.mark.parametrize(
    ("example_path", "request_schema", "response_schema", "request_model", "response_model"),
    [
        (
            "examples/consultation-summary/summary-example.json",
            "requests/ConsultationSummaryRequest.schema.json",
            "responses/ConsultationSummaryResponse.schema.json",
            ConsultationSummaryRequest,
            ConsultationSummaryResult,
        ),
        (
            "examples/technician-report/report-example.json",
            "requests/TechnicianReportRequest.schema.json",
            "responses/TechnicianReportResponse.schema.json",
            TechnicianReportRequest,
            TechnicianReportResult,
        ),
    ],
)
def test_secondary_ai_contract_examples_round_trip(
    example_path, request_schema, response_schema, request_model, response_model
):
    contract_root = Path("contracts/ai")
    example = json.loads((contract_root / example_path).read_text(encoding="utf-8"))
    _validator(contract_root / request_schema).validate(example["request"])
    _validator(contract_root / response_schema).validate(example["response"])
    assert request_model.model_validate(example["request"]).model_dump(mode="json") == example["request"]
    assert response_model.model_validate(example["response"]).model_dump(mode="json") == example["response"]


@pytest.mark.parametrize(
    "example_path",
    [
        "examples/symptom-analysis/validation-failed.json",
        "examples/fallback/timeout-error.json",
    ],
)
def test_ai_error_examples_match_contract(example_path):
    contract_root = Path("contracts/ai")
    example = json.loads((contract_root / example_path).read_text(encoding="utf-8"))
    _validator(contract_root / "common/AIErrorResponse.schema.json").validate(example["error_response"])
    ApiErrorResponse.model_validate(example["error_response"])


def test_symptom_runtime_and_contract_top_level_fields_match():
    contract_root = Path("contracts/ai")
    request_contract = json.loads((contract_root / "requests/SymptomAnalysisRequest.schema.json").read_text(encoding="utf-8"))
    response_contract = json.loads((contract_root / "responses/SymptomAnalysisResponse.schema.json").read_text(encoding="utf-8"))
    assert set(SymptomAnalysisApiRequest.model_json_schema()["properties"]) == set(request_contract["properties"])
    assert set(SymptomAnalysisResult.model_json_schema()["properties"]) == set(response_contract["properties"])
    assert request_contract["x-contract-version"] == response_contract["x-contract-version"] == "1.1.0"


def test_symptom_request_contract_and_runtime_reject_same_boundaries():
    schema = _validator(Path("contracts/ai/requests/SymptomAnalysisRequest.schema.json"))
    base = {
        "inquiry_id": "018f2f9b-7c30-7981-b541-1a987c88b309",
        "correlation_id": "corr-parity",
        "ai_request_id": "ai-req-parity",
        "state_version": 1,
        "raw_symptom": "물이 나오지 않습니다.",
        "model_code": "WPUJAC104DWH",
    }
    invalid_payloads = [
        {**base, "inquiry_id": "DEMO-INQ-001"},
        {**base, "selected_symptoms": ["증상"] * 31},
        {**base, "selected_symptoms": [""]},
        {**base, "selected_symptoms": ["가" * 201]},
        {**base, "previous_answers": [{"question_id": "q", "answer_text": "a"}] * 51},
        {**base, "previous_answers": [{"question_id": "", "answer_text": "a"}]},
        {**base, "previous_answers": [{"question_id": "q", "answer_text": "가" * 1001}]},
    ]
    for payload in invalid_payloads:
        assert list(schema.iter_errors(payload))
        with pytest.raises(ValidationError):
            SymptomAnalysisApiRequest.model_validate(payload)


def test_error_and_evidence_nested_contract_constraints_are_enforced():
    valid_error = {
        "success": False,
        "inquiry_id": "018f2f9b-7c30-7981-b541-1a987c88b310",
        "correlation_id": "corr-error",
        "ai_request_id": "ai-req-error",
        "state_version": 1,
        "error": {
            "code": "AI-FAILED-01",
            "message": "분석 실패",
            "details": None,
            "retryable": True,
            "failure_stage": "FAILED",
            "retry_count": 0,
        },
    }
    for mutate in (
        lambda value: value.update(success=True),
        lambda value: value["error"].update(code="UNKNOWN"),
        lambda value: value["error"].update(message="가" * 501),
        lambda value: value["error"].update(failure_stage="COMPLETED"),
    ):
        payload = json.loads(json.dumps(valid_error))
        mutate(payload)
        with pytest.raises(ValidationError):
            ApiErrorResponse.model_validate(payload)

    with pytest.raises(ValidationError):
        EvidenceReference(
            document_title="매뉴얼",
            chunk_id="RAG-1",
            summary="근거",
            verification_status="unverified",
        )


def test_all_ai_contract_schemas_are_versioned_and_well_formed():
    schema_paths = sorted(Path("contracts/ai").rglob("*.schema.json"))
    assert schema_paths
    for schema_path in schema_paths:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        assert schema["$id"]
        assert schema["x-contract-version"] == "1.1.0"
