"""실제 Local Runtime Identity Gate의 fail-closed 동작 테스트."""

import hashlib
import json
from types import SimpleNamespace

import pytest

import ai.scripts.verify_local_runtime as runtime_gate
from ai.scripts.verify_local_runtime import (
    EXPECTED_EMBEDDING_REVISION,
    LocalRuntimeFailure,
    verify_local_runtime,
)


class FakeRouter:
    EVIDENCE_BY_MODEL = {
        "WPUJAC104DWH": "RAG-WPUJAC104DWH-LOW-FLOW-001",
        "WPUIAC425SNW": "CHILD-WPUIAC425SNW-P005-LEAK-001",
        "WPUIAC606SNW": "CHILD-WPUIAC606SNW-P005-LEAK-001",
    }

    THREE_MODEL_JAC_EVIDENCE = "CHILD-WPUJAC104DWH-P005-LEAK-001"
    HANDOFF_REASONS = (
        "START_ANALYSIS",
        "RETRIEVAL_REQUIRED",
        "EVIDENCE_READY",
        "CARE_DECISION_READY",
    )
    HANDOFF_ROUTES = {
        "START_ANALYSIS": ("SUPERVISOR", "SYMPTOM_ANALYSIS"),
        "RETRIEVAL_REQUIRED": ("SYMPTOM_ANALYSIS", "EVIDENCE_ANALYSIS"),
        "EVIDENCE_READY": ("EVIDENCE_ANALYSIS", "CARE_DECISION"),
        "CARE_DECISION_READY": ("CARE_DECISION", "SUPERVISOR"),
    }

    def __init__(
        self,
        *,
        tokens_used=18,
        include_evidence=True,
        three_model=False,
        runtime_name="multi_agent",
        include_runtime_metadata=True,
        handoff_reasons=None,
        awaiting_customer_input=False,
        response_identity_overrides=None,
        handoff_identity_overrides=None,
    ):
        self.tokens_used = tokens_used
        self.include_evidence = include_evidence
        self.three_model = three_model
        self.runtime_name = runtime_name
        self.include_runtime_metadata = include_runtime_metadata
        self.handoff_reasons = (
            list(self.HANDOFF_REASONS)
            if handoff_reasons is None
            else list(handoff_reasons)
        )
        self.awaiting_customer_input = awaiting_customer_input
        self.response_identity_overrides = response_identity_overrides or {}
        self.handoff_identity_overrides = handoff_identity_overrides or {}
        self.calls = 0

    def run_pipeline(self, **kwargs):
        self.calls += 1
        evidence = []
        if self.include_evidence:
            chunk_id = self.EVIDENCE_BY_MODEL[kwargs["model_code"]]
            if self.three_model and kwargs["model_code"] == "WPUJAC104DWH":
                chunk_id = self.THREE_MODEL_JAC_EVIDENCE
            evidence = [
                SimpleNamespace(
                    chunk_id=chunk_id,
                    verification_status=SimpleNamespace(value="official_verified"),
                    summary="승인 Evidence 원문",
                )
            ]
        response = SimpleNamespace(
            status=SimpleNamespace(value="SUCCEEDED"),
            failure_stage=None,
            evidence_references=evidence,
            usage_guidance=SimpleNamespace(message="승인 Evidence 원문"),
            inquiry_id=kwargs["inquiry_id"],
            correlation_id=kwargs["correlation_id"],
            ai_request_id=kwargs["ai_request_id"],
            state_version=kwargs["state_version"],
            model_code=kwargs["model_code"],
            retry_count=0,
        )
        for field_name, value in self.response_identity_overrides.items():
            setattr(response, field_name, value)
        context = SimpleNamespace(
            model_metadata=SimpleNamespace(
                model_name="gpt-4.1-mini-2025-04-14",
                prompt_version="customer_guidance/v4",
                tokens_used=self.tokens_used,
            )
        )
        multi_agent_metadata = None
        if self.runtime_name == "multi_agent" and self.include_runtime_metadata:
            handoffs = []
            for hop_count, reason_code in enumerate(self.handoff_reasons, start=1):
                from_agent, to_agent = self.HANDOFF_ROUTES.get(
                    reason_code,
                    ("SUPERVISOR", "SUPERVISOR"),
                )
                values = {
                    "inquiry_id": kwargs["inquiry_id"],
                    "correlation_id": kwargs["correlation_id"],
                    "ai_request_id": kwargs["ai_request_id"],
                    "state_version": kwargs["state_version"],
                    "hop_count": hop_count,
                    "retry_count": 0,
                }
                values.update(self.handoff_identity_overrides)
                handoffs.append(
                    SimpleNamespace(
                        from_agent=SimpleNamespace(value=from_agent),
                        to_agent=SimpleNamespace(value=to_agent),
                        reason_code=SimpleNamespace(value=reason_code),
                        **values,
                    )
                )
            multi_agent_metadata = SimpleNamespace(
                runtime_name="multi_agent",
                hop_count=len(handoffs),
                handoffs=handoffs,
                awaiting_customer_input=self.awaiting_customer_input,
            )
        return SimpleNamespace(
            context=context,
            runtime_name=self.runtime_name,
            multi_agent_metadata=multi_agent_metadata,
            to_analysis_result=lambda: response,
        )


