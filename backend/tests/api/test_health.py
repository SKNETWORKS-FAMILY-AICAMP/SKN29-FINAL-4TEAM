"""Public liveness·추적 Header·CORS 검증."""

import uuid

def test_provisional_health_returns_empty_200_with_trace_header(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.content == b""
    uuid.UUID(response["X-Correlation-ID"])


def test_health_does_not_allow_unapproved_cross_origin(client):
    response = client.get(
        "/health",
        headers={"Origin": "https://unapproved.example"},
    )

    assert "Access-Control-Allow-Origin" not in response


def test_health_allows_configured_cross_origin(client):
    response = client.get(
        "/health",
        headers={"Origin": "https://approved.example"},
    )

    assert (
        response["Access-Control-Allow-Origin"]
        == "https://approved.example"
    )
    assert (
        response["Access-Control-Expose-Headers"]
        == "X-Correlation-ID"
    )
    assert "Origin" in response["Vary"]


def test_health_allows_configured_preflight(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "https://approved.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": (
                "Authorization, X-Correlation-ID"
            ),
        },
    )

    assert response.status_code == 204
    assert response["Access-Control-Allow-Origin"] == (
        "https://approved.example"
    )
    assert "X-Correlation-ID" in response["Access-Control-Allow-Headers"]
    assert response["Access-Control-Expose-Headers"] == "X-Correlation-ID"
    uuid.UUID(response["X-Correlation-ID"])


def test_health_rejects_unapproved_post_method(client):
    response = client.post("/health")

    assert response.status_code == 405
