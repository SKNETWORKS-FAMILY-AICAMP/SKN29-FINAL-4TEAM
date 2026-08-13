"""사람이 직접 확인할 수 있는 OpenAPI·Swagger 문서 진입점 검증."""


def test_public_openapi_schema_contains_executable_health(client):
    response = client.get("/api/schema/", HTTP_ACCEPT="application/json")

    assert response.status_code == 200
    schema = response.json()
    operation = schema["paths"]["/health"]["get"]
    bearer = schema["components"]["securitySchemes"]["BearerAuth"]
    assert operation["operationId"] == "getHealth"
    assert operation["tags"] == ["Health"]
    assert operation.get("security", []) == []
    assert "200" in operation["responses"]
    assert bearer["type"] == "http"
    assert bearer["scheme"] == "bearer"
    assert bearer["bearerFormat"] == "JWT"


def test_swagger_demo_login_has_consultant_request_example(client):
    response = client.get("/api/schema/", HTTP_ACCEPT="application/json")

    assert response.status_code == 200
    operation = response.json()["paths"]["/api/v1/auth/demo-login"]["post"]
    media_type = operation["requestBody"]["content"]["application/json"]
    examples = media_type["examples"]
    assert operation.get("security", []) == []
    assert any(
        example["value"] == {"demo_user_code": "DEMO-CONSULTANT-001"}
        for example in examples.values()
    )


def test_public_swagger_ui_points_to_runtime_schema(client):
    response = client.get("/api/docs/")

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "swagger-ui" in content
    assert "/api/schema/" in content
