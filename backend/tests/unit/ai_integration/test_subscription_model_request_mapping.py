from types import SimpleNamespace
from uuid import uuid4

import pytest

from integrations.ai.request_mapper import build_request_from_inquiry


@pytest.mark.parametrize(
    "model_code",
    ["WPUJAC104DWH", "WPUIAC425SNW", "WPUIAC606SNW"],
)
def test_ai_request_uses_owned_subscription_model_without_client_override(
    model_code,
):
    inquiry = SimpleNamespace(
        public_id=uuid4(),
        state_version=2,
        raw_text="소유 구독의 제품으로 증상을 분석해 주세요.",
        subscription=SimpleNamespace(
            product_model=SimpleNamespace(model_code=model_code)
        ),
        representative_symptom=None,
        ai_qa_entries=[],
    )

    payload = build_request_from_inquiry(
        inquiry,
        correlation_id=uuid4(),
        ai_request_id=uuid4(),
    )

    assert payload["model_code"] == model_code
    assert set(payload) == {
        "inquiry_id",
        "correlation_id",
        "ai_request_id",
        "state_version",
        "raw_symptom",
        "model_code",
        "selected_symptoms",
        "previous_answers",
    }
