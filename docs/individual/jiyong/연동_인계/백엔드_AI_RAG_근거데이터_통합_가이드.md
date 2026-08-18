# 백엔드·AI RAG 근거데이터 통합 가이드

> 관련 업무: Canonical Evidence·Crosswalk·Readonly View·Verifier·T-028B
> 최신 반영일: 2026-08-17
> 원칙: Backend 공식 문서·Chunk가 근거 데이터의 SSOT다.

## 1. 식별자 계약

AI는 Canonical `chunk_id`를 반환한다. Backend는 승인된 1:1 Crosswalk로
`knowledge_document_chunk.public_id`를 찾아 검증·저장한다. 고객 공개 DTO에는
`public_id`만 사용하고 내부 Chunk ID·경로·원문 전체를 노출하지 않는다.

## 2. 주요 경로

- `ai/configs/canonical_evidence_identity.json`
- `backend/apps/evidence/**`
- `backend/apps/evidence/migrations/**`
- `backend/apps/evidence/management/commands/**`
- `backend/integrations/ai/response_mapper.py`
- `scripts/database/audit_backend_ai_g1b_readiness.py`
- `backend/tests/unit/database/test_backend_ai_g1b_readiness.py`
- `backend/tests/integration/database/test_team_integration_roles_postgresql.py`

## 3. Import·Crosswalk

1. Canonical Identity·Hash·Index Version 검증
2. Source Document·Page·Chunk·Embedding Scope 검증
3. Dry-run에서 쓰기 0 확인
4. 승인 Fixture Apply
5. 동일 입력 Replay 비의도 변경 0 확인
6. Stale·Rogue Mapping 비활성화
7. 공식 Crosswalk 수량과 1:1 관계 확인

## 4. Readonly View

AI 검색 View는 승인 상태·완료 Ingestion·DQ·유효기간·Superseded·Embedding
Revision을 Fail-closed로 필터링한다. AI Role은 View SELECT만 허용한다.

View Metadata에는 검색·검증에 필요한 문서 제목, 모델, 세대, 페이지,
검증 상태, 허용 용도, Source Hash, Embedding Model·Revision, Index Version을
포함한다.

## 5. Evidence Verifier

Verifier는 다음을 확인한 뒤에만 EvidenceLink를 저장한다.

- Canonical ID ↔ Public UUID 1:1
- Document·Page·Chunk 활성·승인 상태
- Model·Generation·Allowed Use 일치
- Source Hash·Index Version·Embedding Revision 일치
- 중복·알 수 없는 Chunk 거부

검증 예외는 Fail-closed Fallback으로 처리하고 미검증 Evidence를 공개하지 않는다.

## 6. Safety Guard

Safety Rule ID는 공유 계약 Registry의 값만 허용한다. LLM 판단만으로 위험 전이를
적용하지 않고 Backend가 최신 State·Version·Rule Allowlist를 재검증한다.

## 7. 실행 Gate

| Gate | 성공 조건 |
| --- | --- |
| Fixture | 승인 Identity·Hash·Version 일치 |
| Import | Dry-run·Apply·Replay PASS |
| Crosswalk | 승인 건수 1:1 |
| View | 예상 Column·Row와 필터 정합 |
| Role | View SELECT만 허용 |
| Verifier | 미확정·변조 Evidence 차단 |
| Local RAG | 실제 pgvector 검색과 Backend 저장 |

## 8. T-028B 안전 Projection 준비 골격

현재 구현은 승인 전 내부 후보 생성과 거부 검증까지만 담당한다. 공개 API·Serializer·
URL·OpenAPI DTO는 연결하지 않았고 `projection_status=PREPARATION_ONLY`를 강제한다.
호출자는 먼저 해당 문의에 대한 Actor 권한을 검증해야 한다.

### 내부 최소 후보

- 대상 역할: CUSTOMER·CONSULTANT·TECHNICIAN
- 세 역할 모두 동일한 최소 필드만 사용
- 검증 완료된 `EvidenceLink`와 저장 당시 불변 Snapshot만 조회
- Evidence UUID, 문서 코드·제목·Revision·기관·HTTPS 공식 URL
- 페이지·Section, 근거 요약, 제품 모델 코드, 검증 여부
- 미검증 Link, 미지원 역할, 누락·추가 필드, 비 HTTPS URL은 즉시 차단

### 명시적 비공개 필드

- AI Run·Retrieval Run·Hit·내부 `chunk_id`
- 인용 원문·수동 추출 원문·검색 Query·Prompt
- 유사도·Vector 점수와 내부 검증자 식별자
- Source Hash·로컬/스토리지 경로·원본 URI
- 승인되지 않은 위험도·행동·공개 상태 확장

### Readiness 경계

- Repository·Service·Validator만 구현된 현재 상태는
  `EVIDENCE_PUBLIC_RUNTIME_INCOMPLETE`다.
- 빈 `contracts/api/paths/evidence.yaml`은 그대로 유지한다.
- 공개 DTO는 PM·소비자 합의와 T-028A 완료 전 임의 확정하지 않는다.
- 기존 고객 Guidance의 `evidence: []` 경계는 유지한다.

### 자체 검증

- 안전 Projection·거부 표적: `17 passed / 0 failed`
- 검증된 Snapshot의 세 역할 동일 최소 출력 확인
- 미검증 Evidence와 금지 필드의 중첩 삽입도 Fail-closed 확인
- 공개 API 파일 미구현과 Readiness HOLD 확인
- `--require-runtime-ready`는 열린 Gate 4건을 보고하고 Exit 2로 차단

관련 구현:

- `backend/apps/evidence/repositories/evidence_repository.py`
- `backend/apps/evidence/services/evidence_card_service.py`
- `backend/apps/evidence/services/evidence_validation_service.py`
- `backend/tests/unit/evidence/test_t028b_safe_projection.py`

## 9. 금지사항

- AI Readonly DSN으로 Index Build·UPSERT 실행
- 개인 DB의 `ai_rag_chunks`를 팀 정본으로 승격
- 내부 Chunk ID·원문·파일 경로 공개
- Unit Readiness를 실제 pgvector·LLM E2E PASS로 확대

## 10. 판정

Import·Crosswalk·View·Role·Verifier는 Backend G1-B 준비를 증명한다. 실제
AI Retrieval·Provider·Backend 저장과 독립 QA가 통과해야 통합 Gate가 닫힌다.

T-028B는 내부 안전 후보와 Failing Test를 구현한 상태다. 공개 DTO 승인·소비자 연결·
독립 QA 전에는 Public Runtime 또는 전체 WBS 완료로 판정하지 않는다.
