"""WaterBridge A2A Safety Server 기본 테스트."""

from fastapi.testclient import TestClient

from ai.app.integrations.a2a.server import (
    create_app,
)


def test_a2a_server_exposes_health_and_agent_card():
    app = create_app(
        public_base_url="http://127.0.0.1:9101",
    )

    with TestClient(app) as client:
        health = client.get("/health")

        assert health.status_code == 200
        assert health.json() == {
            "status": "ok",
            "agent": "waterbridge-safety",
        }

        card = client.get(
            "/.well-known/agent-card.json"
        )

        assert card.status_code == 200

        payload = card.json()

        assert (
            payload["name"]
            == "WaterBridge Safety Agent"
        )

        interfaces = payload[
            "supportedInterfaces"
        ]

        assert len(interfaces) == 1

        assert (
            interfaces[0]["url"]
            == "http://127.0.0.1:9101/a2a"
        )
