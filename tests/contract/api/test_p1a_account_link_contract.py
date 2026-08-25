"""P1-A G2 frozen contract policy tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "contracts" / "api"
P1_PATHS = API_ROOT / "paths" / "p1-auth.yaml"
AUTH_SCHEMA_ROOT = API_ROOT / "components" / "schemas" / "auth"
P1A_OPERATION_PATHS = (
    "/auth/contract-verification/challenges",
    "/auth/contract-verification/challenges/{challenge_id}/verify",
    "/auth/signup",
    "/auth/login",
    "/auth/account-recovery/username/challenges",
    "/auth/account-recovery/username/challenges/{challenge_id}/verify",
    "/auth/password-reset/challenges",
    "/auth/password-reset/challenges/{challenge_id}/verify",
    "/auth/password-reset/confirm",
)


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys in the reviewed P1-A contract files."""


def _construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _yaml(path: Path) -> dict:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)


def test_p1_auth_schemas_are_valid_draft_2020_12() -> None:
    for path in sorted(AUTH_SCHEMA_ROOT.glob("P1*.yaml")):
        Draft202012Validator.check_schema(_yaml(path))


def test_p1a_operations_keep_frozen_contract_and_explicit_runtime_status() -> None:
    contract = _yaml(P1_PATHS)

    assert contract["x-p1a-policy"]["contract_status"] == "CONFIRMED"
    for path in P1A_OPERATION_PATHS:
        operation = contract[path]["post"]
        assert operation["x-contract-status"] == "CONFIRMED"
        assert operation["x-runtime-status"] == (
            "IMPLEMENTED"
            if path == "/auth/login"
            else "NOT_IMPLEMENTED"
        )


def test_challenge_creation_conceals_candidate_existence() -> None:
    contract = _yaml(P1_PATHS)
    challenge_paths = (
        "/auth/contract-verification/challenges",
        "/auth/account-recovery/username/challenges",
        "/auth/password-reset/challenges",
    )

    for path in challenge_paths:
        operation = contract[path]["post"]
        assert "202" in operation["responses"]
        assert "404" not in operation["responses"]

    response_schema = _yaml(AUTH_SCHEMA_ROOT / "P1ChallengeAccepted.yaml")
    properties = response_schema["properties"]
    assert properties["expires_in"]["const"] == 300
    assert properties["resend_after"]["const"] == 60
    field_names = " ".join(properties).lower()
    assert "email" not in field_names
    assert "masked" not in field_names


def test_all_otp_verify_paths_use_challenge_id_rule() -> None:
    contract = _yaml(P1_PATHS)
    expected_paths = (
        "/auth/contract-verification/challenges/{challenge_id}/verify",
        "/auth/account-recovery/username/challenges/{challenge_id}/verify",
        "/auth/password-reset/challenges/{challenge_id}/verify",
    )

    for path in expected_paths:
        assert path in contract
        parameters = contract[path]["parameters"]
        assert parameters[0]["name"] == "challenge_id"
        assert parameters[0]["in"] == "path"
        assert parameters[0]["required"] is True

    assert "/auth/account-recovery/username/verify" not in contract
    assert "/auth/password-reset/verify" not in contract


def test_signup_password_and_required_consents_are_machine_validated() -> None:
    schema = _yaml(AUTH_SCHEMA_ROOT / "P1SignupRequest.yaml")
    validator = Draft202012Validator(schema)
    valid = {
        "claim_ticket": "x" * 32,
        "username": "waterbridge.user",
        "password": "waterbridge2026",
        "consents": [
            {"code": "TERMS_OF_SERVICE", "version": "v1", "agreed": True},
            {
                "code": "PRIVACY_COLLECTION_USE",
                "version": "v1",
                "agreed": True,
            },
        ],
    }
    validator.validate(valid)

    for invalid_password in ("onlylettersxx", "123456789012", "Abc123"):
        with pytest.raises(ValidationError):
            validator.validate({**valid, "password": invalid_password})

    missing_privacy = {
        **valid,
        "consents": [
            {"code": "TERMS_OF_SERVICE", "version": "v1", "agreed": True},
            {"code": "MARKETING", "version": "v1", "agreed": False},
        ],
    }
    with pytest.raises(ValidationError):
        validator.validate(missing_privacy)


def test_ticket_fields_are_request_body_secrets_and_login_reuses_contract() -> None:
    signup = _yaml(AUTH_SCHEMA_ROOT / "P1SignupRequest.yaml")
    reset = _yaml(AUTH_SCHEMA_ROOT / "P1PasswordResetConfirmRequest.yaml")
    assert signup["properties"]["claim_ticket"]["writeOnly"] is True
    assert reset["properties"]["reset_ticket"]["writeOnly"] is True

    contract = _yaml(P1_PATHS)
    login_ref = (
        contract["/auth/login"]["post"]["responses"]["200"]["content"]
        ["application/json"]["schema"]["allOf"][1]["properties"]["data"]
        ["$ref"]
    )
    signup_ref = (
        contract["/auth/signup"]["post"]["responses"]["201"]["content"]
        ["application/json"]["schema"]["allOf"][1]["properties"]["data"]
        ["$ref"]
    )
    expected = "../components/schemas/auth/LoginResponse.yaml"
    assert login_ref == expected
    assert signup_ref == expected


def test_public_auth_failures_use_non_enumerating_responses() -> None:
    contract = _yaml(P1_PATHS)
    expected = {
        "/auth/contract-verification/challenges/{challenge_id}/verify": (
            "../components/responses/P1VerificationFailed.yaml"
        ),
        "/auth/signup": "../components/responses/P1VerificationFailed.yaml",
        "/auth/login": "../components/responses/P1LoginFailed.yaml",
        "/auth/account-recovery/username/challenges/{challenge_id}/verify": (
            "../components/responses/P1VerificationFailed.yaml"
        ),
        "/auth/password-reset/challenges/{challenge_id}/verify": (
            "../components/responses/P1VerificationFailed.yaml"
        ),
        "/auth/password-reset/confirm": (
            "../components/responses/P1VerificationFailed.yaml"
        ),
    }
    for path, response_ref in expected.items():
        assert contract[path]["post"]["responses"]["401"]["$ref"] == response_ref


def test_rate_limit_response_exposes_safe_retry_delay() -> None:
    response = _yaml(API_ROOT / "components" / "responses" / "TooManyRequests.yaml")
    assert response["headers"]["Retry-After"]["schema"]["minimum"] == 1
    content = response["content"]["application/json"]
    assert "retry_after_seconds" in content["description"]
