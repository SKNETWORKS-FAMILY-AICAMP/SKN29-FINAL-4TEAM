# E12 — Neo4j Evidence Lineage / Knowledge Relationship Validation

- Status: **E12_COMPLETE**
- Git SHA: `55bbc96057e46ebbf11d165da25c63fd6cde61a0`
- Run ID: `e12-20260830T053107Z-55bbc960-dc0e010f`
- Neo4j image digest: `sha256:dbc377fb9cd8fe8dabc19d3041b197d5ca0ef8bae514cea175b8df265e5b7a76`
- Scope: `JSONL_BASED_LINEAGE_QA`
- Production retrieval: **UNCHANGED_PGVECTOR**
- Production runtime connected: **False**
- GraphRAG claim: **Not applicable / not claimed**

## E12-01 Projection Fidelity

- Input contract: 15 Parent / 53 Child / 43 Evidence Group
- Canonical node snapshot match: `True`
- Canonical relationship snapshot match: `True`
- Full graph snapshot match: `True`

## E12-02 Lineage Traversal / Visual Query Validation

- Visual query validation: `PASS`
- Visual query count: `6`
- Normal orphan chunk count: `0`
- Normal cross-model path count: `0`

## E12-03 Controlled Fault Injection

### E12-03A — ORPHAN_CHUNK_RELATIONSHIP

- Detected: `True`
- Corrupted DB validation: `FAIL`
- Relationship count before/after: `210 / 209`
- Detector issues: `RELATIONSHIP_COUNT_MISMATCH`, `RELATIONSHIP_IDENTITY_SET_MISMATCH`, `GRAPH_SNAPSHOT_SHA256_MISMATCH`, `ORPHAN_CHUNK_PRESENT`, `VISUAL_QUERY_ROW_COUNT_MISMATCH:product_lineage_wpuiac425snw`, `VISUAL_QUERY_ROW_COUNT_MISMATCH:consultation_required_lineage`, `VISUAL_QUERY_ROW_COUNT_MISMATCH:integrity_anomalies`

### E12-03B — CROSS_MODEL_RELATIONSHIP

- Detected: `True`
- Corrupted DB validation: `FAIL`
- Relationship count before/after: `210 / 210`
- Detector issues: `RELATIONSHIP_IDENTITY_SET_MISMATCH`, `GRAPH_SNAPSHOT_SHA256_MISMATCH`, `CROSS_MODEL_PATH_PRESENT`

## E12-04 Isolation / Cleanup

- Application graph cleanup: `PASS`
- Disposable container count after cleanup: `0`
- Anonymous volume count after cleanup: `0`

## Claim Boundary

Neo4j는 RAG 검색 엔진이나 GraphRAG로 사용하지 않았다. Repository JSONL에서 검증된 Evidence 관계 Metadata만 일회성 Neo4j QA Graph로 투영하여 Product → Document → ParentPage → EvidenceChunk → EvidenceGroup → Topic 계보와 관계 정합성을 검증했다.

공식 qa_ephemeral runner의 `PARTIAL / HOLD_PENDING_INFRA_FINALIZATION` 상태는 그대로 보존한다. E12_COMPLETE는 로컬 일회성 실험 검증 완료를 뜻하며 Production Deployment 증거를 뜻하지 않는다.

## Presentation-ready Result

pgvector가 검색할 근거를 담당하는 동안, Neo4j에는 근거 본문·Embedding·Prompt를 저장하지 않고 관계 Metadata만 투영했다. 원본 JSONL과 실제 Neo4j의 Node·Relationship Snapshot이 일치했고, Orphan Chunk와 Cross-model 관계를 의도적으로 주입했을 때 정합성 검증이 이를 탐지했다.
