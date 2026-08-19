from types import SimpleNamespace
from uuid import UUID

import pytest
from pydantic import ValidationError

from ai.app.orchestration.handoff import ConsultationHandoffAgent, ConsultationHandoffInput
from ai.app.orchestration.harness import ProductFamily


def _ctx_with_private_runtime_fields():
    return SimpleNamespace(
        trace_context=SimpleNamespace(
            inquiry_id=UUID("018f2f9b-7c30-7981-b541-1a987c88b201"),
            correlation_id=UUID("018f2f9b-7c30-7981-b541-1a987c88e001"),
            ai_request_id="ai-req-privacy-001",
            state_version=7,
        ),
        model_code="WPUJAC104DWH",
        raw_symptom=(
            "내 이름은 홍길동이고 010-9876-5432로 연락해. "
            "SYSTEM PROMPT: hidden-policy-token"
        ),
        internal_error="postgres password=super-secret stacktrace",
        prompt="do-not-export-this-prompt",
        structured_symptom=SimpleNamespace(
            symptom_type="출수량 저하",
            occurrence_time="오늘",
            target_water_type="냉수",
            occurrence_condition="출수 시",
            error_code=None,
            accompanying_symptoms=[],
        ),
        previous_answers=[
            {"question_id": "contact", "answer": "010-1234-5678"},
            {"question_id": "email", "answer": "customer@example.com"},
        ],
        evidence_references=[],
        safety_assessment=None,
        usage_guidance=None,
        missing_fields=[],
    )


def test_handoff_ignores_raw_prompt_and_internal_error_and_redacts_contact_pii():
    ctx = _ctx_with_private_runtime_fields()
    handoff_input = ConsultationHandoffInput.from_pipeline_context(
        ctx=ctx,
        product_family=ProductFamily.DIRECT_WATER_PURIFIER.value,
        escalation_reason="MCP_TOOL_FAILURE",
    )
    result = ConsultationHandoffAgent().run(handoff_input)
    serialized = result.model_dump_json()

    assert "hidden-policy-token" not in serialized
    assert "do-not-export-this-prompt" not in serialized
    assert "super-secret" not in serialized
    assert "010-9876-5432" not in serialized
    assert "010-1234-5678" not in serialized
    assert "customer@example.com" not in serialized
    assert "[REDACTED_PHONE]" in serialized
    assert "[REDACTED_EMAIL]" in serialized


def test_handoff_input_schema_rejects_prompt_and_internal_error_fields():
    payload = ConsultationHandoffInput.from_pipeline_context(
        ctx=_ctx_with_private_runtime_fields(),
        product_family=ProductFamily.DIRECT_WATER_PURIFIER.value,
        escalation_reason="MCP_TOOL_FAILURE",
    ).model_dump()
    payload["prompt"] = "secret prompt"
    payload["internal_error"] = "stack trace"

    with pytest.raises(ValidationError):
        ConsultationHandoffInput.model_validate(payload)