@pytest.fixture(autouse=True)
def _clean_source_identity(monkeypatch):
    monkeypatch.setattr(
        runtime_gate,
        "_git_identity",
        lambda: {
            "branch": "dongyoon",
            "git_sha": "a" * 40,
            "git_dirty": False,
        },
    )


def _set_required_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setenv("AI_VECTOR_DSN", "postgresql://test-only")
    monkeypatch.setenv("AI_EMBEDDING_REVISION", EXPECTED_EMBEDDING_REVISION)
    monkeypatch.setenv("AI_VECTOR_TABLE_NAME", "backend_ai_rag_chunks_v1")
    monkeypatch.setenv("AI_LLM_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("AI_PIPELINE_RUNTIME", "multi_agent")
    monkeypatch.setenv("AI_RETRIEVAL_TRANSPORT", "direct")
    monkeypatch.setenv("AI_RAG_RUNTIME_PROFILE", "mvp")


def test_local_runtime_gate_verifies_actual_identity_without_exposing_secrets(monkeypatch):
    _set_required_environment(monkeypatch)

    router = FakeRouter()
    result = verify_local_runtime(router, environment_id="TEAM_DB_STAGING")

    assert result["result"] == "PASS"
    assert result["schema_version"] == "1.0.0"
    assert result["evidence_scope"] == "LOCAL_RETRIEVER_PROVIDER_RUNTIME"
    assert result["environment_id"] == "TEAM_DB_STAGING"
    assert result["python_version"] == "3.13.13"
    assert len(result["source"]["git_sha"]) == 40
    assert result["pipeline_runtime"] == "multi_agent"
    assert result["retrieval_transport"] == "direct"
    assert result["runtime_profile"] == "mvp"
    assert result["identity_chunk_count"] == 7
    assert result["identity_chunk_count_source"] == (
        "CANONICAL_IDENTITY_FILE_EXPECTATION"
    )
    assert result["database_row_count"] is None
    assert result["database_row_count_status"] == "NOT_VERIFIED_BY_THIS_GATE"
    assert result["database_readonly_permission_status"] == (
        "NOT_VERIFIED_BY_THIS_GATE"
    )
    assert result["embedding_revision"] == EXPECTED_EMBEDDING_REVISION
    assert result["provider_adapter"] == "OPENAI_RESPONSES"
    assert result["provider_endpoint_class"] == "OPENAI_PUBLIC_API"
    assert result["provider_models"] == ["gpt-4.1-mini-2025-04-14"]
    assert result["prompt_version"] == "customer_guidance/v4"
    assert result["tokens_used"] == 18
    assert result["evidence_count"] == 1
    assert result["evidence_unique_count"] == 1
    assert len(result["evidence_id_set_sha256"]) == 64
    assert result["public_runtime_activation_source"] == "RAG_PROFILE_POLICY"
    assert result["public_deployment_status"] == "NOT_VERIFIED_BY_THIS_GATE"
    assert result["runtime_executions"] == [
        {
            "model_code": "WPUJAC104DWH",
            "runtime_name": "multi_agent",
            "hop_count": 4,
            "handoff_reason_codes": list(FakeRouter.HANDOFF_REASONS),
            "awaiting_customer_input": False,
            "public_retry_count": 0,
        }
    ]
    assert result["owner_evidence_boundaries"] == {
        "harness_hitl_consultation_handoff": "OWNER_EVIDENCE_REQUIRED",
        "backend_same_inquiry_persistence": "NOT_VERIFIED_BY_THIS_GATE",
        "web_mobile_projection": "NOT_VERIFIED_BY_THIS_GATE",
    }
    assert "evidence_ids" not in result
    integrity = result["integrity"]
    unhashed = dict(result)
    unhashed.pop("integrity")
    expected_payload_hash = hashlib.sha256(
        json.dumps(
            unhashed,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest().upper()
    assert integrity["payload_sha256"] == expected_payload_hash
    assert router.calls == 1
    assert "test-only-key" not in str(result)
    assert "postgresql://" not in str(result)


def test_local_runtime_gate_rejects_missing_environment(monkeypatch):
    for name in (
        "OPENAI_API_KEY",
        "AI_VECTOR_DSN",
        "AI_EMBEDDING_REVISION",
        "AI_VECTOR_TABLE_NAME",
        "AI_LLM_MODEL",
        "AI_PIPELINE_RUNTIME",
        "AI_RETRIEVAL_TRANSPORT",
        "AI_RAG_RUNTIME_PROFILE",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(LocalRuntimeFailure, match="OPENAI_API_KEY"):
        verify_local_runtime(FakeRouter(), environment_id="UNIT_TEST")


@pytest.mark.parametrize(
    ("router", "message"),
    [
        (FakeRouter(tokens_used=0), "Token 사용 증거"),
        (FakeRouter(include_evidence=False), "Canonical Child Evidence"),
    ],
)
def test_local_runtime_gate_rejects_missing_provider_usage_or_evidence(
    monkeypatch,
    router,
    message,
):
    _set_required_environment(monkeypatch)

    with pytest.raises(LocalRuntimeFailure, match=message):
        verify_local_runtime(router, environment_id="UNIT_TEST")


@pytest.mark.parametrize(
    ("router", "message"),
    [
        (FakeRouter(runtime_name="single_rag"), "요청한 Runtime과 다릅니다"),
        (
            FakeRouter(include_runtime_metadata=False),
            "Multi-Agent 실행 Metadata가 없습니다",
        ),
        (
            FakeRouter(handoff_reasons=["START_ANALYSIS"]),
            "필수 Handoff Sequence 증거가 없습니다",
        ),
        (
            FakeRouter(awaiting_customer_input=True),
            "고객 입력 대기 상태",
        ),
    ],
)
def test_local_runtime_gate_rejects_incomplete_runtime_execution_evidence(
    monkeypatch,
    router,
    message,
):
    _set_required_environment(monkeypatch)

    with pytest.raises(LocalRuntimeFailure, match=message):
        verify_local_runtime(router, environment_id="UNIT_TEST")


def test_local_runtime_gate_rejects_response_trace_identity_mismatch(monkeypatch):
    _set_required_environment(monkeypatch)
    router = FakeRouter(
        response_identity_overrides={"correlation_id": "wrong-correlation-id"}
    )

    with pytest.raises(LocalRuntimeFailure, match="Trace 또는 제품 Identity"):
        verify_local_runtime(router, environment_id="UNIT_TEST")


def test_local_runtime_gate_rejects_handoff_trace_identity_mismatch(monkeypatch):
    _set_required_environment(monkeypatch)
    router = FakeRouter(
        handoff_identity_overrides={"correlation_id": "wrong-correlation-id"}
    )

    with pytest.raises(LocalRuntimeFailure, match="Handoff Trace Identity"):
        verify_local_runtime(router, environment_id="UNIT_TEST")


def test_local_runtime_gate_rejects_unpinned_embedding_revision(monkeypatch):
    _set_required_environment(monkeypatch)
    monkeypatch.setenv("AI_EMBEDDING_REVISION", "b" * 40)

    with pytest.raises(LocalRuntimeFailure, match="Embedding Revision"):
        verify_local_runtime(FakeRouter(), environment_id="UNIT_TEST")


def test_local_runtime_gate_rejects_custom_provider_endpoint(monkeypatch):
    _set_required_environment(monkeypatch)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://provider-proxy.example/v1")

    with pytest.raises(LocalRuntimeFailure, match="공식 OpenAI Provider Endpoint") as exc:
        verify_local_runtime(FakeRouter(), environment_id="UNIT_TEST")

    assert "provider-proxy.example" not in str(exc.value)


def test_local_runtime_gate_rejects_wrong_python_version(monkeypatch):
    _set_required_environment(monkeypatch)
    monkeypatch.setattr(runtime_gate.platform, "python_version", lambda: "3.13.12")

    with pytest.raises(LocalRuntimeFailure, match="Python Version"):
        verify_local_runtime(FakeRouter(), environment_id="UNIT_TEST")


def test_local_runtime_gate_rejects_dirty_worktree_when_generating_evidence(
    monkeypatch,
):
    _set_required_environment(monkeypatch)
    monkeypatch.setattr(
        runtime_gate,
        "_git_identity",
        lambda: {"branch": "dongyoon", "git_sha": "a" * 40, "git_dirty": True},
    )

    with pytest.raises(LocalRuntimeFailure, match="Clean Worktree"):
        verify_local_runtime(
            FakeRouter(),
            environment_id="UNIT_TEST",
        )


def test_single_rag_runtime_gate_records_zero_agent_hops(monkeypatch):
    _set_required_environment(monkeypatch)
    monkeypatch.setenv("AI_PIPELINE_RUNTIME", "single_rag")

    result = verify_local_runtime(
        FakeRouter(runtime_name="single_rag"),
        environment_id="UNIT_TEST",
    )

    assert result["pipeline_runtime"] == "single_rag"
    assert result["runtime_executions"][0]["hop_count"] == 0
    assert result["runtime_executions"][0]["handoff_reason_codes"] == []


def test_three_model_runtime_gate_verifies_all_models_and_53_child_identity(
    monkeypatch,
):
    _set_required_environment(monkeypatch)
    monkeypatch.setenv("AI_RAG_RUNTIME_PROFILE", "three_model_integration")
    router = FakeRouter(three_model=True)

    result = verify_local_runtime(router, environment_id="TEAM_DB_STAGING")

    assert result["result"] == "PASS"
    assert result["runtime_profile"] == "three_model_integration"
    assert result["activation_scope"] == "INTEGRATION_VERIFICATION_ONLY"
    assert result["public_runtime_activation"] == "HOLD"
    assert result["identity_chunk_count"] == 53
    assert result["verified_model_codes"] == [
        "WPUIAC425SNW",
        "WPUIAC606SNW",
        "WPUJAC104DWH",
    ]
    assert router.calls == 3
    assert result["tokens_used"] == 54
    assert len(result["runtime_executions"]) == 3
    assert all(
        execution["runtime_name"] == "multi_agent"
        for execution in result["runtime_executions"]
    )
