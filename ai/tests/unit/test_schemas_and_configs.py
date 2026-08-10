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
from ai.app.schemas.common import ModelMetadata, ProcessingTrace, ValidationResult, AiStage
from ai.app.schemas.symptom import MissingField, FollowUpQuestion


def test_pydantic_common_schemas():
    """공통 스키마 및 Enum 생성 검증"""
    assert RiskLevel.GENERAL.value == "general"
    assert UsageGuidanceStatus.TOTAL_STOP.value == "TOTAL_STOP"

    trace = TraceContext(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b307",
        correlation_id="018f2f9b-7c30-7981-b541-1a987c88b499",
        ai_request_id="ai-req-001",
        state_version=1,
    )
    assert str(trace.inquiry_id) == "018f2f9b-7c30-7981-b541-1a987c88b307"
    assert str(trace.correlation_id) == "018f2f9b-7c30-7981-b541-1a987c88b499"


def test_symptom_analysis_result_schema():
    """통합 분석 응답 모델 객체 생성 검증"""
    result = SymptomAnalysisResult(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b308",
        correlation_id="018f2f9b-7c30-7981-b541-1a987c88b499",
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
        "examples/fallback/vector-not-configured-error.json",
        "examples/fallback/retrieval-failed-error.json",
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
    assert request_contract["x-contract-version"] == response_contract["x-contract-version"] == "2.0.0"


def test_symptom_request_contract_and_runtime_reject_same_boundaries():
    schema = _validator(Path("contracts/ai/requests/SymptomAnalysisRequest.schema.json"))
    base = {
        "inquiry_id": "018f2f9b-7c30-7981-b541-1a987c88b309",
        "correlation_id": "018f2f9b-7c30-7981-b541-1a987c88b499",
        "ai_request_id": "ai-req-parity",
        "state_version": 1,
        "raw_symptom": "물이 나오지 않습니다.",
        "model_code": "WPUJAC104DWH",
    }
    invalid_payloads = [
        {**base, "inquiry_id": "DEMO-INQ-001"},
        {**base, "correlation_id": "not-a-uuid"},
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
        "correlation_id": "018f2f9b-7c30-7981-b541-1a987c88b499",
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
        lambda value: value.update(correlation_id="not-a-uuid"),
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
        assert schema["x-contract-version"] == "2.0.0"


@pytest.mark.parametrize(
    ("schema_path", "model", "payload", "accepted"),
    [
        ("common/MissingField.schema.json", MissingField,
         {"field_name": "occurrence_time", "reason": "발생 시점 확인 필요", "importance": "high"}, True),
        ("common/MissingField.schema.json", MissingField,
         {"field_name": "", "reason": "", "importance": "urgent"}, False),
        ("common/FollowUpQuestion.schema.json", FollowUpQuestion,
         {"question_id": "q1", "question_text": "언제 시작됐나요?", "options": ["오늘"], "target_field": "occurrence_time"}, True),
        ("common/FollowUpQuestion.schema.json", FollowUpQuestion,
         {"question_id": "q1", "question_text": "질문", "options": ["선택"] * 11, "target_field": "field"}, False),
        ("common/EvidenceReference.schema.json", EvidenceReference,
         {"document_title": "매뉴얼", "chunk_id": "RAG-1", "summary": "근거", "page_refs": [1], "verification_status": "official_verified"}, True),
        ("common/EvidenceReference.schema.json", EvidenceReference,
         {"document_title": "매뉴얼", "chunk_id": "RAG-1", "summary": "근거", "page_refs": [0], "verification_status": "official_verified"}, False),
        ("common/ModelMetadata.schema.json", ModelMetadata,
         {"model_name": "BAAI/bge-m3", "prompt_version": "v1", "tokens_used": 0, "latency_ms": 0}, True),
        ("common/ModelMetadata.schema.json", ModelMetadata,
         {"model_name": "", "prompt_version": "", "tokens_used": -1, "latency_ms": -1}, False),
        ("common/ProcessingTrace.schema.json", ProcessingTrace,
         {"stage": "FAILED", "status": "FAILED", "latency_ms": 0, "retry_count": 0, "error_code": "AI-FAILED-01"}, True),
        ("common/ProcessingTrace.schema.json", ProcessingTrace,
         {"stage": "FAILED", "status": "FAILED", "latency_ms": 0, "retry_count": 0, "error_code": "x" * 101}, False),
        ("common/ValidationResult.schema.json", ValidationResult,
         {"is_valid": True, "schema_valid": True, "grounding_valid": True, "safety_valid": True, "violations": []}, True),
        ("common/ValidationResult.schema.json", ValidationResult,
         {"is_valid": False, "schema_valid": False, "grounding_valid": True, "safety_valid": True, "violations": [""]}, False),
    ],
)
def test_common_contract_and_runtime_acceptance_parity(schema_path, model, payload, accepted):
    schema_accepts = not list(_validator(Path("contracts/ai") / schema_path).iter_errors(payload))
    try:
        model.model_validate(payload)
        runtime_accepts = True
    except ValidationError:
        runtime_accepts = False
    assert schema_accepts is accepted
    assert runtime_accepts is accepted


def test_error_contract_required_nullable_keys_match_runtime():
    payload = {
        "success": False,
        "inquiry_id": None,
        "correlation_id": None,
        "ai_request_id": None,
        "state_version": None,
        "error": {
            "code": "AI-FAILED-01",
            "message": "분석 실패",
            "details": None,
            "retryable": True,
            "failure_stage": "FAILED",
            "retry_count": 0,
        },
    }
    _validator(Path("contracts/ai/common/AIErrorResponse.schema.json")).validate(payload)
    assert ApiErrorResponse.model_validate(payload).model_dump(mode="json") == payload
    for required_key in ("success", "inquiry_id", "correlation_id", "ai_request_id", "state_version"):
        invalid = dict(payload)
        invalid.pop(required_key)
        assert list(_validator(Path("contracts/ai/common/AIErrorResponse.schema.json")).iter_errors(invalid))
        with pytest.raises(ValidationError):
            ApiErrorResponse.model_validate(invalid)


def test_every_ai_contract_has_runtime_valid_and_extra_field_parity():
    contract_root = Path("contracts/ai")
    symptom_example = json.loads(
        (contract_root / "examples/symptom-analysis/general-guidance.json").read_text(encoding="utf-8")
    )
    error_example = json.loads(
        (contract_root / "examples/symptom-analysis/validation-failed.json").read_text(encoding="utf-8")
    )
    consultation_example = json.loads(
        (contract_root / "examples/consultation-summary/summary-example.json").read_text(encoding="utf-8")
    )
    technician_example = json.loads(
        (contract_root / "examples/technician-report/report-example.json").read_text(encoding="utf-8")
    )
    response = symptom_example["response"]
    matrix = {
        "common/AIErrorResponse.schema.json": (ApiErrorResponse, error_example["error_response"]),
        "common/EvidenceReference.schema.json": (EvidenceReference, response["evidence_references"][0]),
        "common/FollowUpQuestion.schema.json": (FollowUpQuestion, {
            "question_id": "q1", "question_text": "언제 시작됐나요?", "options": [], "target_field": "occurrence_time",
        }),
        "common/MissingField.schema.json": (MissingField, {
            "field_name": "occurrence_time", "reason": "발생 시점 확인 필요", "importance": "medium",
        }),
        "common/ModelMetadata.schema.json": (ModelMetadata, {
            "model_name": "BAAI/bge-m3", "prompt_version": "v1", "tokens_used": 0, "latency_ms": 0,
        }),
        "common/ProcessingTrace.schema.json": (ProcessingTrace, {
            "stage": "COMPLETED", "status": "SUCCEEDED", "latency_ms": 1, "retry_count": 0, "error_code": None,
        }),
        "common/SafetyAssessment.schema.json": (SafetyAssessment, response["safety_assessment"]),
        "common/StructuredSymptom.schema.json": (StructuredSymptom, response["structured_symptom"]),
        "common/UsageGuidance.schema.json": (UsageGuidance, response["usage_guidance"]),
        "common/ValidationResult.schema.json": (ValidationResult, {
            "is_valid": True, "schema_valid": True, "grounding_valid": True, "safety_valid": True, "violations": [],
        }),
        "requests/ConsultationSummaryRequest.schema.json": (ConsultationSummaryRequest, consultation_example["request"]),
        "requests/SymptomAnalysisRequest.schema.json": (SymptomAnalysisApiRequest, symptom_example["request"]),
        "requests/TechnicianReportRequest.schema.json": (TechnicianReportRequest, technician_example["request"]),
        "responses/ConsultationSummaryResponse.schema.json": (ConsultationSummaryResult, consultation_example["response"]),
        "responses/SymptomAnalysisResponse.schema.json": (SymptomAnalysisResult, response),
        "responses/TechnicianReportResponse.schema.json": (TechnicianReportResult, technician_example["response"]),
    }
    schema_paths = {
        path.relative_to(contract_root).as_posix()
        for path in contract_root.rglob("*.schema.json")
    }
    assert set(matrix) == schema_paths
    for relative_path, (model, payload) in matrix.items():
        validator = _validator(contract_root / relative_path)
        validator.validate(payload)
        model.model_validate(payload)
        invalid = {**payload, "__unexpected__": True}
        assert list(validator.iter_errors(invalid))
        with pytest.raises(ValidationError):
            model.model_validate(invalid)


def test_backend_integration_environment_manifest_is_reproducible():
    manifest = json.loads(
        Path("ai/configs/backend_integration_environment.json").read_text(encoding="utf-8")
    )
    assert manifest["python_version"] == "3.13.13"
    assert manifest["dependency_manifest"] == "ai/requirements.lock"
    assert manifest["contract_version"] == "2.0.0"
    assert manifest["ai_modes"] == ["mock", "local"]
    assert manifest["required_environment_variable_names"]["mock"] == []
    assert manifest["required_environment_variable_names"]["local_general_or_caution"] == [
        "AI_VECTOR_DSN",
        "AI_EMBEDDING_REVISION",
    ]
    assert "AI_MAX_IN_FLIGHT_WORKERS" in manifest["optional_environment_variable_names"]
    assert "POST http://127.0.0.1:8001/api/v1/ai/analyze" in manifest["analysis_endpoint"]
    assert manifest["db_seed_or_reset_command"]["mock"] == "NOT_REQUIRED"
    assert {item["http_status"] for item in manifest["missing_configuration_contract"]} == {503}
