"""Neo4j JSONL Lineage QA의 격리·정합성·비노출 계약 테스트."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any, Mapping

import httpx
import pytest

from ai.app.experiments.neo4j_evidence_lineage import (
    DEFAULT_CHILD_CHUNKS_PATH,
    LAB_LOOPBACK_PROFILE,
    QA_EPHEMERAL_LOOPBACK_PROFILE,
    QA_NODE_LABEL,
    QA_TARGET_LABEL,
    EvidenceLineageGraph,
    Neo4jEvidenceLineageError,
    Neo4jHttpQueryClient,
    Neo4jQaTargetIdentity,
    build_evidence_lineage_graph,
    build_visual_query_presets,
    canonical_json_sha256,
    cleanup_graph_run,
    load_graph_into_neo4j,
    render_lineage_svg,
    render_visual_query_bundle,
    verify_graph_in_neo4j,
)


RUN_ID = "unit-lineage-001"
IMAGE_DIGEST = "sha256:" + "a" * 64


class FakeNeo4jExecutor:
    def __init__(
        self,
        expected_graph: EvidenceLineageGraph,
        *,
        database_graph: EvidenceLineageGraph | None = None,
        profile: str = LAB_LOOPBACK_PROFILE,
        target_identity: Neo4jQaTargetIdentity | None = None,
        unexpected_node_count: int = 0,
        relationship_count_before_load: int = 0,
        marker_after_cleanup_status: str = "UNCHANGED",
        visual_row_count_overrides: Mapping[str, int] | None = None,
    ) -> None:
        self.expected_graph = expected_graph
        self.database_graph = database_graph or expected_graph
        self.profile = profile
        self.database = "neo4j"
        self.endpoint_class = "TEST_EXECUTOR"
        self.target_identity = target_identity
        self.unexpected_node_count = unexpected_node_count
        self.relationship_count_before_load = relationship_count_before_load
        self.marker_after_cleanup_status = marker_after_cleanup_status
        self.visual_row_count_overrides = visual_row_count_overrides or {}
        self.calls: list[tuple[str, Mapping[str, Any]]] = []
        self.cleaned = False

    def query(
        self,
        statement: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        values = parameters or {}
        self.calls.append((statement, values))
        if "dbms.components" in statement:
            return [
                {
                    "name": "Neo4j Kernel",
                    "version": "2026.07.1",
                    "edition": "community",
                },
                {"name": "Cypher", "version": "5", "edition": ""},
            ]
        if f"MATCH (marker:{QA_TARGET_LABEL})" in statement:
            if self.target_identity is None:
                return []
            marker = {
                "labels": [QA_TARGET_LABEL],
                **self.target_identity.expected_marker(),
            }
            if self.cleaned and self.marker_after_cleanup_status == "MISSING":
                return []
            if self.cleaned and self.marker_after_cleanup_status == "DUPLICATE":
                return [marker, dict(marker)]
            if self.cleaned and self.marker_after_cleanup_status == "MUTATED":
                marker["image_digest"] = "sha256:" + "f" * 64
            return [marker]
        if "RETURN count(n) AS unexpected_node_count" in statement:
            return [{"unexpected_node_count": self.unexpected_node_count}]
        if "RETURN count(rel) AS relationship_count" in statement:
            return [{"relationship_count": self.relationship_count_before_load}]
        if "RETURN labels(n) AS labels" in statement:
            if self.cleaned:
                return []
            return [
                {
                    "labels": [QA_NODE_LABEL, node.label],
                    "kind": node.label,
                    "id": node.node_id,
                    "properties": {
                        **node.as_row(),
                        "qa_run_id": RUN_ID,
                        "qa_kind": node.label,
                        "qa_key": f"{RUN_ID}:{node.label}:{node.node_id}",
                    },
                }
                for node in self.database_graph.nodes
            ]
        if "source.qa_kind AS source_kind" in statement:
            if self.cleaned:
                return []
            return [
                {
                    "source_kind": edge.source_label,
                    "source_id": edge.source_id,
                    "relationship": edge.relationship,
                    "target_kind": edge.target_label,
                    "target_id": edge.target_id,
                    "properties": {
                        **dict(edge.properties),
                        "qa_run_id": RUN_ID,
                    },
                }
                for edge in self.database_graph.edges
            ]
        if "cross_namespace_relationship_count" in statement:
            return [{"cross_namespace_relationship_count": 0}]
        if "orphan_chunk_count" in statement:
            return [{"orphan_chunk_count": 0}]
        if "cross_model_path_count" in statement:
            return [{"cross_model_path_count": 0}]
        if (
            "rel:COVERS_TOPIC" in statement
            and "model_code AS model_code" in statement
        ):
            return [
                {
                    "model_code": edge.source_id,
                    "topic_code": edge.target_id,
                    "evidence_group_count": edge.properties[
                        "evidence_group_count"
                    ],
                }
                for edge in self.database_graph.edges
                if edge.relationship == "COVERS_TOPIC"
            ]
        for preset in build_visual_query_presets(self.expected_graph):
            if statement == preset.statement:
                row_count = self.visual_row_count_overrides.get(
                    preset.query_id,
                    int(preset.expected_result["row_count"]),
                )
                return [{"visual_row": index} for index in range(row_count)]
        if "$rows" in statement and " AS loaded" in statement:
            return [{"loaded": len(values.get("rows", []))}]
        if "DETACH DELETE node" in statement:
            self.cleaned = True
            return [{"deleted_node_count": len(self.database_graph.nodes)}]
        if "residual_node_count" in statement:
            return [{"residual_node_count": 0 if self.cleaned else 1}]
        if "residual_relationship_count" in statement:
            return [{"residual_relationship_count": 0 if self.cleaned else 1}]
        if "unexpected_relationship_count" in statement:
            return [{"unexpected_relationship_count": 0}]
        raise AssertionError(f"Unhandled test query: {statement}")


def _target_identity() -> Neo4jQaTargetIdentity:
    return Neo4jQaTargetIdentity(
        target_id="container-unit-001",
        run_id=RUN_ID,
        nonce_sha256="b" * 64,
        database="neo4j",
        image_digest=IMAGE_DIGEST,
    )


def _corrupt_relationship(
    graph: EvidenceLineageGraph,
    relationship: str,
) -> EvidenceLineageGraph:
    edge = next(item for item in graph.edges if item.relationship == relationship)
    used_targets = {
        item.target_id
        for item in graph.edges
        if item.relationship == relationship and item.source_id == edge.source_id
    }
    alternative = next(
        node
        for node in graph.nodes
        if node.label == edge.target_label and node.node_id not in used_targets
    )
    corrupted = replace(edge, target_id=alternative.node_id)
    return replace(
        graph,
        edges=tuple(corrupted if item is edge else item for item in graph.edges),
    )


def test_projection_uses_fixed_relationships_without_source_text():
    graph = build_evidence_lineage_graph()

    assert graph.node_counts() == {
        "Product": 3,
        "Document": 3,
        "ParentPage": 15,
        "EvidenceChunk": 53,
        "EvidenceGroup": 43,
        "Topic": 25,
    }
    assert graph.relationship_counts() == {
        "HAS_DOCUMENT": 3,
        "HAS_PARENT_PAGE": 15,
        "HAS_CHILD": 53,
        "MEMBER_OF": 53,
        "ABOUT": 43,
        "COVERS_TOPIC": 43,
    }
    projection = graph.projection_payload()
    serialized = json.dumps(projection, ensure_ascii=False)
    assert projection["scope"] == "JSONL_BASED_LINEAGE_QA"
    assert projection["rds_connected"] is False
    assert projection["production_runtime_connected"] is False
    assert len(graph.canonical_nodes()) == 142
    assert len(graph.canonical_relationships()) == 210
    for forbidden_name in (
        "child_text",
        "parent_text",
        "safe_actions",
        "consultation_conditions",
        "source_span",
        "embedding",
        "similarity_score",
        "prompt",
    ):
        assert forbidden_name not in serialized


def test_projection_fails_closed_on_cross_model_child_relation(tmp_path: Path):
    rows = [
        json.loads(line)
        for line in DEFAULT_CHILD_CHUNKS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows[0]["exact_sales_code"] = "WPUIAC606SNW"
    corrupted_path = tmp_path / "corrupted_children.jsonl"
    corrupted_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(Neo4jEvidenceLineageError, match="제품 또는 문서 관계"):
        build_evidence_lineage_graph(child_chunks_path=corrupted_path)


def test_loader_and_verifier_use_run_scope_and_exact_snapshot():
    graph = build_evidence_lineage_graph()
    executor = FakeNeo4jExecutor(graph)
    verification = load_graph_into_neo4j(
        graph,
        executor,
        profile=LAB_LOOPBACK_PROFILE,
        run_id=RUN_ID,
    )
    report = verify_graph_in_neo4j(graph, executor, run_id=RUN_ID)
    svg = render_lineage_svg(report)

    assert report["database_validation"] == "PASS"
    assert report["graph_identity_validation"]["snapshot"]["match"] is True
    assert report["graph_identity_validation"]["nodes"]["actual_count"] == 142
    assert report["graph_identity_validation"]["relationships"]["actual_count"] == 210
    assert report["visual_summary"]["match"] is True
    assert report["visual_query_validation"]["query_count"] == 6
    assert "Neo4j Evidence Lineage QA" in svg
    assert "CHILD-" not in svg
    assert "PARENT-" not in svg
    assert "EVD-" not in svg
    statements = [statement for statement, _ in executor.calls]
    forbidden_global_delete = "MATCH (n) " + "DETACH DELETE n"
    assert not any(forbidden_global_delete in statement for statement in statements)
    assert not any("CREATE CONSTRAINT" in statement for statement in statements)
    assert any("CREATE (n:WaterbridgeQaLineage" in statement for statement in statements)
    assert all("$rows" in statement for statement in statements if "UNWIND" in statement)


@pytest.mark.parametrize("relationship", ["HAS_PARENT_PAGE", "ABOUT", "COVERS_TOPIC"])
def test_same_count_wrong_relationship_fails_exact_identity(relationship: str):
    graph = build_evidence_lineage_graph()
    corrupted_graph = _corrupt_relationship(graph, relationship)
    executor = FakeNeo4jExecutor(graph, database_graph=corrupted_graph)

    report = verify_graph_in_neo4j(graph, executor, run_id=RUN_ID)

    assert corrupted_graph.relationship_counts() == graph.relationship_counts()
    assert report["database_validation"] == "FAIL"
    assert "RELATIONSHIP_IDENTITY_SET_MISMATCH" in report["issues"]
    assert "GRAPH_SNAPSHOT_SHA256_MISMATCH" in report["issues"]
    relationship_result = report["graph_identity_validation"]["relationships"]
    assert relationship_result["expected_identity_sha256"] != relationship_result[
        "actual_identity_sha256"
    ]


def test_same_identity_wrong_relationship_property_fails_snapshot_hash():
    graph = build_evidence_lineage_graph()
    target = next(edge for edge in graph.edges if edge.relationship == "COVERS_TOPIC")
    corrupted = replace(
        target,
        properties={
            "evidence_group_count": int(target.properties["evidence_group_count"]) + 1
        },
    )
    corrupted_graph = replace(
        graph,
        edges=tuple(corrupted if edge is target else edge for edge in graph.edges),
    )
    executor = FakeNeo4jExecutor(graph, database_graph=corrupted_graph)

    report = verify_graph_in_neo4j(graph, executor, run_id=RUN_ID)

    assert report["database_validation"] == "FAIL"
    assert "RELATIONSHIP_IDENTITY_SET_MISMATCH" not in report["issues"]
    assert "GRAPH_SNAPSHOT_SHA256_MISMATCH" in report["issues"]
    assert "VISUAL_SUMMARY_RESULT_SET_MISMATCH" in report["issues"]


def test_duplicate_identity_snapshot_hash_is_stable_across_database_row_order():
    graph = build_evidence_lineage_graph()
    original = graph.nodes[0]
    duplicate = replace(
        original,
        properties={**dict(original.properties), "display_label": "Duplicate"},
    )
    nodes = (*graph.nodes, duplicate)
    first_database_graph = replace(graph, nodes=nodes)
    second_database_graph = replace(graph, nodes=tuple(reversed(nodes)))

    first = verify_graph_in_neo4j(
        graph,
        FakeNeo4jExecutor(graph, database_graph=first_database_graph),
        run_id=RUN_ID,
    )
    second = verify_graph_in_neo4j(
        graph,
        FakeNeo4jExecutor(graph, database_graph=second_database_graph),
        run_id=RUN_ID,
    )

    assert "DUPLICATE_NODE_IDENTITY" in first["issues"]
    assert first["database_validation"] == second["database_validation"] == "FAIL"
    assert first["graph_identity_validation"]["snapshot"][
        "actual_sha256"
    ] == second["graph_identity_validation"]["snapshot"]["actual_sha256"]


def test_qa_preflight_requires_exact_infra_marker_before_mutation():
    graph = build_evidence_lineage_graph()
    target = _target_identity()
    executor = FakeNeo4jExecutor(
        graph,
        profile=QA_EPHEMERAL_LOOPBACK_PROFILE,
        target_identity=replace(target, nonce_sha256="c" * 64),
    )

    with pytest.raises(Neo4jEvidenceLineageError, match="표식"):
        load_graph_into_neo4j(
            graph,
            executor,
            profile=QA_EPHEMERAL_LOOPBACK_PROFILE,
            run_id=RUN_ID,
            target_identity=target,
        )

    assert not any("UNWIND" in statement for statement, _ in executor.calls)


def test_qa_preflight_and_cleanup_preserve_target_marker():
    graph = build_evidence_lineage_graph()
    target = _target_identity()
    executor = FakeNeo4jExecutor(
        graph,
        profile=QA_EPHEMERAL_LOOPBACK_PROFILE,
        target_identity=target,
    )
    verification = load_graph_into_neo4j(
        graph,
        executor,
        profile=QA_EPHEMERAL_LOOPBACK_PROFILE,
        run_id=RUN_ID,
        target_identity=target,
    )
    cleanup = cleanup_graph_run(
        executor,
        verification=verification,
        target_identity=target,
    )

    assert verification.marker_validated is True
    assert cleanup["status"] == "PASS"
    assert cleanup["target_marker_validation"] == "PASS"
    assert cleanup["container_cleanup"] == "NOT_RUN_INFRA_OWNED"
    delete_statements = [
        statement for statement, _ in executor.calls if "DETACH DELETE" in statement
    ]
    assert delete_statements == [
        f"MATCH (node:{QA_NODE_LABEL} {{qa_run_id: $run_id}}) "
        "DETACH DELETE node RETURN count(node) AS deleted_node_count"
    ]


@pytest.mark.parametrize(
    "marker_after_cleanup_status",
    ["MISSING", "DUPLICATE", "MUTATED"],
)
def test_qa_cleanup_fails_if_infra_target_marker_changes(
    marker_after_cleanup_status: str,
) -> None:
    graph = build_evidence_lineage_graph()
    target = _target_identity()
    executor = FakeNeo4jExecutor(
        graph,
        profile=QA_EPHEMERAL_LOOPBACK_PROFILE,
        target_identity=target,
        marker_after_cleanup_status=marker_after_cleanup_status,
    )
    verification = load_graph_into_neo4j(
        graph,
        executor,
        profile=QA_EPHEMERAL_LOOPBACK_PROFILE,
        run_id=RUN_ID,
        target_identity=target,
    )

    cleanup = cleanup_graph_run(
        executor,
        verification=verification,
        target_identity=target,
    )

    assert cleanup["status"] == "FAIL"
    assert cleanup["target_marker_validation"] == "FAIL"


def test_visual_query_presets_are_run_scoped():
    graph = build_evidence_lineage_graph()
    presets = build_visual_query_presets(graph)
    by_id = {preset.query_id: preset for preset in presets}
    bundle = render_visual_query_bundle(presets, run_id=RUN_ID)

    assert len(presets) == 6
    assert by_id["product_topic_overview"].expected_result["row_count"] == 43
    assert by_id["product_lineage_wpujac104dwh"].expected_result["path_count"] == 15
    assert by_id["product_lineage_wpuiac425snw"].expected_result["path_count"] == 19
    assert by_id["product_lineage_wpuiac606snw"].expected_result["path_count"] == 19
    assert by_id["integrity_anomalies"].expected_result == {"row_count": 0}
    assert ":param run_id" in bundle
    assert bundle.count("// [") == 6
    assert all("$run_id" in preset.statement for preset in presets)


def test_visual_query_validation_fails_closed_on_row_count_mismatch():
    graph = build_evidence_lineage_graph()
    executor = FakeNeo4jExecutor(
        graph,
        visual_row_count_overrides={"product_lineage_wpujac104dwh": 14},
    )

    report = verify_graph_in_neo4j(graph, executor, run_id=RUN_ID)

    assert report["database_validation"] == "FAIL"
    assert (
        "VISUAL_QUERY_ROW_COUNT_MISMATCH:product_lineage_wpujac104dwh"
        in report["issues"]
    )


def test_http_query_client_profiles_reject_network_and_require_qa_basic_auth():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["authorization"] = request.headers.get("Authorization")
        return httpx.Response(
            202,
            json={"data": {"fields": ["value"], "values": [[1]]}},
        )

    with pytest.raises(Neo4jEvidenceLineageError, match="Loopback"):
        Neo4jHttpQueryClient("https://neo4j.example.com")
    with pytest.raises(Neo4jEvidenceLineageError, match="Basic"):
        Neo4jHttpQueryClient(
            "http://127.0.0.1:7474",
            profile=QA_EPHEMERAL_LOOPBACK_PROFILE,
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = Neo4jHttpQueryClient(
        "http://127.0.0.1:7474",
        profile=QA_EPHEMERAL_LOOPBACK_PROFILE,
        username="neo4j",
        password="do-not-print-this-secret",
        http_client=http_client,
    )
    rows = client.query("RETURN $value AS value", {"value": 1})

    assert rows == [{"value": 1}]
    assert captured["path"] == "/db/neo4j/query/v2"
    assert str(captured["authorization"]).startswith("Basic ")
    assert "do-not-print-this-secret" not in repr(client)


def test_http_query_client_redacts_secret_on_auth_failure(
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "never-echo-this-password"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=f"unauthorized:{secret}")

    client = Neo4jHttpQueryClient(
        "http://127.0.0.1:7474",
        profile=QA_EPHEMERAL_LOOPBACK_PROFILE,
        username="neo4j",
        password=secret,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(Neo4jEvidenceLineageError) as captured:
        client.query("RETURN 1")

    assert secret not in str(captured.value)
    assert secret not in repr(captured.value)
    output = capsys.readouterr()
    assert secret not in output.out
    assert secret not in output.err
    assert secret not in caplog.text


def test_canonical_snapshot_hash_is_stable():
    graph = build_evidence_lineage_graph()

    first = canonical_json_sha256(graph.canonical_snapshot())
    second = canonical_json_sha256(graph.canonical_snapshot())

    assert first == second
    assert len(first) == 64
