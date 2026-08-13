"""실제 Local Runtime Identity Gate의 fail-closed 동작 테스트."""

from types import SimpleNamespace

import pytest

from ai.scripts.verify_local_runtime import (
    EXPECTED_EVIDENCE_ID,
    LocalRuntimeFailure,
    verify_local_runtime,
)


class FakeRouter:
    def __init__(self, *, tokens_used=18, message="승인 Evidence 원문"):
        self.tokens_used = tokens_used
        self.message = message

    def run_pipeline(self, **kwargs):
        evidence = SimpleNamespace(
            chunk_id=EXPECTED_EVIDENCE_ID,
            verification_status=SimpleNamespace(value="official_verified"),
            summary="승인 Evidence 원문",
        )
        response = SimpleNamespace(
            status=SimpleNamespace(value="SUCCEEDED"),
            failure_stage=None,
            evidence_references=[evidence],
            usage_guidance=SimpleNamespace(message=self.message),
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

    result = verify_local_runtime(FakeRouter())

    assert result["result"] == "PASS"
    assert result["model_name"] == "gpt-4.1-mini-2025-04-14"
    assert result["prompt_version"] == "customer_guidance/v2"
    assert result["tokens_used"] == 18
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
        (FakeRouter(message="결정적 Fallback"), "Evidence 추출 문장"),
    ],
)
def test_local_runtime_gate_rejects_no_llm_or_deterministic_fallback(
    monkeypatch,
    router,
    message,
):
    _set_required_environment(monkeypatch)

    with pytest.raises(LocalRuntimeFailure, match=message):
        verify_local_runtime(router)
