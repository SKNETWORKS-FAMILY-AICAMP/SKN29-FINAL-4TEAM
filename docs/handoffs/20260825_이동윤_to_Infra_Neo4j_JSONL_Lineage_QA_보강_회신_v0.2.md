# Neo4j JSONL Lineage QA 보강 회신 v0.2

- 작성자: 이동윤
- 수신: Infra
- 기준일: 2026-08-25
- 현재 기준: branch `dongyoon`, base HEAD `427f42b3f5e0bec07dcc14b209975b70808ba5c6`, Dirty 보강 중

## 결론

Infra 검토 5개 항목을 반영했다. 이번 Job은 **저장소 JSONL 3종 기반 계보 QA**이며,
RDS·pgvector·운영 Pipeline에는 연결하지 않는다. 공용·외부 Neo4j Endpoint도
지원하지 않고, 같은 Job/Pod의 인증된 전용 일회성 Container와 Loopback 연결만
허용한다.

## AI 영역 반영 내용

1. 실제 Node 142개와 Relationship 210개의 Domain ID·허용 속성을 Projection과
   전수 비교하고, Node·Relationship·전체 Snapshot의 canonical SHA-256을 각각
   기대값/실제값으로 기록한다.
2. 같은 건수를 유지하면서 `HAS_PARENT_PAGE`, `ABOUT`, `COVERS_TOPIC`의 대상을
   바꾼 Unit 및 실제 Neo4j 오류 주입 테스트를 추가했다. 세 경우 모두
   `RELATIONSHIP_IDENTITY_SET_MISMATCH`와
   `GRAPH_SNAPSHOT_SHA256_MISMATCH`로 FAIL한다.
3. `MATCH (n) DETACH DELETE n`, 전역 Constraint, `MERGE`를 제거했다. 모든 QA
   Node·Relationship에 `qa_run_id`를 붙이고, 정리도 현재 run의
   `:WaterbridgeQaLineage` Node만 대상으로 한다. run 밖 관계가 있으면 삭제하지
   않고 fail-closed한다.
4. `lab_loopback`과 `qa_ephemeral_loopback`을 분리했다. QA Profile은 Basic 인증과
   Infra가 독립 생성한 `:WaterbridgeQaTarget` 표식이 모두 맞아야 첫 쓰기를
   허용한다. non-loopback, URL Credential, 다른 Database는 거부한다.
5. 영구 Artifact에는 전체 `graph_projection.json`을 제외하고 Evidence, SVG,
   Query Catalog/Bundle, Projection Manifest, Graph Cleanup Evidence, Run Manifest,
   파일별 SHA-256 Manifest와 `checksums.sha256`만 포함한다.

관련 구현 경로:

- `ai/app/experiments/neo4j_evidence_lineage.py`
- `ai/scripts/run_neo4j_evidence_lineage_lab.py`
- `ai/tests/unit/test_neo4j_evidence_lineage_experiment_v0.py`
- `ai/tests/integration/test_neo4j_evidence_lineage_runtime.py`

## Infra에 요청하는 QA Job 구성

1. Neo4j `neo4j:2026.07.1`을 볼륨 없는 전용 일회성 Container/Sidecar로 실행하고
   Query API는 같은 Job의 Loopback에만 노출해 달라.
2. 인증을 활성화하고 다음 값은 CI Secret/실행 변수로만 주입해 달라. 값은 로그와
   Artifact에 출력하지 않는다.
   - `NEO4J_QA_USERNAME`
   - `NEO4J_QA_PASSWORD`
   - `NEO4J_QA_TARGET_ID`
   - `NEO4J_QA_TARGET_NONCE_SHA256`
   - `NEO4J_QA_IMAGE_DIGEST`
   - `NEO4J_QA_RUN_ID`
   - `NEO4J_QA_ENDPOINT` (`http://127.0.0.1:<ephemeral-port>`)
3. AI 실행 전에 Infra 초기화 단계가 `:WaterbridgeQaTarget` Node를 정확히 1개
   생성해 달라. 속성은 `target_id`, `run_id`, `nonce_sha256`, `database=neo4j`,
   실제 이미지 `image_digest`다. AI 코드가 이 Marker를 스스로 만들지는 않는다.
4. 아래 두 실행을 같은 SHA·run_id에서 수행해 달라.
   - 실제 오류 관계 통합 테스트:
     `AI_NEO4J_LINEAGE_E2E=1` 상태에서
     `python -m pytest ai/tests/integration/test_neo4j_evidence_lineage_runtime.py -q`
   - 정상 증거 생성:
     `python -m ai.scripts.run_neo4j_evidence_lineage_lab`에
     `--profile qa_ephemeral_loopback`, `--run-id`, `--endpoint`,
     `--neo4j-image-digest`를 전달
5. Job Artifact로 다음 파일을 업로드해 달라.
   - `run_manifest.json`
   - `neo4j_lab_evidence.json`
   - `neo4j_evidence_lineage_visual.svg`
   - `visual_query_catalog.json`
   - `neo4j_browser_visual_query.cypher`
   - `projection_manifest.json`
   - `cleanup_evidence.json`
   - `artifact_manifest.json`
   - `checksums.sha256`
6. `always()`에서 해당 run label의 Container와 익명 Volume만 제거하고,
   Container 0·Volume 0 결과와 실제 이미지 Repo Digest를 CI 실행 로그/별도 Infra
   Cleanup 증거에 남겨 달라. 애플리케이션 Evidence의 Graph 정리 PASS가 Container
   제거까지 증명하지는 않는다.
