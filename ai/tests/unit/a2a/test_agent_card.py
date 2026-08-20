"""WaterBridge Safety A2A Agent Card 테스트."""

from ai.app.integrations.a2a.agent_card import (
    SAFETY_SKILL_ID,
    build_safety_agent_card,
)


def test_safety_agent_card_exposes_expected_capability():
    card = build_safety_agent_card(
        url="http://127.0.0.1:9101/a2a",
    )

    assert card.name == "WaterBridge Safety Agent"
    assert card.version == "1.0.0"

    # ---------------------------------------------------------------
    # A2A endpoint 확인
    # ---------------------------------------------------------------
    assert len(card.supported_interfaces) == 1

    interface = card.supported_interfaces[0]

    assert interface.protocol_binding == "JSONRPC"
    assert interface.protocol_version == "1.0"
    assert interface.url == "http://127.0.0.1:9101/a2a"

    # ---------------------------------------------------------------
    # Agent Capability 확인
    # ---------------------------------------------------------------
    assert card.capabilities.streaming is False
    assert card.capabilities.extended_agent_card is False

    # ---------------------------------------------------------------
    # Safety Skill 확인
    # ---------------------------------------------------------------
    assert len(card.skills) == 1

    skill = card.skills[0]

    assert skill.id == SAFETY_SKILL_ID
    assert skill.name == "WaterBridge Safety Assessment"

    assert "application/json" in skill.input_modes
    assert "application/json" in skill.output_modes

    # Product Context를 소비하는 Safety Agent임을
    # Agent Card에서도 명확하게 표현합니다.
    assert "product-context" in skill.tags
