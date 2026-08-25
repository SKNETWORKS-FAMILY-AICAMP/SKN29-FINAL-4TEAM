"""Prepare and verify the disposable Neo4j target used by the lineage QA job."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from typing import Any
from urllib.parse import urlparse

import httpx


RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
TARGET_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
SHA256_PATTERN = re.compile(r"[A-Fa-f0-9]{64}")
IMAGE_DIGEST_PATTERN = re.compile(r"sha256:[A-Fa-f0-9]{64}")


class PreparationError(RuntimeError):
    """The disposable target did not satisfy the write-safety preconditions."""


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise PreparationError(f"Required Neo4j QA setting is missing: {name}")
    return value


def _validated_endpoint(value: str) -> str:
    normalized = value.rstrip("/")
    parsed = urlparse(normalized)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise PreparationError("Neo4j QA endpoint must be an HTTP loopback root.")
    return normalized


def _query(
    client: httpx.Client,
    endpoint: str,
    statement: str,
    parameters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    response = client.post(
        f"{endpoint}/db/neo4j/query/v2",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json={"statement": statement, "parameters": parameters or {}},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("errors"):
        raise PreparationError("Neo4j QA marker query failed closed.")
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    fields = data.get("fields", [])
    values = data.get("values", [])
    if not isinstance(fields, list) or not isinstance(values, list):
        raise PreparationError("Neo4j QA marker response is malformed.")
    return [dict(zip((str(field) for field in fields), row)) for row in values]


def _wait_until_ready(client: httpx.Client, endpoint: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            rows = _query(client, endpoint, "RETURN 1 AS ready")
            if rows == [{"ready": 1}]:
                return
        except (httpx.HTTPError, ValueError, PreparationError):
            pass
        time.sleep(1)
    raise PreparationError("Neo4j QA container did not become ready in time.")


def prepare(timeout_seconds: int) -> dict[str, Any]:
    endpoint = _validated_endpoint(_required_environment("NEO4J_QA_ENDPOINT"))
    username = _required_environment("NEO4J_QA_USERNAME")
    password = _required_environment("NEO4J_QA_PASSWORD")
    run_id = _required_environment("NEO4J_QA_RUN_ID")
    target_id = _required_environment("NEO4J_QA_TARGET_ID")
    nonce_sha256 = _required_environment("NEO4J_QA_TARGET_NONCE_SHA256")
    image_digest = _required_environment("NEO4J_QA_IMAGE_DIGEST")
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise PreparationError("Neo4j QA run ID is invalid.")
    if TARGET_ID_PATTERN.fullmatch(target_id) is None:
        raise PreparationError("Neo4j QA target ID is invalid.")
    if SHA256_PATTERN.fullmatch(nonce_sha256) is None:
        raise PreparationError("Neo4j QA nonce digest is invalid.")
    if IMAGE_DIGEST_PATTERN.fullmatch(image_digest) is None:
        raise PreparationError("Neo4j QA image digest is invalid.")

    with httpx.Client(
        auth=httpx.BasicAuth(username, password),
        timeout=10.0,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        _wait_until_ready(client, endpoint, timeout_seconds)
        counts = _query(
            client,
            endpoint,
            "MATCH (n) WITH count(n) AS nodes "
            "OPTIONAL MATCH ()-[r]->() RETURN nodes, count(r) AS relationships",
        )
        if counts != [{"nodes": 0, "relationships": 0}]:
            raise PreparationError("Neo4j QA target is not empty before marker creation.")
        marker = {
            "target_id": target_id,
            "run_id": run_id,
            "nonce_sha256": nonce_sha256.casefold(),
            "database": "neo4j",
            "image_digest": image_digest.casefold(),
        }
        created = _query(
            client,
            endpoint,
            "CREATE (marker:WaterbridgeQaTarget) SET marker = $marker "
            "RETURN count(marker) AS created",
            {"marker": marker},
        )
        if created != [{"created": 1}]:
            raise PreparationError("Neo4j QA target marker was not created exactly once.")

    return {
        "status": "PASS",
        "profile": "qa_ephemeral_loopback",
        "database": "neo4j",
        "marker_count": 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-seconds", type=int, default=90)
    args = parser.parse_args()
    try:
        result = prepare(args.timeout_seconds)
    except (PreparationError, httpx.HTTPError, ValueError):
        print(json.dumps({"status": "FAIL", "message": "Neo4j QA target preparation failed."}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
