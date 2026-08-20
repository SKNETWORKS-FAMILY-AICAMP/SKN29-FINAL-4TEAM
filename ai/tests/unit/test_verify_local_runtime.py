"""실제 Local Runtime Identity Gate의 fail-closed 동작 테스트."""

from types import SimpleNamespace

import pytest

from ai.scripts.verify_local_runtime import (
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

    def __init__(
        self,
        *,
        tokens_used=18,
        include_evidence=True,
        three_model=False,
    ):
        self.tokens_used = tokens_used
        self.include_evidence = include_evidence
        self.three_model = three_model
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
            correlation_id=kwargs["correlation_id"],
        )
        context = SimpleNamespace(
            model_metadata=SimpleNamespace(
                model_name="gpt-4.1-mini-2025-04-14",
                prompt_version="customer_guidance/v2",
                tokens_used=self.tokens_used,
            )
        )
        return SimpleNamespace(
            context=context,
            to_analysis_result=lambda: response,
        )


def _set_required_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setenv("AI_VECTOR_DSN", "postgresql://test-only")
    monkeypatch.setenv("AI_EMBEDDING_REVISION", "a" * 40)
    monkeypatch.setenv("AI_VECTOR_TABLE_NAME", "backend_ai_rag_chunks_v1")
    monkeypatch.setenv("AI_LLM_MODEL", "gpt-4.1-mini")


def test_local_runtime_gate_verifies_actual_identity_without_exposing_secrets(monkeypatch):
    _set_required_environment(monkeypatch)

    router = FakeRouter()
    result = verify_local_runtime(router)

    assert result["result"] == "PASS"
    assert result["runtime_profile"] == "mvp"
    assert result["identity_chunk_count"] == 7
    assert result["provider_models"] == ["gpt-4.1-mini-2025-04-14"]
    assert result["prompt_version"] == "customer_guidance/v2"
    assert result["tokens_used"] == 18
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
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(LocalRuntimeFailure, match="OPENAI_API_KEY"):
        verify_local_runtime(FakeRouter())


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
        verify_local_runtime(router)


def test_three_model_runtime_gate_verifies_all_models_and_53_child_identity(
    monkeypatch,
):
    _set_required_environment(monkeypatch)
    monkeypatch.setenv("AI_RAG_RUNTIME_PROFILE", "three_model_integration")
    router = FakeRouter(three_model=True)

    result = verify_local_runtime(router)

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
