"""Neo4j Evidence Lineage LAB 전용 읽기 전용 Graph Projection."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
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

LAB_LOOPBACK_PROFILE = "lab_loopback"
QA_EPHEMERAL_LOOPBACK_PROFILE = "qa_ephemeral_loopback"
SUPPORTED_NEO4J_PROFILES = {
    LAB_LOOPBACK_PROFILE,
    QA_EPHEMERAL_LOOPBACK_PROFILE,
}
QA_NODE_LABEL = "WaterbridgeQaLineage"
QA_TARGET_LABEL = "WaterbridgeQaTarget"
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
TARGET_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
SHA256_PATTERN = re.compile(r"[A-Fa-f0-9]{64}")
IMAGE_DIGEST_PATTERN = re.compile(r"sha256:[A-Fa-f0-9]{64}")
_TARGET_VERIFICATION_CAPABILITY = object()

JsonScalar = str | int | float | bool | None


class Neo4jEvidenceLineageError(RuntimeError):
    """독립 Graph LAB 입력·실행·정합성 실패."""


def _validated_run_id(value: str) -> str:
    if RUN_ID_PATTERN.fullmatch(value) is None:
        raise Neo4jEvidenceLineageError("Neo4j QA run_id 형식이 올바르지 않습니다.")
    return value


def _validated_image_digest(value: str) -> str:
    if IMAGE_DIGEST_PATTERN.fullmatch(value) is None:
        raise Neo4jEvidenceLineageError(
            "Neo4j 이미지 Digest는 sha256 형식이어야 합니다."
        )
    return value.casefold()


@dataclass(frozen=True, slots=True)
class Neo4jQaTargetIdentity:
    """Infra가 컨테이너 초기화 단계에서 독립 생성한 QA 대상 표식."""

    target_id: str
    run_id: str
    nonce_sha256: str
    database: str
    image_digest: str

    def __post_init__(self) -> None:
        if TARGET_ID_PATTERN.fullmatch(self.target_id) is None:
            raise Neo4jEvidenceLineageError(
                "Neo4j QA target_id 형식이 올바르지 않습니다."
            )
        _validated_run_id(self.run_id)
        if SHA256_PATTERN.fullmatch(self.nonce_sha256) is None:
            raise Neo4jEvidenceLineageError(
                "Neo4j QA nonce SHA-256 형식이 올바르지 않습니다."
            )
        if self.database != "neo4j":
            raise Neo4jEvidenceLineageError(
                "Neo4j QA는 전용 컨테이너의 neo4j Database만 허용합니다."
            )
        _validated_image_digest(self.image_digest)

    def expected_marker(self) -> dict[str, str]:
        return {
            "target_id": self.target_id,
            "run_id": self.run_id,
            "nonce_sha256": self.nonce_sha256.casefold(),
            "database": self.database,
            "image_digest": self.image_digest.casefold(),
        }


@dataclass(frozen=True, slots=True)
class _Neo4jTargetVerification:
    """적재 직전 읽기 전용 대상 검증 결과."""

    profile: str
    run_id: str
    database: str
    marker_validated: bool
    unexpected_node_count: int
    relationship_count: int
    executor_identity: int
    expected_marker_sha256: str | None
    _capability: object


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
class VisualQueryPreset:
    """Neo4j Browser에서 재현할 수 있는 정제 시각 검증 Query."""

    query_id: str
    title: str
    purpose: str
    statement: str
    expected_result: Mapping[str, JsonScalar]

    def manifest_row(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "title": self.title,
            "purpose": self.purpose,
            "expected_result": dict(self.expected_result),
            "statement_sha256": sha256(
                self.statement.encode("utf-8")
            ).hexdigest().upper(),
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

    def canonical_nodes(self) -> list[dict[str, Any]]:
        return sorted(
            (
                {
                    "kind": node.label,
                    "id": node.node_id,
                    "properties": node.as_row(),
                }
                for node in self.nodes
            ),
            key=lambda row: (
                str(row["kind"]),
                str(row["id"]),
                json.dumps(
                    row["properties"],
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )

    def canonical_relationships(self) -> list[dict[str, Any]]:
        return sorted(
            (
                {
                    "source_kind": edge.source_label,
                    "source_id": edge.source_id,
                    "relationship": edge.relationship,
                    "target_kind": edge.target_label,
                    "target_id": edge.target_id,
                    "properties": dict(edge.properties),
                }
                for edge in self.edges
            ),
            key=lambda row: (
                str(row["source_kind"]),
                str(row["source_id"]),
                str(row["relationship"]),
                str(row["target_kind"]),
                str(row["target_id"]),
                json.dumps(
                    row["properties"],
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )

    def canonical_snapshot(self) -> dict[str, Any]:
        return {
            "nodes": self.canonical_nodes(),
            "relationships": self.canonical_relationships(),
        }

    def projection_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "2.0.0",
            "scope": "JSONL_BASED_LINEAGE_QA",
            "input_source": "REPOSITORY_JSONL_ONLY",
            "rds_connected": False,
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
    """공용 Endpoint를 거부하는 Loopback Neo4j Query API v2 Client."""

    def __init__(
        self,
        endpoint: str,
        *,
        profile: str = LAB_LOOPBACK_PROFILE,
        database: str = "neo4j",
        username: str | None = None,
        password: str | None = None,
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
                "Neo4j Query API는 전용 컨테이너의 HTTP Loopback Endpoint만 허용합니다."
            )
        if profile not in SUPPORTED_NEO4J_PROFILES:
            raise Neo4jEvidenceLineageError("지원하지 않는 Neo4j 실행 Profile입니다.")
        if database != "neo4j":
            raise Neo4jEvidenceLineageError(
                "Neo4j QA는 전용 컨테이너의 neo4j Database만 허용합니다."
            )
        if profile == LAB_LOOPBACK_PROFILE:
            if username is not None or password is not None:
                raise Neo4jEvidenceLineageError(
                    "Neo4j LAB Profile에는 인증 정보를 전달하지 않습니다."
                )
            auth: httpx.Auth | None = None
            endpoint_class = "LAB_LOOPBACK_QUERY_API_V2_AUTH_DISABLED"
        else:
            if not username or not password:
                raise Neo4jEvidenceLineageError(
                    "Neo4j QA Profile에는 Basic 인증 Secret이 필요합니다."
                )
            auth = httpx.BasicAuth(username, password)
            endpoint_class = "QA_EPHEMERAL_LOOPBACK_QUERY_API_V2_BASIC_AUTH"
        self.endpoint = normalized
        self.profile = profile
        self.database = database
        self.endpoint_class = endpoint_class
        self._auth = auth
        self._client = http_client or httpx.Client(
            timeout=10.0,
            follow_redirects=False,
            trust_env=False,
        )
        self._owns_client = http_client is None

    def query(
        self,
        statement: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        compact_statement = " ".join(statement.split())
        try:
            response = self._client.post(
                f"{self.endpoint}/db/{self.database}/query/v2",
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                auth=self._auth,
                json={
                    "statement": compact_statement,
                    "parameters": dict(parameters or {}),
                    "maxExecutionTime": 10,
                    "txMetadata": {"appName": "waterbridge-neo4j-lineage-qa"},
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


def _single_int(rows: list[dict[str, Any]], key: str) -> int:
    if len(rows) != 1 or key not in rows[0]:
        raise Neo4jEvidenceLineageError(
            "Neo4j QA Count Query 응답 형식이 올바르지 않습니다."
        )
    value = rows[0][key]
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise Neo4jEvidenceLineageError(
            "Neo4j QA Count Query 응답 값이 올바르지 않습니다."
        )
    return value


def _qa_marker_matches(
    rows: list[dict[str, Any]],
    target_identity: Neo4jQaTargetIdentity,
) -> bool:
    if len(rows) != 1:
        return False
    marker = rows[0]
    labels = marker.get("labels")
    actual_marker = {
        "target_id": marker.get("target_id"),
        "run_id": marker.get("run_id"),
        "nonce_sha256": str(marker.get("nonce_sha256", "")).casefold(),
        "database": marker.get("database"),
        "image_digest": str(marker.get("image_digest", "")).casefold(),
    }
    return labels == [QA_TARGET_LABEL] and (
        actual_marker == target_identity.expected_marker()
    )


def _query_qa_marker(executor: Neo4jQueryExecutor) -> list[dict[str, Any]]:
    return executor.query(
        f"MATCH (marker:{QA_TARGET_LABEL}) "
        "RETURN labels(marker) AS labels, marker.target_id AS target_id, "
        "marker.run_id AS run_id, marker.nonce_sha256 AS nonce_sha256, "
        "marker.database AS database, marker.image_digest AS image_digest"
    )


def _assert_target_verification(
    executor: Neo4jQueryExecutor,
    verification: _Neo4jTargetVerification,
) -> None:
    if (
        verification._capability is not _TARGET_VERIFICATION_CAPABILITY
        or verification.executor_identity != id(executor)
        or verification.profile not in SUPPORTED_NEO4J_PROFILES
        or verification.database != "neo4j"
        or verification.unexpected_node_count != 0
        or verification.relationship_count != 0
        or getattr(executor, "profile", verification.profile)
        != verification.profile
        or str(getattr(executor, "database", verification.database))
        != verification.database
    ):
        raise Neo4jEvidenceLineageError("Neo4j 대상 검증 capability가 올바르지 않습니다.")


def preflight_neo4j_target(
    executor: Neo4jQueryExecutor,
    *,
    profile: str,
    run_id: str,
    target_identity: Neo4jQaTargetIdentity | None = None,
) -> _Neo4jTargetVerification:
    """어떤 Graph도 쓰기 전에 전용·빈 대상임을 fail-closed로 확인한다."""

    _validated_run_id(run_id)
    if profile not in SUPPORTED_NEO4J_PROFILES:
        raise Neo4jEvidenceLineageError("지원하지 않는 Neo4j 실행 Profile입니다.")
    executor_profile = getattr(executor, "profile", profile)
    database = str(getattr(executor, "database", "neo4j"))
    if executor_profile != profile or database != "neo4j":
        raise Neo4jEvidenceLineageError(
            "Neo4j Client와 대상 검증 Profile이 일치하지 않습니다."
        )

    marker_validated = False
    if profile == LAB_LOOPBACK_PROFILE:
        if target_identity is not None:
            raise Neo4jEvidenceLineageError(
                "Neo4j LAB Profile에는 QA 대상 표식을 전달하지 않습니다."
            )
        unexpected_node_count = _single_int(
            executor.query("MATCH (n) RETURN count(n) AS unexpected_node_count"),
            "unexpected_node_count",
        )
    else:
        if target_identity is None or target_identity.run_id != run_id:
            raise Neo4jEvidenceLineageError(
                "Neo4j QA 대상 표식이 없거나 run_id가 일치하지 않습니다."
            )
        marker_rows = _query_qa_marker(executor)
        if not _qa_marker_matches(marker_rows, target_identity):
            raise Neo4jEvidenceLineageError(
                "Neo4j QA 대상 표식이 실행 계약과 일치하지 않습니다."
            )
        marker_validated = True
        unexpected_node_count = _single_int(
            executor.query(
                f"MATCH (n) WHERE NOT n:{QA_TARGET_LABEL} "
                "RETURN count(n) AS unexpected_node_count"
            ),
            "unexpected_node_count",
        )

    relationship_count = _single_int(
        executor.query("MATCH ()-[rel]->() RETURN count(rel) AS relationship_count"),
        "relationship_count",
    )
    if unexpected_node_count != 0 or relationship_count != 0:
        raise Neo4jEvidenceLineageError(
            "Neo4j QA 대상에 예상 밖 Graph가 있어 적재를 거부합니다."
        )
    return _Neo4jTargetVerification(
        profile=profile,
        run_id=run_id,
        database=database,
        marker_validated=marker_validated,
        unexpected_node_count=unexpected_node_count,
        relationship_count=relationship_count,
        executor_identity=id(executor),
        expected_marker_sha256=(
            canonical_json_sha256(target_identity.expected_marker())
            if target_identity is not None
            else None
        ),
        _capability=_TARGET_VERIFICATION_CAPABILITY,
    )


def _load_verified_graph_into_neo4j(
    graph: EvidenceLineageGraph,
    executor: Neo4jQueryExecutor,
    *,
    verification: _Neo4jTargetVerification,
) -> None:
    """검증된 빈 일회성 DB에 run 범위 Projection만 적재한다."""

    _assert_target_verification(executor, verification)
    run_id = _validated_run_id(verification.run_id)
    if (
        verification.profile == QA_EPHEMERAL_LOOPBACK_PROFILE
        and not verification.marker_validated
    ):
        raise Neo4jEvidenceLineageError("Neo4j QA 대상 표식 검증이 완료되지 않았습니다.")

    for label in NODE_LABELS:
        rows = [
            {
                **node.as_row(),
                "qa_run_id": run_id,
                "qa_kind": label,
                "qa_key": f"{run_id}:{label}:{node.node_id}",
            }
            for node in graph.nodes
            if node.label == label
        ]
        loaded = _single_int(
            executor.query(
                f"UNWIND $rows AS row CREATE (n:{QA_NODE_LABEL}:{label}) "
                "SET n = row RETURN count(n) AS loaded",
                {"rows": rows},
            ),
            "loaded",
        )
        if loaded != len(rows):
            raise Neo4jEvidenceLineageError(
                "Neo4j QA Node 적재 건수가 Projection과 다릅니다."
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
            loaded = _single_int(
                executor.query(
                    f"UNWIND $rows AS row MATCH (source:{QA_NODE_LABEL}:{source_label} "
                    "{qa_run_id: $run_id, id: row.source_id}) "
                    f"MATCH (target:{QA_NODE_LABEL}:{target_label} "
                    "{qa_run_id: $run_id, id: row.target_id}) "
                    f"CREATE (source)-[rel:{relationship}]->(target) "
                    "SET rel = row.properties, rel.qa_run_id = $run_id "
                    "RETURN count(rel) AS loaded",
                    {"rows": rows, "run_id": run_id},
                ),
                "loaded",
            )
            if loaded != len(rows):
                raise Neo4jEvidenceLineageError(
                    "Neo4j QA Relationship 적재 건수가 Projection과 다릅니다."
                )


def load_graph_into_neo4j(
    graph: EvidenceLineageGraph,
    executor: Neo4jQueryExecutor,
    *,
    profile: str,
    run_id: str,
    target_identity: Neo4jQaTargetIdentity | None = None,
) -> _Neo4jTargetVerification:
    """대상 preflight와 Graph 적재를 하나의 fail-closed mutation API로 묶는다."""

    verification = preflight_neo4j_target(
        executor,
        profile=profile,
        run_id=run_id,
        target_identity=target_identity,
    )
    try:
        _load_verified_graph_into_neo4j(
            graph,
            executor,
            verification=verification,
        )
    except Exception:
        cleanup_graph_run(
            executor,
            verification=verification,
            target_identity=target_identity,
        )
        raise
    return verification


def _canonical_actual_nodes(
    rows: list[dict[str, Any]],
    *,
    run_id: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    normalized: list[dict[str, Any]] = []
    issues: list[str] = []
    for row in rows:
        kind = row.get("kind")
        node_id = row.get("id")
        labels = row.get("labels")
        properties = row.get("properties")
        if (
            kind not in NODE_LABELS
            or not isinstance(node_id, str)
            or not isinstance(labels, list)
            or set(labels) != {QA_NODE_LABEL, kind}
            or not isinstance(properties, dict)
        ):
            issues.append("NODE_NAMESPACE_METADATA_MISMATCH")
            continue
        safe_properties = dict(properties)
        internal = {
            "qa_run_id": safe_properties.pop("qa_run_id", None),
            "qa_kind": safe_properties.pop("qa_kind", None),
            "qa_key": safe_properties.pop("qa_key", None),
        }
        if internal != {
            "qa_run_id": run_id,
            "qa_kind": kind,
            "qa_key": f"{run_id}:{kind}:{node_id}",
        }:
            issues.append("NODE_NAMESPACE_METADATA_MISMATCH")
        normalized.append(
            {"kind": kind, "id": node_id, "properties": safe_properties}
        )
    return (
        sorted(
            normalized,
            key=lambda row: (
                row["kind"],
                row["id"],
                json.dumps(
                    row["properties"],
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        ),
        issues,
    )


def _canonical_actual_relationships(
    rows: list[dict[str, Any]],
    *,
    run_id: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    normalized: list[dict[str, Any]] = []
    issues: list[str] = []
    for row in rows:
        source_kind = row.get("source_kind")
        source_id = row.get("source_id")
        relationship = row.get("relationship")
        target_kind = row.get("target_kind")
        target_id = row.get("target_id")
        properties = row.get("properties")
        if (
            source_kind not in NODE_LABELS
            or target_kind not in NODE_LABELS
            or relationship not in RELATIONSHIP_TYPES
            or not isinstance(source_id, str)
            or not isinstance(target_id, str)
            or not isinstance(properties, dict)
        ):
            issues.append("RELATIONSHIP_NAMESPACE_METADATA_MISMATCH")
            continue
        safe_properties = dict(properties)
        if safe_properties.pop("qa_run_id", None) != run_id:
            issues.append("RELATIONSHIP_NAMESPACE_METADATA_MISMATCH")
        normalized.append(
            {
                "source_kind": source_kind,
                "source_id": source_id,
                "relationship": relationship,
                "target_kind": target_kind,
                "target_id": target_id,
                "properties": safe_properties,
            }
        )
    return (
        sorted(
            normalized,
            key=lambda row: (
                row["source_kind"],
                row["source_id"],
                row["relationship"],
                row["target_kind"],
                row["target_id"],
                json.dumps(
                    row["properties"],
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        ),
        issues,
    )


def _has_duplicate_identities(
    rows: list[dict[str, Any]],
    fields: tuple[str, ...],
) -> bool:
    identities = [tuple(str(row[field]) for field in fields) for row in rows]
    return len(identities) != len(set(identities))


def verify_graph_in_neo4j(
    graph: EvidenceLineageGraph,
    executor: Neo4jQueryExecutor,
    *,
    run_id: str,
) -> dict[str, Any]:
    """실제 Neo4j의 ID·속성·관계 전수 Snapshot을 Projection과 대조한다."""

    _validated_run_id(run_id)
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
    raw_node_rows = executor.query(
        f"MATCH (n:{QA_NODE_LABEL} {{qa_run_id: $run_id}}) "
        "RETURN labels(n) AS labels, n.qa_kind AS kind, n.id AS id, "
        "properties(n) AS properties ORDER BY kind, id",
        {"run_id": run_id},
    )
    raw_relationship_rows = executor.query(
        f"MATCH (source:{QA_NODE_LABEL} {{qa_run_id: $run_id}})"
        "-[rel]->"
        f"(target:{QA_NODE_LABEL} {{qa_run_id: $run_id}}) "
        "WHERE rel.qa_run_id = $run_id "
        "RETURN source.qa_kind AS source_kind, source.id AS source_id, "
        "type(rel) AS relationship, target.qa_kind AS target_kind, "
        "target.id AS target_id, properties(rel) AS properties "
        "ORDER BY source_kind, source_id, relationship, target_kind, target_id",
        {"run_id": run_id},
    )
    cross_namespace_count = _single_int(
        executor.query(
            f"MATCH (node:{QA_NODE_LABEL} {{qa_run_id: $run_id}})-[rel]-(other) "
            f"WHERE NOT other:{QA_NODE_LABEL} "
            "OR coalesce(other.qa_run_id, '') <> $run_id "
            "OR coalesce(rel.qa_run_id, '') <> $run_id "
            "RETURN count(DISTINCT rel) AS cross_namespace_relationship_count",
            {"run_id": run_id},
        ),
        "cross_namespace_relationship_count",
    )
    orphan_count = _single_int(
        executor.query(
            f"MATCH (c:{QA_NODE_LABEL}:EvidenceChunk {{qa_run_id: $run_id}}) "
            "WHERE NOT EXISTS { "
            f"MATCH (:{QA_NODE_LABEL}:ParentPage {{qa_run_id: $run_id}})"
            "-[:HAS_CHILD {qa_run_id: $run_id}]->(c) } "
            "OR NOT EXISTS { MATCH (c)-[:MEMBER_OF {qa_run_id: $run_id}]->"
            f"(:{QA_NODE_LABEL}:EvidenceGroup {{qa_run_id: $run_id}}) }} "
            "RETURN count(c) AS orphan_chunk_count",
            {"run_id": run_id},
        ),
        "orphan_chunk_count",
    )
    cross_model_count = _single_int(
        executor.query(
            f"MATCH (p:{QA_NODE_LABEL}:Product {{qa_run_id: $run_id}})"
            "-[:HAS_DOCUMENT {qa_run_id: $run_id}]->"
            f"(:{QA_NODE_LABEL}:Document {{qa_run_id: $run_id}})"
            "-[:HAS_PARENT_PAGE {qa_run_id: $run_id}]->"
            f"(:{QA_NODE_LABEL}:ParentPage {{qa_run_id: $run_id}})"
            "-[:HAS_CHILD {qa_run_id: $run_id}]->"
            f"(c:{QA_NODE_LABEL}:EvidenceChunk {{qa_run_id: $run_id}}) "
            "WHERE p.model_code <> c.model_code "
            "RETURN count(c) AS cross_model_path_count",
            {"run_id": run_id},
        ),
        "cross_model_path_count",
    )
    visual_rows = executor.query(
        f"MATCH (p:{QA_NODE_LABEL}:Product {{qa_run_id: $run_id}})"
        "-[rel:COVERS_TOPIC {qa_run_id: $run_id}]->"
        f"(t:{QA_NODE_LABEL}:Topic {{qa_run_id: $run_id}}) "
        "RETURN p.model_code AS model_code, t.topic_code AS topic_code, "
        "rel.evidence_group_count AS evidence_group_count "
        "ORDER BY model_code, topic_code",
        {"run_id": run_id},
    )

    actual_nodes, node_metadata_issues = _canonical_actual_nodes(
        raw_node_rows,
        run_id=run_id,
    )
    actual_relationships, relationship_metadata_issues = (
        _canonical_actual_relationships(raw_relationship_rows, run_id=run_id)
    )
    expected_nodes = graph.canonical_nodes()
    expected_relationships = graph.canonical_relationships()
    expected_node_identities = [
        {"kind": row["kind"], "id": row["id"]} for row in expected_nodes
    ]
    actual_node_identities = [
        {"kind": row["kind"], "id": row["id"]} for row in actual_nodes
    ]
    relationship_identity_fields = (
        "source_kind",
        "source_id",
        "relationship",
        "target_kind",
        "target_id",
    )
    expected_relationship_identities = [
        {field: row[field] for field in relationship_identity_fields}
        for row in expected_relationships
    ]
    actual_relationship_identities = [
        {field: row[field] for field in relationship_identity_fields}
        for row in actual_relationships
    ]
    expected_snapshot = {
        "nodes": expected_nodes,
        "relationships": expected_relationships,
    }
    actual_snapshot = {
        "nodes": actual_nodes,
        "relationships": actual_relationships,
    }

    actual_node_counts = {
        label: sum(row["kind"] == label for row in actual_nodes)
        for label in NODE_LABELS
    }
    actual_relationship_counts = {
        relationship: sum(
            row["relationship"] == relationship for row in actual_relationships
        )
        for relationship in RELATIONSHIP_TYPES
    }
    expected_visual_rows = sorted(
        (
            {
                "model_code": edge.source_id,
                "topic_code": edge.target_id,
                "evidence_group_count": edge.properties["evidence_group_count"],
            }
            for edge in graph.edges
            if edge.relationship == "COVERS_TOPIC"
        ),
        key=lambda row: (row["model_code"], row["topic_code"]),
    )
    actual_visual_rows = sorted(
        visual_rows,
        key=lambda row: (str(row.get("model_code")), str(row.get("topic_code"))),
    )

    issues = [*node_metadata_issues, *relationship_metadata_issues]
    if actual_node_counts != graph.node_counts():
        issues.append("NODE_COUNT_MISMATCH")
    if actual_relationship_counts != graph.relationship_counts():
        issues.append("RELATIONSHIP_COUNT_MISMATCH")
    if _has_duplicate_identities(actual_nodes, ("kind", "id")):
        issues.append("DUPLICATE_NODE_IDENTITY")
    if _has_duplicate_identities(actual_relationships, relationship_identity_fields):
        issues.append("DUPLICATE_RELATIONSHIP_IDENTITY")
    if actual_node_identities != expected_node_identities:
        issues.append("NODE_IDENTITY_SET_MISMATCH")
    if actual_relationship_identities != expected_relationship_identities:
        issues.append("RELATIONSHIP_IDENTITY_SET_MISMATCH")
    if actual_snapshot != expected_snapshot:
        issues.append("GRAPH_SNAPSHOT_SHA256_MISMATCH")
    if cross_namespace_count != 0:
        issues.append("CROSS_NAMESPACE_RELATIONSHIP_PRESENT")
    if orphan_count != 0:
        issues.append("ORPHAN_CHUNK_PRESENT")
    if cross_model_count != 0:
        issues.append("CROSS_MODEL_PATH_PRESENT")
    if actual_visual_rows != expected_visual_rows:
        issues.append("VISUAL_SUMMARY_RESULT_SET_MISMATCH")

    visual_query_results: list[dict[str, Any]] = []
    visual_query_issues: list[str] = []
    for preset in build_visual_query_presets(graph):
        preset_rows = executor.query(preset.statement, {"run_id": run_id})
        expected_row_count = int(preset.expected_result["row_count"])
        actual_row_count = len(preset_rows)
        status = "PASS" if actual_row_count == expected_row_count else "FAIL"
        if status == "FAIL":
            issue = f"VISUAL_QUERY_ROW_COUNT_MISMATCH:{preset.query_id}"
            visual_query_issues.append(issue)
        visual_query_results.append(
            {
                "query_id": preset.query_id,
                "status": status,
                "expected_row_count": expected_row_count,
                "actual_row_count": actual_row_count,
            }
        )
    issues.extend(visual_query_issues)
    issues = list(dict.fromkeys(issues))

    return {
        "database_validation": "PASS" if not issues else "FAIL",
        "neo4j": {
            "name": str(kernel["name"]),
            "version": str(kernel["version"]),
            "edition": str(kernel["edition"]),
            "database": str(getattr(executor, "database", "neo4j")),
            "endpoint_class": str(
                getattr(executor, "endpoint_class", "TEST_EXECUTOR")
            ),
        },
        "node_counts": actual_node_counts,
        "relationship_counts": actual_relationship_counts,
        "graph_identity_validation": {
            "status": "PASS" if actual_snapshot == expected_snapshot else "FAIL",
            "nodes": {
                "expected_count": len(expected_nodes),
                "actual_count": len(actual_nodes),
                "expected_identity_sha256": canonical_json_sha256(
                    expected_node_identities
                ),
                "actual_identity_sha256": canonical_json_sha256(
                    actual_node_identities
                ),
                "expected_snapshot_sha256": canonical_json_sha256(expected_nodes),
                "actual_snapshot_sha256": canonical_json_sha256(actual_nodes),
                "match": actual_nodes == expected_nodes,
            },
            "relationships": {
                "expected_count": len(expected_relationships),
                "actual_count": len(actual_relationships),
                "expected_identity_sha256": canonical_json_sha256(
                    expected_relationship_identities
                ),
                "actual_identity_sha256": canonical_json_sha256(
                    actual_relationship_identities
                ),
                "expected_snapshot_sha256": canonical_json_sha256(
                    expected_relationships
                ),
                "actual_snapshot_sha256": canonical_json_sha256(
                    actual_relationships
                ),
                "match": actual_relationships == expected_relationships,
            },
            "snapshot": {
                "expected_sha256": canonical_json_sha256(expected_snapshot),
                "actual_sha256": canonical_json_sha256(actual_snapshot),
                "match": actual_snapshot == expected_snapshot,
            },
        },
        "orphan_chunk_count": orphan_count,
        "cross_model_path_count": cross_model_count,
        "cross_namespace_relationship_count": cross_namespace_count,
        "visual_summary": {
            "row_count": len(actual_visual_rows),
            "expected_result_set_sha256": canonical_json_sha256(
                expected_visual_rows
            ),
            "actual_result_set_sha256": canonical_json_sha256(actual_visual_rows),
            "match": actual_visual_rows == expected_visual_rows,
            "rows": actual_visual_rows,
        },
        "visual_query_validation": {
            "status": "PASS" if not visual_query_issues else "FAIL",
            "query_count": len(visual_query_results),
            "results": visual_query_results,
        },
        "issues": issues,
    }


def cleanup_graph_run(
    executor: Neo4jQueryExecutor,
    *,
    verification: _Neo4jTargetVerification,
    target_identity: Neo4jQaTargetIdentity | None = None,
) -> dict[str, Any]:
    """다른 namespace를 건드리지 않고 현재 run Graph만 정리·확인한다."""

    _assert_target_verification(executor, verification)
    run_id = _validated_run_id(verification.run_id)
    profile = verification.profile
    if profile == QA_EPHEMERAL_LOOPBACK_PROFILE:
        if (
            target_identity is None
            or target_identity.run_id != run_id
            or verification.expected_marker_sha256
            != canonical_json_sha256(target_identity.expected_marker())
        ):
            raise Neo4jEvidenceLineageError(
                "Neo4j QA 정리 대상 표식 capability가 일치하지 않습니다."
            )
    elif target_identity is not None:
        raise Neo4jEvidenceLineageError(
            "Neo4j LAB 정리에는 QA 대상 표식을 전달하지 않습니다."
        )
    cross_namespace_count = _single_int(
        executor.query(
            f"MATCH (node:{QA_NODE_LABEL} {{qa_run_id: $run_id}})-[rel]-(other) "
            f"WHERE NOT other:{QA_NODE_LABEL} "
            "OR coalesce(other.qa_run_id, '') <> $run_id "
            "RETURN count(DISTINCT rel) AS cross_namespace_relationship_count",
            {"run_id": run_id},
        ),
        "cross_namespace_relationship_count",
    )
    if cross_namespace_count != 0:
        raise Neo4jEvidenceLineageError(
            "Neo4j QA run 밖의 관계가 있어 자동 삭제를 거부합니다."
        )
    deleted_node_count = _single_int(
        executor.query(
            f"MATCH (node:{QA_NODE_LABEL} {{qa_run_id: $run_id}}) "
            "DETACH DELETE node RETURN count(node) AS deleted_node_count",
            {"run_id": run_id},
        ),
        "deleted_node_count",
    )
    residual_node_count = _single_int(
        executor.query(
            f"MATCH (node:{QA_NODE_LABEL} {{qa_run_id: $run_id}}) "
            "RETURN count(node) AS residual_node_count",
            {"run_id": run_id},
        ),
        "residual_node_count",
    )
    residual_relationship_count = _single_int(
        executor.query(
            "MATCH ()-[rel]->() WHERE rel.qa_run_id = $run_id "
            "RETURN count(rel) AS residual_relationship_count",
            {"run_id": run_id},
        ),
        "residual_relationship_count",
    )
    if profile == QA_EPHEMERAL_LOOPBACK_PROFILE:
        unexpected_node_statement = (
            f"MATCH (n) WHERE NOT n:{QA_TARGET_LABEL} "
            "RETURN count(n) AS unexpected_node_count"
        )
    else:
        unexpected_node_statement = (
            "MATCH (n) RETURN count(n) AS unexpected_node_count"
        )
    unexpected_node_count = _single_int(
        executor.query(unexpected_node_statement),
        "unexpected_node_count",
    )
    unexpected_relationship_count = _single_int(
        executor.query(
            "MATCH ()-[rel]->() RETURN count(rel) AS unexpected_relationship_count"
        ),
        "unexpected_relationship_count",
    )
    if target_identity is not None:
        marker_validated_after_cleanup = _qa_marker_matches(
            _query_qa_marker(executor),
            target_identity,
        )
    else:
        marker_validated_after_cleanup = True
    cleanup_status = (
        "PASS"
        if residual_node_count == 0
        and residual_relationship_count == 0
        and unexpected_node_count == 0
        and unexpected_relationship_count == 0
        and marker_validated_after_cleanup
        else "FAIL"
    )
    return {
        "status": cleanup_status,
        "scope": "QA_RUN_ONLY",
        "deleted_node_count": deleted_node_count,
        "residual_node_count": residual_node_count,
        "residual_relationship_count": residual_relationship_count,
        "unexpected_node_count_excluding_target_marker": unexpected_node_count,
        "unexpected_relationship_count": unexpected_relationship_count,
        "target_marker_validation": (
            "PASS" if marker_validated_after_cleanup else "FAIL"
        ),
        "container_cleanup": "NOT_RUN_INFRA_OWNED",
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
        'font-size="30" font-weight="700">Neo4j Evidence Lineage QA</text>',
        '<text x="70" y="96" fill="#93A4BA" font-family="Segoe UI, sans-serif" '
        'font-size="16">JSONL input · Query API validated · Production runtime disconnected</text>',
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
    f"MATCH (p:{QA_NODE_LABEL}:Product {{qa_run_id: $run_id}})"
    "-[r:COVERS_TOPIC {qa_run_id: $run_id}]->"
    f"(t:{QA_NODE_LABEL}:Topic {{qa_run_id: $run_id}}) "
    "RETURN p, r, t ORDER BY p.model_code, t.topic_code"
)


def build_visual_query_presets(
    graph: EvidenceLineageGraph,
) -> tuple[VisualQueryPreset, ...]:
    """개요·제품별 계보·안전·이상관계 시각 Query를 고정한다."""

    products = sorted(
        node.node_id for node in graph.nodes if node.label == "Product"
    )
    if not products:
        raise Neo4jEvidenceLineageError("시각 Query 대상 Product가 없습니다.")
    for model_code in products:
        if re.fullmatch(r"[A-Z0-9]+", model_code) is None:
            raise Neo4jEvidenceLineageError(
                "시각 Query의 제품 코드 형식이 올바르지 않습니다."
            )

    product_count = sum(node.label == "Product" for node in graph.nodes)
    topic_count = sum(node.label == "Topic" for node in graph.nodes)
    presets: list[VisualQueryPreset] = [
        VisualQueryPreset(
            query_id="product_topic_overview",
            title="Product to Evidence Topic Overview",
            purpose="제품별 공식 Evidence Topic 범위와 중첩을 확인한다.",
            statement=VISUAL_BROWSER_QUERY,
            expected_result={
                "node_count": product_count + topic_count,
                "relationship_count": graph.relationship_counts()[
                    "COVERS_TOPIC"
                ],
                "row_count": graph.relationship_counts()["COVERS_TOPIC"],
            },
        )
    ]
    for model_code in products:
        child_count = sum(
            node.label == "EvidenceChunk"
            and node.properties.get("model_code") == model_code
            for node in graph.nodes
        )
        evidence_group_count = sum(
            node.label == "EvidenceGroup"
            and node.properties.get("model_code") == model_code
            for node in graph.nodes
        )
        model_topic_count = sum(
            edge.relationship == "COVERS_TOPIC"
            and edge.source_id == model_code
            for edge in graph.edges
        )
        presets.append(
            VisualQueryPreset(
                query_id=f"product_lineage_{model_code.casefold()}",
                title=f"Evidence Lineage for {model_code}",
                purpose=(
                    "한 제품의 Document부터 Topic까지 정제된 Evidence 계보를 "
                    "드릴다운한다."
                ),
                statement=(
                    f"MATCH path=(p:{QA_NODE_LABEL}:Product "
                    f"{{qa_run_id: $run_id, model_code: '{model_code}'}})"
                    "-[:HAS_DOCUMENT]->(:Document)-[:HAS_PARENT_PAGE]->"
                    "(:ParentPage)-[:HAS_CHILD]->(:EvidenceChunk)"
                    "-[:MEMBER_OF]->(:EvidenceGroup)-[:ABOUT]->(:Topic) "
                    "WHERE all(node IN nodes(path) WHERE node.qa_run_id = $run_id) "
                    "AND all(rel IN relationships(path) WHERE rel.qa_run_id = $run_id) "
                    "RETURN path"
                ),
                expected_result={
                    "model_code": model_code,
                    "path_count": child_count,
                    "row_count": child_count,
                    "evidence_group_count": evidence_group_count,
                    "topic_count": model_topic_count,
                },
            )
        )

    consultation_group_ids = {
        node.node_id
        for node in graph.nodes
        if node.label == "EvidenceGroup"
        and node.properties.get("requires_consultation") is True
    }
    consultation_path_count = sum(
        edge.relationship == "MEMBER_OF"
        and edge.target_id in consultation_group_ids
        for edge in graph.edges
    )
    presets.extend(
        [
            VisualQueryPreset(
                query_id="consultation_required_lineage",
                title="Consultation Required Evidence Lineage",
                purpose=(
                    "상담이 필요한 Evidence Group의 제품별 계보가 유지되는지 "
                    "확인한다."
                ),
                statement=(
                    f"MATCH path=(p:{QA_NODE_LABEL}:Product "
                    "{qa_run_id: $run_id})-[:HAS_DOCUMENT]->(:Document)"
                    "-[:HAS_PARENT_PAGE]->(:ParentPage)-[:HAS_CHILD]->"
                    "(:EvidenceChunk)-[:MEMBER_OF]->"
                    "(g:EvidenceGroup)-[:ABOUT]->(:Topic) "
                    "WHERE g.requires_consultation = true "
                    "AND all(node IN nodes(path) WHERE node.qa_run_id = $run_id) "
                    "AND all(rel IN relationships(path) WHERE rel.qa_run_id = $run_id) "
                    "RETURN path"
                ),
                expected_result={
                    "evidence_group_count": len(consultation_group_ids),
                    "path_count": consultation_path_count,
                    "row_count": consultation_path_count,
                },
            ),
            VisualQueryPreset(
                query_id="integrity_anomalies",
                title="Evidence Lineage Integrity Anomalies",
                purpose=(
                    "고아 Chunk 또는 Parent·Evidence Group과 제품이 다른 관계를 "
                    "탐지한다."
                ),
                statement=(
                    f"MATCH (c:{QA_NODE_LABEL}:EvidenceChunk "
                    "{qa_run_id: $run_id}) "
                    f"OPTIONAL MATCH (parent:{QA_NODE_LABEL}:ParentPage "
                    "{qa_run_id: $run_id})"
                    "-[:HAS_CHILD {qa_run_id: $run_id}]->(c) "
                    "OPTIONAL MATCH (c)-[:MEMBER_OF {qa_run_id: $run_id}]->"
                    f"(group:{QA_NODE_LABEL}:EvidenceGroup "
                    "{qa_run_id: $run_id}) "
                    "WITH c, parent, group "
                    "WHERE parent IS NULL OR group IS NULL "
                    "OR c.model_code <> parent.model_code "
                    "OR c.model_code <> group.model_code "
                    "RETURN c, parent, group"
                ),
                expected_result={"row_count": 0},
            ),
        ]
    )
    return tuple(presets)


def render_visual_query_bundle(
    presets: tuple[VisualQueryPreset, ...],
    *,
    run_id: str | None = None,
) -> str:
    """Neo4j Browser에 하나씩 붙여 넣을 수 있는 정제 Query Bundle."""

    if not presets:
        raise Neo4jEvidenceLineageError("시각 Query Preset이 없습니다.")
    lines = [
        "// Neo4j Evidence Lineage Visual Validation",
        "// JSONL_BASED_LINEAGE_QA / production runtime disconnected",
        "",
    ]
    if run_id is not None:
        lines.extend([f":param run_id => '{_validated_run_id(run_id)}';", ""])
    for preset in presets:
        lines.extend(
            [
                f"// [{preset.query_id}] {preset.title}",
                f"// Purpose: {preset.purpose}",
                "// Expected: "
                + json.dumps(
                    dict(preset.expected_result),
                    ensure_ascii=True,
                    sort_keys=True,
                ),
                preset.statement.rstrip(";") + ";",
                "",
            ]
        )
    return "\n".join(lines)


__all__ = [
    "DEFAULT_CHILD_CHUNKS_PATH",
    "DEFAULT_EVIDENCE_GROUPS_PATH",
    "DEFAULT_PARENT_PAGES_PATH",
    "EvidenceLineageGraph",
    "GraphEdge",
    "GraphNode",
    "LAB_LOOPBACK_PROFILE",
    "Neo4jEvidenceLineageError",
    "Neo4jHttpQueryClient",
    "Neo4jQaTargetIdentity",
    "Neo4jQueryExecutor",
    "QA_EPHEMERAL_LOOPBACK_PROFILE",
    "VISUAL_BROWSER_QUERY",
    "VisualQueryPreset",
    "build_evidence_lineage_graph",
    "build_visual_query_presets",
    "canonical_json_sha256",
    "cleanup_graph_run",
    "load_graph_into_neo4j",
    "preflight_neo4j_target",
    "render_lineage_svg",
    "render_visual_query_bundle",
    "verify_graph_in_neo4j",
]
