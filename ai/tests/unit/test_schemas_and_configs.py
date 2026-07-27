"""Pydantic 스키마 및 안전 규칙 YAML 로딩 단위 테스트."""

import os
import yaml
import pytest
from ai.app.schemas.common import RiskLevel, UsageGuidanceStatus, TraceContext
from ai.app.schemas.symptom import StructuredSymptom
from ai.app.schemas.safety import SafetyAssessment
from ai.app.schemas.guidance import UsageGuidance
from ai.app.schemas.pipeline import SymptomAnalysisResult


def test_pydantic_common_schemas():
    """공통 스키마 및 Enum 생성 검증"""
    assert RiskLevel.GENERAL.value == "general"
    assert UsageGuidanceStatus.TOTAL_STOP.value == "TOTAL_STOP"

    trace = TraceContext(inquiry_id="DEMO-INQ-001", correlation_id="test-corr-id-123")
    assert trace.inquiry_id == "DEMO-INQ-001"
    assert trace.correlation_id == "test-corr-id-123"


def test_symptom_analysis_result_schema():
    """통합 분석 응답 모델 객체 생성 검증"""
    result = SymptomAnalysisResult(
        trace_context=TraceContext(inquiry_id="DEMO-INQ-002", correlation_id="corr-002"),
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
        model_metadata={"model_name": "gpt-4o-mini", "prompt_version": "v1"},
        processing_traces=[]
    )

    assert result.safety_assessment.risk_level == RiskLevel.DANGER
    assert result.usage_guidance.guidance_status == UsageGuidanceStatus.TOTAL_STOP


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
