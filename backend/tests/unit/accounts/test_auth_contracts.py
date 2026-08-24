"""T-017 코드·OpenAPI·오류 계약과 Django 구현의 정합성 검증."""

from pathlib import Path

import yaml

from apps.accounts.models import User


BACKEND_DIR = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = BACKEND_DIR.parent


def load_yaml(relative_path: str):
    return yaml.safe_load(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
    )


def test_role_contract_matches_user_text_choices():
    role_contract = load_yaml("contracts/codes/user-roles.yaml")

    assert set(role_contract["codes"]) == set(User.Role.values)
    assert role_contract["status"] == "OWNER_BASELINE"


def test_auth_path_contract_contains_four_implemented_operations():
    auth_paths = load_yaml("contracts/api/paths/auth.yaml")

    assert set(auth_paths) == {
        "/auth/demo-login",
        "/auth/refresh",
        "/auth/logout",
        "/me",
    }
    assert {
        path: set(path_item)
        for path, path_item in auth_paths.items()
    } == {
        "/auth/demo-login": {"post"},
        "/auth/refresh": {"post"},
        "/auth/logout": {"post"},
        "/me": {"get"},
    }
    assert all(
        operation["responses"]
        for path_item in auth_paths.values()
        for operation in path_item.values()
    )
    assert all(
        operation["x-contract-status"]
        == "CONFIRMED"
        for path_item in auth_paths.values()
        for operation in path_item.values()
    )
    assert all(
        operation["responses"]["200"]["headers"][
            "X-Correlation-ID"
        ] == {"$ref": "../components/headers/CorrelationId.yaml"}
        for path_item in auth_paths.values()
        for operation in path_item.values()
    )
    assert auth_paths["/auth/demo-login"]["post"]["responses"][
        "403"
    ] == {"$ref": "../components/responses/Forbidden.yaml"}
    assert {
        path: set(path_item["post"]["responses"])
        for path, path_item in auth_paths.items()
        if "post" in path_item
    } == {
        "/auth/demo-login": {"200", "400", "401", "403", "422"},
        "/auth/refresh": {"200", "400", "401", "422"},
        "/auth/logout": {"200", "400", "401", "422"},
    }
    assert auth_paths["/me"]["get"]["responses"].keys() == {
        "200",
        "401",
    }


def test_openapi_registers_auth_paths_and_bearer_scheme():
    openapi = load_yaml("contracts/api/openapi.yaml")

    assert openapi["info"]["version"] == "0.9.0"
    for path in (
        "/auth/demo-login",
        "/auth/refresh",
        "/auth/logout",
        "/me",
    ):
        assert path in openapi["paths"]
    bearer = openapi["components"]["securitySchemes"]["BearerAuth"]
    assert bearer == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }


def test_auth_session_contract_uses_confirmed_token_lifetimes():
    response = load_yaml(
        "contracts/api/components/schemas/auth/LoginResponse.yaml"
    )

    assert response["properties"]["access_expires_in"]["const"] == 60 * 60
    refresh_expires_in = response["properties"]["refresh_expires_in"]
    assert "const" not in refresh_expires_in
    assert refresh_expires_in["minimum"] == 1
    assert refresh_expires_in["maximum"] == 7 * 24 * 60 * 60


def test_authenticated_user_contract_exposes_public_uuid_only():
    response = load_yaml(
        "contracts/api/components/schemas/auth/AuthenticatedUser.yaml"
    )

    assert response["properties"]["id"] == {
        "type": "string",
        "format": "uuid",
    }
    assert response["properties"]["customer_profile"]["properties"][
        "id"
    ] == {
        "type": "string",
        "format": "uuid",
    }


def test_auth_request_contracts_match_runtime_serializers():
    login = load_yaml(
        "contracts/api/components/schemas/auth/LoginRequest.yaml"
    )
    refresh = load_yaml(
        "contracts/api/components/schemas/auth/TokenRefreshRequest.yaml"
    )
    logout = load_yaml(
        "contracts/api/components/schemas/auth/LogoutRequest.yaml"
    )

    assert login["required"] == ["demo_user_code"]
    assert set(login["properties"]) == {"demo_user_code"}
    for token_request in (refresh, logout):
        assert token_request["required"] == ["refresh_token"]
        assert set(token_request["properties"]) == {"refresh_token"}


def test_auth_schemas_and_error_contracts_are_nonempty():
    schema_dir = (
        REPOSITORY_ROOT
        / "contracts"
        / "api"
        / "components"
        / "schemas"
        / "auth"
    )
    schemas = [
        yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in schema_dir.glob("*.yaml")
    ]
    assert len(schemas) >= 6
    assert all(schema.get("properties") for schema in schemas)

    auth_errors = load_yaml(
        "contracts/error-codes/categories/auth.yaml"
    )
    permission_errors = load_yaml(
        "contracts/error-codes/categories/permission.yaml"
    )
    assert {item["code"] for item in auth_errors["errors"]} == {
        "AUTH_REQUIRED",
        "AUTH_VERIFICATION_FAILED",
        "AUTH_LOGIN_FAILED",
        "AUTH_IDENTIFIER_UNAVAILABLE",
        "AUTH_SIGNUP_CONFLICT",
        "AUTH_RATE_LIMITED",
    }
    assert {
        item["code"] for item in permission_errors["errors"]
    } == {"FORBIDDEN"}