7. 정리 완료 후 `infra_cleanup_evidence.json`과 외부
   `submission_manifest.json`·`submission_checksums.sha256`을 생성해 달라. 외부
   Submission Manifest에는 CI Run ID/로그 참조, 실제 Repo Digest, Container·
   Volume 0, Clean Git SHA 및 AI `artifact_manifest.json`의 파일 SHA-256을
   결합한다. AI Runner 단독 결과는 `HOLD_PENDING_INFRA_FINALIZATION`이며 이 외부
   묶음 전에는 PM 제출 READY로 승격하지 않는다.

### Runner 종료 코드와 CI 처리

- `0`: `lab_loopback` 애플리케이션 PASS. 배포 증거는 아님
- `1`: Application·Graph Cleanup·Git provenance 중 하나가 FAIL
- `2`: Application PASS지만 Clean Commit 또는 Infra Finalization 대기

QA 정상 경로도 외부 Finalization 전에는 의도적으로 `2`를 반환한다. 따라서 Runner
Step은 종료 코드를 별도로 보존한 뒤 `0/2`만 후속 처리 허용 대상으로 삼거나
`continue-on-error`로 실행하고, Artifact Upload·Container Cleanup·외부 Finalizer는
`if: always()`에서 수행해 달라. 단, `1` 또는 Evidence의
`application_validation!=PASS`를 최종 Job이 성공으로 숨기면 안 된다. 최종 성공
여부는 외부 `submission_manifest.json` 검증 단계가 결정한다.

## Trigger와 RDS 범위

이번 Job Trigger는 JSONL 3종, Projection/Query/Runner, Neo4j QA 설정 변경 및
수동 Release Candidate 실행으로 제한한다. `RDS Lineage View 변경`은 제외한다.

현재 PASS는 JSONL Projection 계보 정합성만 증명한다. 팀 RDS Import·Crosswalk·
Readonly View, 모델별 `15/19/19`, Retrieval 50 Case를 증명하지 않는다. RDS 준비
후 Backend/DB가 승인한 Readonly View 계약을 입력으로 하는 별도
`RDS Lineage QA` Gate를 설계한다.

별도 내부 Network Service가 꼭 필요해질 경우에만 HTTPS, 인증서 검증, 정확한
Hostname Allowlist, CA 전달 계약을 갖춘 세 번째 Profile을 별도 승인받는다.
현재 코드는 non-loopback Endpoint를 명시적으로 거부한다.

## 현재 실행 증거 상태

- Neo4j 계보·보안 표적 Unit: `18 passed` — PASS
- Runner Artifact·Git 계보 표적 Unit: `4 passed` — PASS
- 실제 인증 Neo4j 오류 관계 통합: `3 passed` — PASS
- 정상 실제 Graph ID·Snapshot 검증: PASS
- run 범위 Graph 정리: PASS
- Container·Volume 정식 정리 증거: `NOT_RUN` — Infra `always()` 및 외부
  Submission Manifest 대기
- 로컬 후보 증거:
  `.runtime/neo4j_evidence_lineage_v0_4/neo4j-qa-ef9ac8f8b81b/`

위 로컬 실행에서 운영자 확인 기준 신규 Container·익명 Volume 잔존은 0건이었지만,
이는 AI Artifact checksum에 포함된 Infra 증거가 아니므로 정식 상태는 `NOT_RUN`으로
유지한다. 또한 해당 실행은 보강 중인 Dirty Worktree의 중간 후보라 최종 판정이
`PARTIAL`이다. 코드 Commit 후 Infra Job의 Clean HEAD에서 같은 묶음을 재생성하고
외부 Submission Manifest까지 생성해야 정식 QA Artifact로 제출할 수 있다.

## Infra 반영 상태 — 김은진, 2026-08-25

- 상태: `WORKFLOW_IMPLEMENTED / ACTUAL_GITHUB_RUN_NOT_RUN`
- 운영 배포와 분리된 수동 `workflow_dispatch` 전용 Workflow로 반영했다.
- Job마다 임시 Basic 인증값과 Target Marker를 생성하므로 Repository Secret의
  실제 값을 추가하거나 문서화하지 않는다.
- Neo4j는 Digest를 확인한 뒤 Loopback 임시 Port에만 연결하는 `--rm` Container로
  실행하며 운영 Compose 4개 Service에는 추가하지 않는다.
- 동일 Job에서 실제 오류 관계 통합 3건과 정상 Runner를 실행하고, Runner 종료 코드
  `2`만 Infra Finalization 대상으로 허용한다.
- `always()` 단계가 정확한 QA Container와 해당 Container의 익명 Volume만 정리하고
  Container·Volume `0/0`을 검증한다.
- AI Artifact의 파일별 SHA-256, Application·Git·Graph Cleanup PASS와 Infra Cleanup
  PASS가 모두 확인된 경우에만 외부 Submission Manifest를 생성한다.
- 구현 파일:
  - `.github/workflows/neo4j-lineage-qa.yml`
  - `scripts/deployment/prepare_neo4j_lineage_qa.py`
  - `scripts/deployment/finalize_neo4j_lineage_qa.py`
  - `tests/deployment/test_neo4j_lineage_qa_assets.py`
- 로컬 정적·회귀 검증:
  - Neo4j Infra Asset 표적: `6 passed`
  - 전체 Deployment Test: `19 passed`
  - Neo4j·Runner AI Unit: `22 passed`
- GitHub-hosted Runner의 실제 Container 실행과 외부 Artifact 생성은 아직 실행하지
  않았으므로 정식 상태는 계속 `NOT_RUN`이다. Workflow Dispatch 성공 Run이 생성된
  뒤에만 `VERIFIED` 또는 제출 `READY`로 승격한다.
