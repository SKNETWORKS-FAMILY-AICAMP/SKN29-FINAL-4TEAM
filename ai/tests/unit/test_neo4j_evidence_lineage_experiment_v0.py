"""Neo4j Evidence Lineage LAB의 격리·정합성·비노출 계약 테스트."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import httpx
import pytest

from ai.app.experiments.neo4j_evidence_lineage import (
    DEFAULT_CHILD_CHUNKS_PATH,
    EvidenceLineageGraph,
    Neo4jEvidenceLineageError,
    Neo4jHttpQueryClient,
    build_evidence_lineage_graph,
    load_graph_into_neo4j,
    render_lineage_svg,
    verify_graph_in_neo4j,
)


class FakeNeo4jExecutor:
    def __init__(self, graph: EvidenceLineageGraph) -> None:
        self.graph = graph
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

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
        if "labels(n)[0]" in statement:
            return [
                {"label": label, "count": count}
                for label, count in sorted(self.graph.node_counts().items())
            ]
        if "type(r) AS relationship" in statement:
            return [
                {"relationship": relationship, "count": count}
                for relationship, count in sorted(
                    self.graph.relationship_counts().items()
                )
            ]
        if "orphan_chunk_count" in statement:
            return [{"orphan_chunk_count": 0}]
        if "cross_model_path_count" in statement:
            return [{"cross_model_path_count": 0}]
        if "r:COVERS_TOPIC" in statement and "topic_code" in statement:
            return [
                {
                    "model_code": edge.source_id,
                    "topic_code": edge.target_id,
                    "evidence_group_count": edge.properties[
                        "evidence_group_count"
                    ],
                }
                for edge in self.graph.edges
                if edge.relationship == "COVERS_TOPIC"
            ]
        if "$rows" in statement:
            return [{"loaded": len(values.get("rows", []))}]
        return []


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
    assert projection["scope"] == "LAB_ONLY"
    assert projection["production_runtime_connected"] is False
    assert projection["public_runtime_activation"] == "HOLD"
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

    with pytest.raises(
        Neo4jEvidenceLineageError,
        match="제품 또는 문서 관계",
    ):
        build_evidence_lineage_graph(child_chunks_path=corrupted_path)


def test_neo4j_loader_and_verifier_keep_lab_boundary():
    graph = build_evidence_lineage_graph()
    executor = FakeNeo4jExecutor(graph)

    load_graph_into_neo4j(graph, executor)
    report = verify_graph_in_neo4j(graph, executor)
    svg = render_lineage_svg(report)

    assert report["database_validation"] == "PASS"
    assert report["neo4j"] == {
        "name": "Neo4j Kernel",
        "version": "2026.07.1",
        "edition": "community",
        "endpoint_class": "LOOPBACK_QUERY_API_V2_AUTH_DISABLED",
    }
    assert report["orphan_chunk_count"] == 0
    assert report["cross_model_path_count"] == 0
    assert report["visual_summary"]["row_count"] == 43
    assert "Neo4j Evidence Lineage Lab" in svg
    assert "LAB_ONLY" in svg
    assert "CHILD-" not in svg
    assert "PARENT-" not in svg
    assert "EVD-" not in svg
    assert "parent_text" not in svg
    assert any("CREATE CONSTRAINT" in statement for statement, _ in executor.calls)
    assert all("$rows" in statement for statement, _ in executor.calls if "UNWIND" in statement)


def test_http_query_client_accepts_only_loopback_and_parameterizes_request():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            202,
            json={"data": {"fields": ["value"], "values": [[1]]}},
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = Neo4jHttpQueryClient(
        "http://127.0.0.1:7474",
        http_client=http_client,
    )

    rows = client.query("RETURN $value AS value", {"value": 1})

    assert rows == [{"value": 1}]
    assert captured["path"] == "/db/neo4j/query/v2"
    assert captured["payload"]["statement"] == "RETURN $value AS value"
    assert captured["payload"]["parameters"] == {"value": 1}
    with pytest.raises(Neo4jEvidenceLineageError, match="Loopback"):
        Neo4jHttpQueryClient("https://neo4j.example.com")
