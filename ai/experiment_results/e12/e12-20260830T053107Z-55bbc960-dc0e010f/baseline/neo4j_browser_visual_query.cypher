// Neo4j Evidence Lineage Visual Validation
// JSONL_BASED_LINEAGE_QA / production runtime disconnected

:param run_id => 'e12-20260830T053107Z-55bbc960-dc0e010f';

// [product_topic_overview] Product to Evidence Topic Overview
// Purpose: 제품별 공식 Evidence Topic 범위와 중첩을 확인한다.
// Expected: {"node_count": 28, "relationship_count": 43, "row_count": 43}
MATCH (p:WaterbridgeQaLineage:Product {qa_run_id: $run_id})-[r:COVERS_TOPIC {qa_run_id: $run_id}]->(t:WaterbridgeQaLineage:Topic {qa_run_id: $run_id}) RETURN p, r, t ORDER BY p.model_code, t.topic_code;

// [product_lineage_wpuiac425snw] Evidence Lineage for WPUIAC425SNW
// Purpose: 한 제품의 Document부터 Topic까지 정제된 Evidence 계보를 드릴다운한다.
// Expected: {"evidence_group_count": 18, "model_code": "WPUIAC425SNW", "path_count": 19, "row_count": 19, "topic_count": 18}
MATCH path=(p:WaterbridgeQaLineage:Product {qa_run_id: $run_id, model_code: 'WPUIAC425SNW'})-[:HAS_DOCUMENT]->(:Document)-[:HAS_PARENT_PAGE]->(:ParentPage)-[:HAS_CHILD]->(:EvidenceChunk)-[:MEMBER_OF]->(:EvidenceGroup)-[:ABOUT]->(:Topic) WHERE all(node IN nodes(path) WHERE node.qa_run_id = $run_id) AND all(rel IN relationships(path) WHERE rel.qa_run_id = $run_id) RETURN path;

// [product_lineage_wpuiac606snw] Evidence Lineage for WPUIAC606SNW
// Purpose: 한 제품의 Document부터 Topic까지 정제된 Evidence 계보를 드릴다운한다.
// Expected: {"evidence_group_count": 18, "model_code": "WPUIAC606SNW", "path_count": 19, "row_count": 19, "topic_count": 18}
MATCH path=(p:WaterbridgeQaLineage:Product {qa_run_id: $run_id, model_code: 'WPUIAC606SNW'})-[:HAS_DOCUMENT]->(:Document)-[:HAS_PARENT_PAGE]->(:ParentPage)-[:HAS_CHILD]->(:EvidenceChunk)-[:MEMBER_OF]->(:EvidenceGroup)-[:ABOUT]->(:Topic) WHERE all(node IN nodes(path) WHERE node.qa_run_id = $run_id) AND all(rel IN relationships(path) WHERE rel.qa_run_id = $run_id) RETURN path;

// [product_lineage_wpujac104dwh] Evidence Lineage for WPUJAC104DWH
// Purpose: 한 제품의 Document부터 Topic까지 정제된 Evidence 계보를 드릴다운한다.
// Expected: {"evidence_group_count": 7, "model_code": "WPUJAC104DWH", "path_count": 15, "row_count": 15, "topic_count": 7}
MATCH path=(p:WaterbridgeQaLineage:Product {qa_run_id: $run_id, model_code: 'WPUJAC104DWH'})-[:HAS_DOCUMENT]->(:Document)-[:HAS_PARENT_PAGE]->(:ParentPage)-[:HAS_CHILD]->(:EvidenceChunk)-[:MEMBER_OF]->(:EvidenceGroup)-[:ABOUT]->(:Topic) WHERE all(node IN nodes(path) WHERE node.qa_run_id = $run_id) AND all(rel IN relationships(path) WHERE rel.qa_run_id = $run_id) RETURN path;

// [consultation_required_lineage] Consultation Required Evidence Lineage
// Purpose: 상담이 필요한 Evidence Group의 제품별 계보가 유지되는지 확인한다.
// Expected: {"evidence_group_count": 25, "path_count": 35, "row_count": 35}
MATCH path=(p:WaterbridgeQaLineage:Product {qa_run_id: $run_id})-[:HAS_DOCUMENT]->(:Document)-[:HAS_PARENT_PAGE]->(:ParentPage)-[:HAS_CHILD]->(:EvidenceChunk)-[:MEMBER_OF]->(g:EvidenceGroup)-[:ABOUT]->(:Topic) WHERE g.requires_consultation = true AND all(node IN nodes(path) WHERE node.qa_run_id = $run_id) AND all(rel IN relationships(path) WHERE rel.qa_run_id = $run_id) RETURN path;

// [integrity_anomalies] Evidence Lineage Integrity Anomalies
// Purpose: 고아 Chunk 또는 Parent·Evidence Group과 제품이 다른 관계를 탐지한다.
// Expected: {"row_count": 0}
MATCH (c:WaterbridgeQaLineage:EvidenceChunk {qa_run_id: $run_id}) OPTIONAL MATCH (parent:WaterbridgeQaLineage:ParentPage {qa_run_id: $run_id})-[:HAS_CHILD {qa_run_id: $run_id}]->(c) OPTIONAL MATCH (c)-[:MEMBER_OF {qa_run_id: $run_id}]->(group:WaterbridgeQaLineage:EvidenceGroup {qa_run_id: $run_id}) WITH c, parent, group WHERE parent IS NULL OR group IS NULL OR c.model_code <> parent.model_code OR c.model_code <> group.model_code RETURN c, parent, group;
