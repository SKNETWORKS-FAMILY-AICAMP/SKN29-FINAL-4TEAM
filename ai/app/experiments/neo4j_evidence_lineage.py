"""Neo4j Evidence Lineage LAB 전용 읽기 전용 Graph Projection."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from html import escape
import json
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse

import httpx


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PARENT_PAGES_PATH = (
    REPOSITORY_ROOT
    / "data/processed/structured/rag/expansion/rag_parent_pages_3model_v1.jsonl"
)
DEFAULT_CHILD_CHUNKS_PATH = (
    REPOSITORY_ROOT
    / "data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl"
)
DEFAULT_EVIDENCE_GROUPS_PATH = (
    REPOSITORY_ROOT
    / "data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl"
)

EXPECTED_INPUT_COUNTS = {
    "parents": 15,
    "children": 53,
    "evidence_groups": 43,
}
NODE_LABELS = (
    "Product",
    "Document",
    "ParentPage",
    "EvidenceChunk",
    "EvidenceGroup",
    "Topic",
)
RELATIONSHIP_TYPES = (
    "HAS_DOCUMENT",
    "HAS_PARENT_PAGE",
    "HAS_CHILD",
    "MEMBER_OF",
    "ABOUT",
    "COVERS_TOPIC",
)
ALLOWED_NODE_PROPERTIES = {
    "Product": {"display_label", "model_code", "product_generation"},
    "Document": {"display_label", "model_code", "document_version"},
    "ParentPage": {
        "display_label",
        "model_code",
        "page_ref",
        "verification_status",
    },
    "EvidenceChunk": {
        "display_label",
        "model_code",
        "risk_level",
        "requires_consultation",
        "verification_status",
    },
    "EvidenceGroup": {
        "display_label",
        "model_code",
        "topic_code",
        "risk_level",
        "requires_consultation",
        "verification_status",
    },
    "Topic": {"display_label", "topic_code"},
}
FORBIDDEN_SOURCE_FIELDS = {
    "child_text",
    "parent_text",
    "safe_actions",
    "consultation_conditions",
    "row_labels",
    "source_span",
    "embedding",
    "similarity_score",
    "prompt",
}

JsonScalar = str | int | float | bool | None


class Neo4jEvidenceLineageError(RuntimeError):
    """독립 Graph LAB 입력·실행·정합성 실패."""


@dataclass(frozen=True, slots=True)
class GraphNode:
    label: str
    node_id: str
    properties: Mapping[str, JsonScalar]

    def as_row(self) -> dict[str, JsonScalar]:
        return {"id": self.node_id, **dict(self.properties)}


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source_label: str
    source_id: str
    relationship: str
    target_label: str
    target_id: str
    properties: Mapping[str, JsonScalar]

    def as_row(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "properties": dict(self.properties),
        }


@dataclass(frozen=True, slots=True)
class EvidenceLineageGraph:
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    input_files: Mapping[str, Mapping[str, JsonScalar]]

    def node_counts(self) -> dict[str, int]:
        counts = Counter(node.label for node in self.nodes)
        return {label: counts.get(label, 0) for label in NODE_LABELS}

    def relationship_counts(self) -> dict[str, int]:
        counts = Counter(edge.relationship for edge in self.edges)
        return {
            relationship: counts.get(relationship, 0)
            for relationship in RELATIONSHIP_TYPES
        }

    def projection_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "scope": "LAB_ONLY",
            "production_runtime_connected": False,
            "public_runtime_activation": "HOLD",
            "source_status": "DATA_READY_AI_REVERIFY_REQUIRED",
            "nodes": [
                {
                    "label": node.label,
                    **node.as_row(),
                }
                for node in self.nodes
            ],
            "edges": [
                {
                    "source_label": edge.source_label,
                    "source_id": edge.source_id,
                    "relationship": edge.relationship,
                    "target_label": edge.target_label,
                    "target_id": edge.target_id,
                    "properties": dict(edge.properties),
                }
                for edge in self.edges
            ],
        }


class Neo4jQueryExecutor(Protocol):
    def query(
        self,
        statement: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...


class Neo4jHttpQueryClient:
    """Loopback Neo4j Query API v2만 허용하는 LAB Client."""

    def __init__(
        self,
        endpoint: str,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        normalized = endpoint.rstrip("/")
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
            raise Neo4jEvidenceLineageError(
                "Neo4j LAB Query API는 인증을 끈 Loopback Endpoint만 허용합니다."
            )
        self.endpoint = normalized
        self._client = http_client or httpx.Client(timeout=10.0)
        self._owns_client = http_client is None

    def query(
        self,
        statement: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        compact_statement = " ".join(statement.split())
        try:
            response = self._client.post(
                f"{self.endpoint}/db/neo4j/query/v2",
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json={
                    "statement": compact_statement,
                    "parameters": dict(parameters or {}),
                    "maxExecutionTime": 10,
                    "txMetadata": {"appName": "waterbridge-neo4j-lineage-lab"},
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise Neo4jEvidenceLineageError(
                "Neo4j LAB Query API 호출에 실패했습니다."
            ) from exc
        if not isinstance(payload, dict) or payload.get("errors"):
            raise Neo4jEvidenceLineageError(
                "Neo4j LAB Query가 fail-closed로 종료됐습니다."
            )
        data = payload.get("data")
        if not isinstance(data, dict):
            return []
        fields = data.get("fields", [])
        values = data.get("values", [])
        if not isinstance(fields, list) or not isinstance(values, list):
            raise Neo4jEvidenceLineageError("Neo4j LAB Query 응답 형식이 올바르지 않습니다.")
        rows: list[dict[str, Any]] = []
        for value_row in values:
            if not isinstance(value_row, list) or len(value_row) != len(fields):
                raise Neo4jEvidenceLineageError(
                    "Neo4j LAB Query 행 형식이 올바르지 않습니다."
                )
            rows.append(dict(zip((str(field) for field in fields), value_row)))
        return rows

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest().upper()


def _resolve_input(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = REPOSITORY_ROOT / resolved
    resolved = resolved.resolve()
    try:
        resolved.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError as exc:
        raise Neo4jEvidenceLineageError(
            "Neo4j LAB 입력은 저장소 내부 파일만 허용합니다."
        ) from exc
    if not resolved.is_file():
        raise Neo4jEvidenceLineageError("Neo4j LAB 입력 파일이 없습니다.")
    return resolved


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError(f"line={line_number}")
            rows.append(value)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
        raise Neo4jEvidenceLineageError(
            "Neo4j LAB JSONL 입력을 읽지 못했습니다."
        ) from exc
    return rows


def _index_unique(
    rows: list[dict[str, Any]],
    key: str,
    *,
    label: str,
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get(key)
        if not isinstance(value, str) or not value or value in indexed:
            raise Neo4jEvidenceLineageError(
                f"{label} Identity가 비어 있거나 중복됐습니다."
            )
        indexed[value] = row
    return indexed


def _validate_lab_record(
    row: Mapping[str, Any],
    *,
    record_type: str,
    retrieval_role: str | None,
) -> None:
    checks = [
        row.get("record_type") == record_type,
        row.get("allowed_use") == "RAG_HANDOFF_ONLY",
        row.get("verification_status") == "TEXT_AND_VISUAL_VERIFIED",
    ]
    if retrieval_role is not None:
        checks.append(row.get("retrieval_role") == retrieval_role)
    if not all(checks):
        raise Neo4jEvidenceLineageError(
            "Neo4j LAB에는 검증된 RAG Handoff 전용 입력만 허용됩니다."
        )


def build_evidence_lineage_graph(
    *,
    parent_pages_path: str | Path = DEFAULT_PARENT_PAGES_PATH,
    child_chunks_path: str | Path = DEFAULT_CHILD_CHUNKS_PATH,
    evidence_groups_path: str | Path = DEFAULT_EVIDENCE_GROUPS_PATH,
) -> EvidenceLineageGraph:
    """고정 3모델 후보 관계를 원문 없는 LAB Graph로 투영한다."""

    paths = {
        "parents": _resolve_input(parent_pages_path),
        "children": _resolve_input(child_chunks_path),
        "evidence_groups": _resolve_input(evidence_groups_path),
    }
    parent_rows = _load_jsonl(paths["parents"])
    child_rows = _load_jsonl(paths["children"])
    group_rows = _load_jsonl(paths["evidence_groups"])
    actual_counts = {
        "parents": len(parent_rows),
        "children": len(child_rows),
        "evidence_groups": len(group_rows),
    }
    if actual_counts != EXPECTED_INPUT_COUNTS:
        raise Neo4jEvidenceLineageError(
            "Neo4j LAB 입력 수가 15 Parent·53 Child·43 Evidence Group 계약과 다릅니다."
        )

    parents = _index_unique(parent_rows, "parent_id", label="Parent")
    children = _index_unique(child_rows, "child_id", label="Child")
    groups = _index_unique(group_rows, "evidence_group_id", label="Evidence Group")
    for parent in parent_rows:
        _validate_lab_record(
            parent,
            record_type="parent",
            retrieval_role="CONTEXT_ONLY",
        )
    for child in child_rows:
        _validate_lab_record(
            child,
            record_type="child",
            retrieval_role="SEARCH_CANDIDATE",
        )
    for group in group_rows:
        _validate_lab_record(
            group,
            record_type="evidence_group",
            retrieval_role=None,
        )

    children_by_group: dict[str, set[str]] = defaultdict(set)
    variants_by_group: dict[str, set[str]] = defaultdict(set)
    pages_by_group: dict[str, set[int]] = defaultdict(set)
    for child_id, child in children.items():
        parent_id = child.get("parent_id")
        group_id = child.get("evidence_group_id")
        parent = parents.get(str(parent_id))
        group = groups.get(str(group_id))
        if parent is None or group is None:
            raise Neo4jEvidenceLineageError(
                "Child의 Parent 또는 Evidence Group 관계가 끊겼습니다."
            )
        equality_fields = ("exact_sales_code", "document_id")
        if any(
            child.get(field_name) != parent.get(field_name)
            or child.get(field_name) != group.get(field_name)
            for field_name in equality_fields
        ):
            raise Neo4jEvidenceLineageError(
                "Child·Parent·Evidence Group의 제품 또는 문서 관계가 다릅니다."
            )
        if (
            child.get("risk_level") != group.get("risk_level")
            or child.get("requires_consultation")
            != group.get("requires_consultation")
        ):
            raise Neo4jEvidenceLineageError(
                "Child·Evidence Group의 Risk 관계가 다릅니다."
            )
        children_by_group[str(group_id)].add(child_id)
        variants_by_group[str(group_id)].add(str(child.get("source_variant_id")))
        page_refs = child.get("page_refs")
        if not isinstance(page_refs, list) or not all(
            isinstance(page, int) for page in page_refs
        ):
            raise Neo4jEvidenceLineageError("Child Page 관계가 올바르지 않습니다.")
        pages_by_group[str(group_id)].update(page_refs)

    for group_id, group in groups.items():
        expected_children = set(group.get("child_ids", []))
        expected_variants = set(group.get("source_variant_ids", []))
        expected_pages = set(group.get("page_refs", []))
        if (
            children_by_group[group_id] != expected_children
            or variants_by_group[group_id] != expected_variants
            or pages_by_group[group_id] != expected_pages
        ):
            raise Neo4jEvidenceLineageError(
                "Evidence Group의 Child·Variant·Page 관계가 원본 계약과 다릅니다."
            )

    nodes: dict[tuple[str, str], GraphNode] = {}
    edges: dict[tuple[str, str, str, str, str], GraphEdge] = {}

    def add_node(
        label: str,
        node_id: str,
        properties: Mapping[str, JsonScalar],
    ) -> None:
        if label not in NODE_LABELS:
            raise Neo4jEvidenceLineageError("허용되지 않은 LAB Node Label입니다.")
        if set(properties) - ALLOWED_NODE_PROPERTIES[label]:
            raise Neo4jEvidenceLineageError("LAB Node에 허용되지 않은 속성이 있습니다.")
        if set(properties).intersection(FORBIDDEN_SOURCE_FIELDS):
            raise Neo4jEvidenceLineageError("LAB Graph에 Source 본문 속성을 넣을 수 없습니다.")
        key = (label, node_id)
        candidate = GraphNode(label, node_id, dict(properties))
        existing = nodes.get(key)
        if existing is not None and existing != candidate:
            raise Neo4jEvidenceLineageError("같은 LAB Node Identity의 속성이 충돌합니다.")
        nodes[key] = candidate

    def add_edge(
        source_label: str,
        source_id: str,
        relationship: str,
        target_label: str,
        target_id: str,
        properties: Mapping[str, JsonScalar] | None = None,
    ) -> None:
        if relationship not in RELATIONSHIP_TYPES:
            raise Neo4jEvidenceLineageError("허용되지 않은 LAB Relationship입니다.")
        edge_properties = dict(properties or {})
        if relationship != "COVERS_TOPIC" and edge_properties:
            raise Neo4jEvidenceLineageError("Source Relationship에는 속성을 추가하지 않습니다.")
        if relationship == "COVERS_TOPIC" and set(edge_properties) != {
            "evidence_group_count"
        }:
            raise Neo4jEvidenceLineageError("COVERS_TOPIC 집계 속성이 올바르지 않습니다.")
        key = (
            source_label,
            source_id,
            relationship,
            target_label,
            target_id,
        )
        candidate = GraphEdge(
            source_label,
            source_id,
            relationship,
            target_label,
            target_id,
            edge_properties,
        )
        existing = edges.get(key)
        if existing is not None and existing != candidate:
            raise Neo4jEvidenceLineageError("같은 LAB Relationship의 속성이 충돌합니다.")
        edges[key] = candidate

    for parent_id, parent in sorted(parents.items()):
        model_code = str(parent["exact_sales_code"])
        generation = str(parent["product_generation"])
        document_id = str(parent["document_id"])
        version = str(parent["version"])
        page_ref = int(parent["page_refs"][0])
        add_node(
            "Product",
            model_code,
            {
                "display_label": model_code,
                "model_code": model_code,
                "product_generation": generation,
            },
        )
        add_node(
            "Document",
            document_id,
            {
                "display_label": f"Official Manual ({model_code})",
                "model_code": model_code,
                "document_version": version,
            },
        )
        add_node(
            "ParentPage",
            parent_id,
            {
                "display_label": f"Page {page_ref}",
                "model_code": model_code,
                "page_ref": page_ref,
                "verification_status": str(parent["verification_status"]),
            },
        )
        add_edge("Product", model_code, "HAS_DOCUMENT", "Document", document_id)
        add_edge(
            "Document",
            document_id,
            "HAS_PARENT_PAGE",
            "ParentPage",
            parent_id,
        )

    product_topic_counts: Counter[tuple[str, str]] = Counter()
    for group_id, group in sorted(groups.items()):
        model_code = str(group["exact_sales_code"])
        topic_code = str(group["topic_code"])
        add_node(
            "EvidenceGroup",
            group_id,
            {
                "display_label": "Evidence Group",
                "model_code": model_code,
                "topic_code": topic_code,
                "risk_level": str(group["risk_level"]),
                "requires_consultation": bool(group["requires_consultation"]),
                "verification_status": str(group["verification_status"]),
            },
        )
        add_node(
            "Topic",
            topic_code,
            {
                "display_label": topic_code,
                "topic_code": topic_code,
            },
        )
        add_edge("EvidenceGroup", group_id, "ABOUT", "Topic", topic_code)
        product_topic_counts[(model_code, topic_code)] += 1

    for ordinal, (child_id, child) in enumerate(sorted(children.items()), start=1):
        model_code = str(child["exact_sales_code"])
        add_node(
            "EvidenceChunk",
            child_id,
            {
                "display_label": f"Evidence {ordinal:03d}",
                "model_code": model_code,
                "risk_level": str(child["risk_level"]),
                "requires_consultation": bool(child["requires_consultation"]),
                "verification_status": str(child["verification_status"]),
            },
        )
        add_edge(
            "ParentPage",
            str(child["parent_id"]),
            "HAS_CHILD",
            "EvidenceChunk",
            child_id,
        )
        add_edge(
            "EvidenceChunk",
            child_id,
            "MEMBER_OF",
            "EvidenceGroup",
            str(child["evidence_group_id"]),
        )

    for (model_code, topic_code), count in sorted(product_topic_counts.items()):
        add_edge(
            "Product",
            model_code,
            "COVERS_TOPIC",
            "Topic",
            topic_code,
            {"evidence_group_count": count},
        )

    input_files = {
        key: {
            "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256_file(path),
            "row_count": actual_counts[key],
        }
        for key, path in paths.items()
    }
    return EvidenceLineageGraph(
        nodes=tuple(nodes[key] for key in sorted(nodes)),
        edges=tuple(edges[key] for key in sorted(edges)),
        input_files=input_files,
    )


def load_graph_into_neo4j(
    graph: EvidenceLineageGraph,
    executor: Neo4jQueryExecutor,
) -> None:
    """Disposable LAB DB를 비우고 Parameterized Cypher로 Projection을 적재한다."""

    executor.query("MATCH (n) DETACH DELETE n RETURN count(n) AS deleted")
    for label in NODE_LABELS:
        constraint_name = f"neo4j_lineage_{label.casefold()}_id"
        executor.query(
            f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.id IS UNIQUE"
        )
        rows = [node.as_row() for node in graph.nodes if node.label == label]
        executor.query(
            f"UNWIND $rows AS row MERGE (n:{label} {{id: row.id}}) "
            "SET n += row RETURN count(n) AS loaded",
            {"rows": rows},
        )

    for relationship in RELATIONSHIP_TYPES:
        matching = [
            edge for edge in graph.edges if edge.relationship == relationship
        ]
        grouped: dict[tuple[str, str], list[GraphEdge]] = defaultdict(list)
        for edge in matching:
            grouped[(edge.source_label, edge.target_label)].append(edge)
        for (source_label, target_label), edges in sorted(grouped.items()):
            rows = [edge.as_row() for edge in edges]
            executor.query(
                f"UNWIND $rows AS row MATCH (source:{source_label} {{id: row.source_id}}) "
                f"MATCH (target:{target_label} {{id: row.target_id}}) "
                f"MERGE (source)-[rel:{relationship}]->(target) "
                "SET rel += row.properties RETURN count(rel) AS loaded",
                {"rows": rows},
            )


def verify_graph_in_neo4j(
    graph: EvidenceLineageGraph,
    executor: Neo4jQueryExecutor,
) -> dict[str, Any]:
    """실제 Neo4j 결과를 Projection 기대값과 대조한다."""

    component_rows = executor.query(
        "CALL dbms.components() YIELD name, versions, edition "
        "RETURN name, versions[0] AS version, edition"
    )
    kernel_rows = [
        row for row in component_rows if row.get("name") == "Neo4j Kernel"
    ]
    if len(kernel_rows) != 1:
        raise Neo4jEvidenceLineageError("Neo4j Component Identity를 확인하지 못했습니다.")
    kernel = kernel_rows[0]
    node_rows = executor.query(
        "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY label"
    )
    relationship_rows = executor.query(
        "MATCH ()-[r]->() RETURN type(r) AS relationship, count(r) AS count "
        "ORDER BY relationship"
    )
    orphan_rows = executor.query(
        "MATCH (c:EvidenceChunk) "
        "WHERE NOT EXISTS { MATCH (:ParentPage)-[:HAS_CHILD]->(c) } "
        "OR NOT EXISTS { MATCH (c)-[:MEMBER_OF]->(:EvidenceGroup) } "
        "RETURN count(c) AS orphan_chunk_count"
    )
    cross_model_rows = executor.query(
        "MATCH (p:Product)-[:HAS_DOCUMENT]->(:Document)-[:HAS_PARENT_PAGE]->"
        "(:ParentPage)-[:HAS_CHILD]->(c:EvidenceChunk) "
        "WHERE p.model_code <> c.model_code "
        "RETURN count(c) AS cross_model_path_count"
    )
    visual_rows = executor.query(
        "MATCH (p:Product)-[r:COVERS_TOPIC]->(t:Topic) "
        "RETURN p.model_code AS model_code, t.topic_code AS topic_code, "
        "r.evidence_group_count AS evidence_group_count "
        "ORDER BY model_code, topic_code"
    )

    actual_node_counts = {
        str(row["label"]): int(row["count"]) for row in node_rows
    }
    actual_relationship_counts = {
        str(row["relationship"]): int(row["count"])
        for row in relationship_rows
    }
    orphan_count = int(orphan_rows[0]["orphan_chunk_count"])
    cross_model_count = int(cross_model_rows[0]["cross_model_path_count"])
    expected_visual_count = graph.relationship_counts()["COVERS_TOPIC"]
    issues: list[str] = []
    if actual_node_counts != graph.node_counts():
        issues.append("NODE_COUNT_MISMATCH")
    if actual_relationship_counts != graph.relationship_counts():
        issues.append("RELATIONSHIP_COUNT_MISMATCH")
    if orphan_count != 0:
        issues.append("ORPHAN_CHUNK_PRESENT")
    if cross_model_count != 0:
        issues.append("CROSS_MODEL_PATH_PRESENT")
    if len(visual_rows) != expected_visual_count:
        issues.append("VISUAL_SUMMARY_COUNT_MISMATCH")
    return {
        "database_validation": "PASS" if not issues else "FAIL",
        "neo4j": {
            "name": str(kernel["name"]),
            "version": str(kernel["version"]),
            "edition": str(kernel["edition"]),
            "endpoint_class": "LOOPBACK_QUERY_API_V2_AUTH_DISABLED",
        },
        "node_counts": actual_node_counts,
        "relationship_counts": actual_relationship_counts,
        "orphan_chunk_count": orphan_count,
        "cross_model_path_count": cross_model_count,
        "visual_summary": {
            "row_count": len(visual_rows),
            "result_set_sha256": canonical_json_sha256(visual_rows),
            "rows": visual_rows,
        },
        "issues": issues,
    }


def render_lineage_svg(report: Mapping[str, Any]) -> str:
    """실제 Neo4j Product–Topic 집계 결과만 포함하는 정제 SVG를 만든다."""

    visual = report.get("visual_summary")
    if not isinstance(visual, Mapping) or not isinstance(visual.get("rows"), list):
        raise Neo4jEvidenceLineageError("Neo4j 시각화 결과가 없습니다.")
    rows = visual["rows"]
    products = sorted({str(row["model_code"]) for row in rows})
    topics = sorted({str(row["topic_code"]) for row in rows})
    if not products or not topics:
        raise Neo4jEvidenceLineageError("Neo4j 시각화 Node가 없습니다.")

    width = 1440
    height = max(900, 190 + max(len(products), len(topics)) * 68)
    left_x = 250
    right_x = 1120
    top_y = 150
    usable_height = height - 260
    product_positions = {
        product: top_y + index * usable_height / max(1, len(products) - 1)
        for index, product in enumerate(products)
    }
    topic_positions = {
        topic: top_y + index * usable_height / max(1, len(topics) - 1)
        for index, topic in enumerate(topics)
    }
    colors = ["#00B7C7", "#7B61FF", "#FF8A4C"]
    color_by_product = {
        product: colors[index % len(colors)]
        for index, product in enumerate(products)
    }

    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        "<defs>",
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">',
        '<feDropShadow dx="0" dy="4" stdDeviation="6" flood-opacity="0.22"/>',
        "</filter>",
        "</defs>",
        '<rect width="100%" height="100%" fill="#07111F"/>',
        '<text x="70" y="62" fill="#F7FAFC" font-family="Segoe UI, sans-serif" '
        'font-size="30" font-weight="700">Neo4j Evidence Lineage Lab</text>',
        '<text x="70" y="96" fill="#93A4BA" font-family="Segoe UI, sans-serif" '
        'font-size="16">LAB_ONLY · Query API validated · Production runtime disconnected</text>',
        '<text x="250" y="128" text-anchor="middle" fill="#8DA2BD" '
        'font-family="Segoe UI, sans-serif" font-size="15">PRODUCT</text>',
        '<text x="1120" y="128" text-anchor="middle" fill="#8DA2BD" '
        'font-family="Segoe UI, sans-serif" font-size="15">EVIDENCE TOPIC</text>',
    ]
    for row in rows:
        product = str(row["model_code"])
        topic = str(row["topic_code"])
        count = int(row["evidence_group_count"])
        y1 = product_positions[product]
        y2 = topic_positions[topic]
        color = color_by_product[product]
        mid_x = (left_x + right_x) / 2
        svg.extend(
            [
                f'<path d="M {left_x + 135:.1f} {y1:.1f} C {mid_x:.1f} {y1:.1f}, '
                f'{mid_x:.1f} {y2:.1f}, {right_x - 155:.1f} {y2:.1f}" '
                f'stroke="{color}" stroke-opacity="0.42" stroke-width="{1.5 + min(count, 5):.1f}" '
                'fill="none"/>',
                f'<circle cx="{mid_x:.1f}" cy="{(y1 + y2) / 2:.1f}" r="12" '
                'fill="#13263D" stroke="#5A6F89"/>',
                f'<text x="{mid_x:.1f}" y="{(y1 + y2) / 2 + 5:.1f}" '
                'text-anchor="middle" fill="#E7EEF8" font-family="Segoe UI, sans-serif" '
                f'font-size="12">{count}</text>',
            ]
        )
    for product, y in product_positions.items():
        color = color_by_product[product]
        svg.extend(
            [
                f'<rect x="{left_x - 135}" y="{y - 30:.1f}" width="270" height="60" '
                f'rx="16" fill="#10243A" stroke="{color}" stroke-width="2" filter="url(#shadow)"/>',
                f'<text x="{left_x}" y="{y + 6:.1f}" text-anchor="middle" fill="#F7FAFC" '
                'font-family="Segoe UI, sans-serif" font-size="17" font-weight="650">'
                f'{escape(product)}</text>',
            ]
        )
    for topic, y in topic_positions.items():
        svg.extend(
            [
                f'<rect x="{right_x - 155}" y="{y - 25:.1f}" width="310" height="50" '
                'rx="25" fill="#14263B" stroke="#7890AB" stroke-width="1.5"/>',
                f'<text x="{right_x}" y="{y + 5:.1f}" text-anchor="middle" fill="#E9F0F8" '
                'font-family="Segoe UI, sans-serif" font-size="14">'
                f'{escape(topic)}</text>',
            ]
        )
    neo4j = report.get("neo4j", {})
    version = escape(str(neo4j.get("version", "UNKNOWN")))
    svg.extend(
        [
            f'<text x="70" y="{height - 72}" fill="#91A5BE" font-family="Segoe UI, sans-serif" '
            f'font-size="14">Neo4j Community {version} · Edge labels show Evidence Group counts</text>',
            f'<text x="70" y="{height - 44}" fill="#647A94" font-family="Segoe UI, sans-serif" '
            'font-size="13">No source text, vectors, prompts, scores, customer data, or public runtime claims.</text>',
            "</svg>",
        ]
    )
    return "\n".join(svg) + "\n"


VISUAL_BROWSER_QUERY = (
    "MATCH (p:Product)-[r:COVERS_TOPIC]->(t:Topic) "
    "RETURN p, r, t ORDER BY p.model_code, t.topic_code"
)


__all__ = [
    "DEFAULT_CHILD_CHUNKS_PATH",
    "DEFAULT_EVIDENCE_GROUPS_PATH",
    "DEFAULT_PARENT_PAGES_PATH",
    "EvidenceLineageGraph",
    "GraphEdge",
    "GraphNode",
    "Neo4jEvidenceLineageError",
    "Neo4jHttpQueryClient",
    "Neo4jQueryExecutor",
    "VISUAL_BROWSER_QUERY",
    "build_evidence_lineage_graph",
    "canonical_json_sha256",
    "load_graph_into_neo4j",
    "render_lineage_svg",
    "verify_graph_in_neo4j",
]
