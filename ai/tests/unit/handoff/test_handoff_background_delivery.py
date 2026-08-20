"""Background scheduling boundary for consultation handoffs."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from ai.app.interfaces.http.routes import analysis_routes
from ai.app.orchestration.handoff import ConsultationHandoffResult


def _handoff() -> ConsultationHandoffResult:
    return ConsultationHandoffResult(
        inquiry_id=UUID("018f2f9b-7c30-7981-b541-1a987c88b201"),
        correlation_id=UUID("018f2f9b-7c30-7981-b541-1a987c88e001"),
        ai_request_id="ai-handoff-schedule-001",
        model_code="WPUJAC104DWH",
        product_family="DIRECT_WATER_PURIFIER",
        customer_symptom_summary="상담 확인이 필요합니다.",
        questionnaire_answers=[],
        self_help_actions=[],
        evidence=[],
        safety_level="unknown",
        safety_requires_consultation=False,
        safety_notes=[],
        escalation_reason="NO_EVIDENCE",
        consultant_priority_checks=[],
        source_chunk_ids=[],
    )


class _Tasks:
    def __init__(self):
        self.calls = []

    def add_task(self, func, *args, **kwargs):
        self.calls.append((func, args, kwargs))


def _pipeline_result(handoff):
    return SimpleNamespace(
        reliability_runtime=SimpleNamespace(
            harness_runtime=SimpleNamespace(handoff=handoff)
        )
    )


def test_schedule_only_when_handoff_exists_and_delivery_enabled(monkeypatch):
    tasks = _Tasks()
    handoff = _handoff()
    monkeypatch.setattr(
        analysis_routes,
        "handoff_delivery_enabled",
        lambda: True,
    )

    scheduled = analysis_routes._schedule_handoff_delivery(
        tasks,
        _pipeline_result(handoff),
    )

    assert scheduled is True
    assert len(tasks.calls) == 1
    func, args, kwargs = tasks.calls[0]
    assert func is analysis_routes._deliver_handoff_background
    assert args == (handoff,)
    assert kwargs == {}


def test_schedule_is_noop_without_handoff(monkeypatch):
    tasks = _Tasks()
    monkeypatch.setattr(
        analysis_routes,
        "handoff_delivery_enabled",
        lambda: True,
    )

    scheduled = analysis_routes._schedule_handoff_delivery(
        tasks,
        _pipeline_result(None),
    )

    assert scheduled is False
    assert tasks.calls == []
