"""Backend↔AI F01~F12 결정적 Fixture의 AI 소유 구간 검증."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai.app.bootstrap import create_app
from ai.app.common.timeout import PipelineStageTimeoutError
from ai.app.generation.customer_guidance import guidance_generator
from ai.app.generation.customer_guidance.models import GuidanceGenerationResult
from ai.app.integrations.llm import GuidanceLLMResponse, LLMUsage
from ai.app.interfaces.http.routes import analysis_routes
from ai.app.retrieval import RetrievedChunk


MANIFEST_PATH = Path("ai/evaluation/datasets/backend_integration/fixture_manifest.json")


class EmptySearchService:
    def search(self, *args, **kwargs):
        return []


class EvidenceSearchService:
    def search(self, *args, **kwargs):
        return [
            RetrievedChunk(
                chunk_id="RAG-WPUJAC104DWH-COLD-FIXTURE",
                document_title="WPU-JAC104D 사용설명서",
                document_version="REV.00",
                page=37,
                page_refs=[37],
                manual_model="WPUJAC104DWH",
                model_code="WPUJAC104DWH",
                product_generation="D",
                content="냉수 온도가 높으면 잠시 기다린 뒤 다시 확인합니다.",
                similarity_score=0.91,
                official_url="https://example.invalid/official-manual",
                verification_status="official_verified",
                allowed_use=True,
            )
        ]


class FlakySearchService:
    def __init__(self):
        self.calls = 0

    def search(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise ConnectionError("fixture transient failure")
        return EvidenceSearchService().search(*args, **kwargs)


class TransientFailureSearchService:
    def search(self, *args, **kwargs):
        raise ConnectionError("fixture persistent transient failure")


class NonTransientFailureSearchService:
    def search(self, *args, **kwargs):
        raise ValueError("fixture non-transient provider failure")


class FixtureGuidanceLLMClient:
    def generate_guidance(self, request, *, timeout_seconds):
        return GuidanceLLMResponse(
            output=GuidanceGenerationResult(
                message="공식 안내에 따라 제품 상태를 확인해 주세요.",
                next_actions=["안내된 자가조치 단계별 점검 수행"],
            ),
            model_name="gpt-4.1-mini",
            usage=LLMUsage(total_tokens=12),
            latency_ms=5.0,
        )


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _case(case_id: str) -> dict:
    return next(case for case in _manifest()["cases"] if case["id"] == case_id)


def _fixture_document(case: dict) -> dict:
    return json.loads(Path(case["input_file"]).read_text(encoding="utf-8"))


def _configure_driver(monkeypatch, driver: str) -> None:
    monkeypatch.delenv("AI_VECTOR_DSN", raising=False)
    monkeypatch.delenv("AI_EMBEDDING_REVISION", raising=False)
    services = {
        "IN_PROCESS_HTTP_EVIDENCE_ADAPTER": EvidenceSearchService,
        "IN_PROCESS_HTTP_EMPTY_ADAPTER": EmptySearchService,
        "IN_PROCESS_HTTP_FLAKY_ADAPTER": FlakySearchService,
        "IN_PROCESS_HTTP_TRANSIENT_FAILURE_ADAPTER": TransientFailureSearchService,
        "IN_PROCESS_HTTP_NON_TRANSIENT_FAILURE_ADAPTER": NonTransientFailureSearchService,
    }
    service_factory = services.get(driver)
    if service_factory is not None:
        service = service_factory()
        monkeypatch.setattr(
            analysis_routes.PipelineRouter,
            "_configured_search_service",
            staticmethod(lambda: service),
        )
    if driver in {
        "IN_PROCESS_HTTP_EVIDENCE_ADAPTER",
        "IN_PROCESS_HTTP_FLAKY_ADAPTER",
    }:
        monkeypatch.setattr(
            guidance_generator.OpenAIResponsesLLMClient,
            "from_environment",
            classmethod(lambda cls: FixtureGuidanceLLMClient()),
        )
    if driver == "IN_PROCESS_HTTP_STAGE_TIMEOUT_ADAPTER":
        def stage_timeout(*args, **kwargs):
            raise PipelineStageTimeoutError("RETRIEVING")

        monkeypatch.setattr(analysis_routes.PipelineRouter, "run_pipeline", stage_timeout)


def _assert_expected(case: dict, response, request_body: dict) -> None:
    expected = case["expected"]
    body = response.json()
    assert response.status_code == expected["http_status"]
    if expected.get("correlation_id", request_body["correlation_id"]) is None:
        assert body["correlation_id"] is None
        assert "X-Correlation-ID" not in response.headers
    else:
        assert body["correlation_id"] == request_body["correlation_id"]
        assert response.headers["X-Correlation-ID"] == request_body["correlation_id"]

    if response.status_code == 200:
        if "status" in expected:
            assert body["status"] == expected["status"]
        if "failure_stage" in expected:
            assert body["failure_stage"] == expected["failure_stage"]
        if "retry_count" in expected:
            assert body["retry_count"] == expected["retry_count"]
        if "minimum_evidence_count" in expected:
            assert len(body["evidence_references"]) >= expected["minimum_evidence_count"]
        if "evidence_count" in expected:
            assert len(body["evidence_references"]) == expected["evidence_count"]
        if "risk_level" in expected:
            assert body["safety_assessment"]["risk_level"] == expected["risk_level"]
        if "matched_safety_rule_ids" in expected:
            assert body["safety_assessment"]["matched_safety_rule_ids"] == expected[
                "matched_safety_rule_ids"
            ]
        if "guidance_status" in expected:
            assert body["usage_guidance"]["guidance_status"] == expected["guidance_status"]
        if "repeated_question_id" in expected:
            returned_ids = {item["question_id"] for item in body["followup_questions"]}
            assert (expected["repeated_question_id"] in returned_ids) is expected["repeated"]
            assert body["state_version"] == expected["state_version"]
    else:
        error = body["error"]
        assert error["code"] == expected["error_code"]
        assert error["failure_stage"] == expected["failure_stage"]
        assert error["retryable"] is expected["retryable"]
        assert error["retry_count"] == expected["retry_count"]


def test_fixture_manifest_has_all_cases_and_explicit_ownership():
    manifest = _manifest()
    assert manifest["contract_version"] == "3.0.0"
    assert [case["id"] for case in manifest["cases"]] == [f"F{index:02d}" for index in range(1, 13)]
    assert _case("F11")["owner"] == "BACKEND"
    assert _case("F12")["owner"] == "AI_AND_BACKEND"
    for case in manifest["cases"]:
        if case["input_file"] != "NOT_APPLICABLE":
            assert Path(case["input_file"]).is_file()


@pytest.mark.parametrize(
    "case_id",
    ["F01", "F02", "F03", "F04", "F05", "F06", "F07", "F08", "F09", "F10", "F12"],
)
def test_ai_owned_backend_integration_fixture(case_id, monkeypatch):
    case = _case(case_id)
    fixture_document = _fixture_document(case)
    request_body = fixture_document[case["input_key"]]
    headers = fixture_document.get(case.get("headers_key", ""), {})
    _configure_driver(monkeypatch, case["execution_driver"])
    with TestClient(create_app()) as client:
        response = client.post(
            f"/api/v1/ai/analyze?mode={case['mode']}",
            json=request_body,
            headers=headers,
        )
    _assert_expected(case, response, request_body)
