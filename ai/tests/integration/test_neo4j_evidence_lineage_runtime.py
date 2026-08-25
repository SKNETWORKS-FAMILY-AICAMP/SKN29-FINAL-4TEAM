"""인증된 전용 Neo4j Container에서 동일 건수 오류 관계를 검출한다."""

from __future__ import annotations

import os

import pytest

from ai.app.experiments.neo4j_evidence_lineage import (
    QA_EPHEMERAL_LOOPBACK_PROFILE,
    QA_NODE_LABEL,
    EvidenceLineageGraph,
    GraphEdge,
    Neo4jHttpQueryClient,
    Neo4jQaTargetIdentity,
    build_evidence_lineage_graph,
    cleanup_graph_run,
    load_graph_into_neo4j,
    verify_graph_in_neo4j,
)


REQUIRED_ENVIRONMENT = (
    "AI_NEO4J_LINEAGE_E2E",
    "NEO4J_QA_ENDPOINT",
    "NEO4J_QA_USERNAME",
    "NEO4J_QA_PASSWORD",
    "NEO4J_QA_RUN_ID",
    "NEO4J_QA_TARGET_ID",
    "NEO4J_QA_TARGET_NONCE_SHA256",
    "NEO4J_QA_IMAGE_DIGEST",
)
E2E_READY = os.environ.get("AI_NEO4J_LINEAGE_E2E") == "1" and all(
    os.environ.get(name) for name in REQUIRED_ENVIRONMENT[1:]
)
pytestmark = pytest.mark.skipif(
    not E2E_READY,
    reason="인증된 전용 Neo4j QA Container 입력이 없어 NOT_RUN",
)


def _alternative_target(
    graph: EvidenceLineageGraph,
    edge: GraphEdge,
) -> str:
    used_targets = {
        item.target_id
        for item in graph.edges
        if item.relationship == edge.relationship
        and item.source_label == edge.source_label
        and item.source_id == edge.source_id
    }
    return next(
        node.node_id
        for node in graph.nodes
        if node.label == edge.target_label and node.node_id not in used_targets
    )


@pytest.mark.parametrize("relationship", ["HAS_PARENT_PAGE", "ABOUT", "COVERS_TOPIC"])
def test_actual_neo4j_rejects_same_count_wrong_relationship(
    relationship: str,
) -> None:
    run_id = os.environ["NEO4J_QA_RUN_ID"]
    graph = build_evidence_lineage_graph()
    target_identity = Neo4jQaTargetIdentity(
        target_id=os.environ["NEO4J_QA_TARGET_ID"],
        run_id=run_id,
        nonce_sha256=os.environ["NEO4J_QA_TARGET_NONCE_SHA256"],
        database="neo4j",
        image_digest=os.environ["NEO4J_QA_IMAGE_DIGEST"],
    )
    client = Neo4jHttpQueryClient(
        os.environ["NEO4J_QA_ENDPOINT"],
        profile=QA_EPHEMERAL_LOOPBACK_PROFILE,
        username=os.environ["NEO4J_QA_USERNAME"],
        password=os.environ["NEO4J_QA_PASSWORD"],
    )
    verification = None
    try:
        verification = load_graph_into_neo4j(
            graph,
            client,
            profile=QA_EPHEMERAL_LOOPBACK_PROFILE,
            run_id=run_id,
            target_identity=target_identity,
        )
        baseline = verify_graph_in_neo4j(graph, client, run_id=run_id)
        assert baseline["database_validation"] == "PASS"

        edge = next(item for item in graph.edges if item.relationship == relationship)
        alternative_target = _alternative_target(graph, edge)
        before = client.query(
            f"MATCH (:{QA_NODE_LABEL} {{qa_run_id: $run_id}})-[rel]->"
            f"(:{QA_NODE_LABEL} {{qa_run_id: $run_id}}) "
            "WHERE rel.qa_run_id = $run_id RETURN count(rel) AS count",
            {"run_id": run_id},
        )[0]["count"]
        mutated = client.query(
            f"MATCH (source:{QA_NODE_LABEL}:{edge.source_label} "
            "{qa_run_id: $run_id, id: $source_id})"
            f"-[old:{relationship} {{qa_run_id: $run_id}}]->"
            f"(:{QA_NODE_LABEL}:{edge.target_label} "
            "{qa_run_id: $run_id, id: $target_id}) "
            "DELETE old WITH source "
            f"MATCH (wrong:{QA_NODE_LABEL}:{edge.target_label} "
            "{qa_run_id: $run_id, id: $wrong_target_id}) "
            f"CREATE (source)-[replacement:{relationship}]->(wrong) "
            "SET replacement = $properties, replacement.qa_run_id = $run_id "
            "RETURN count(replacement) AS mutated",
            {
                "run_id": run_id,
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "wrong_target_id": alternative_target,
                "properties": dict(edge.properties),
            },
        )[0]["mutated"]
        after = client.query(
            f"MATCH (:{QA_NODE_LABEL} {{qa_run_id: $run_id}})-[rel]->"
            f"(:{QA_NODE_LABEL} {{qa_run_id: $run_id}}) "
            "WHERE rel.qa_run_id = $run_id RETURN count(rel) AS count",
            {"run_id": run_id},
        )[0]["count"]

        corrupted = verify_graph_in_neo4j(graph, client, run_id=run_id)

        assert mutated == 1
        assert before == after == len(graph.edges)
        assert corrupted["database_validation"] == "FAIL"
        assert "RELATIONSHIP_IDENTITY_SET_MISMATCH" in corrupted["issues"]
        assert "GRAPH_SNAPSHOT_SHA256_MISMATCH" in corrupted["issues"]
    finally:
        try:
            if verification is not None:
                cleanup = cleanup_graph_run(
                    client,
                    verification=verification,
                    target_identity=target_identity,
                )
                assert cleanup["status"] == "PASS"
        finally:
            client.close()
