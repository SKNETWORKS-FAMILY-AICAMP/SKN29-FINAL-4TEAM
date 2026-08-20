"""WaterBridge Safety Agent의 A2A Agent Card 정의."""

from __future__ import annotations

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)


SAFETY_SKILL_ID = "waterbridge-safety-assessment"


def build_safety_agent_card(
    *,
    url: str,
    protocol_version: str = "1.0",
) -> AgentCard:
    """
    Safety Agent가 어떤 기능을 제공하는지 A2A 표준 형식으로 설명합니다.

    중요한 점:
    - 실제 Safety 판단은 이 파일에서 하지 않습니다.
    - 기존 RiskClassifier를 사용하는 SafetyA2AAdapter가 실제 판단을 담당합니다.
    - 이 Card는 "어디에 있고, 무엇을 할 수 있는 Agent인지"만 광고합니다.
    """

    safety_skill = AgentSkill(
        id=SAFETY_SKILL_ID,
        name="WaterBridge Safety Assessment",
        description=(
            "고객 증상과 Product Context를 받아 기존 WaterBridge "
            "RiskClassifier 기반 SafetyAssessment를 반환합니다."
        ),
        tags=[
            "waterbridge",
            "safety",
            "risk-assessment",
            "product-context",
        ],
        input_modes=[
            "application/json",
        ],
        output_modes=[
            "application/json",
        ],
        examples=[
            (
                "WPUJAC104DWH 고객의 냉수 이상 증상에 대해 "
                "Safety 위험도를 판정합니다."
            ),
        ],
    )

    return AgentCard(
        name="WaterBridge Safety Agent",
        description=(
            "WaterBridge Multi-Agent Runtime에서 Safety 판단을 담당하는 "
            "A2A Agent입니다. 기존 RiskClassifier를 재사용합니다."
        ),

        # A2A 1.x에서는 AgentCard.url 대신
        # supported_interfaces 내부의 AgentInterface를 사용합니다.
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                protocol_version=protocol_version,
                url=url,
            ),
        ],

        version="1.0.0",

        default_input_modes=[
            "application/json",
        ],
        default_output_modes=[
            "application/json",
        ],

        # 현재 PoC는 Streaming이나 Push Notification을 요구하지 않습니다.
        capabilities=AgentCapabilities(
            streaming=False,
            extended_agent_card=False,
        ),

        skills=[
            safety_skill,
        ],
    )
