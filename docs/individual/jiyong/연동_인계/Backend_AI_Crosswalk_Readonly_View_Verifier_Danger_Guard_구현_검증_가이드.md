# Backend·AI Crosswalk·Readonly View·Verifier 구현·검증 가이드

> 최신 검증: 2026-08-13 KST
> 작성 책임: 최지용 — Backend·Database
> 기준: `main@1289d4b3673d9b061833fa94d45096bde1541a02`에서 만든 로컬 후보
> 상태: `AUTHOR_VERIFIED / POSTGRESQL_TEAM_QA_PENDING / JOINT_E2E_HOLD`

## 1. 결론

Backend 단독 범위로 다음을 구현·검증했다.

1. AI Canonical `chunk_id`와 Backend `DocumentChunk`의 검증된 Crosswalk
2. AI가 읽을 PostgreSQL `backend_ai_rag_chunks_v1` View
3. BGE-M3 1024차원·고정 Revision·Exact Search·승인 7건 검증
4. AI Evidence Reference의 all-or-none 검증과 Public UUID 변환
5. 검증 Evidence를 `Guidance`·`AIRun`·`DocumentChunk`에 연결하는 `EvidenceLink` 저장
6. AI 전용 Role이 해당 View만 조회하도록 하는 최소권한 Provisioning
7. Provider·Model·Prompt 등 AIRun Runtime Identity 저장 증거

고객 Guidance/Public Evidence API는 구현하지 않았다. 현재 Evidence Path·Schema가
준비 상태이고 고객 Snapshot 계약에 해당 필드가 없으므로 계약 Owner 결정이 먼저다.

## 2. 책임과 ID 경계

| 항목 | 정본·책임 |
| --- | --- |
| 공식 문서·Page·Chunk·Embedding | Backend `knowledge_*` 테이블 |
| AI 검색 ID | AI Canonical `chunk_id` |
| Backend 저장 ID | `DocumentChunk.public_id` UUID |
| Crosswalk·View·Verifier·EvidenceLink | 최지용 |
| View Adapter·실제 RAG·LLM | 이동윤 |
| 공용 PostgreSQL·Role 독립 검증 | 김은진 |
| Public Guidance/Evidence 계약 | PM·계약 Owner |

내부 PK, Canonical ID, Vector, 서버 경로, 원문 전체는 고객 DTO로 내보내지 않는다.

## 3. Crosswalk·Migration

- [`AIChunkCrosswalk`](../../../../backend/apps/evidence/models/ai_chunk_crosswalk.py):
  Canonical ID와 Backend Chunk의 1:1 매핑
- [`evidence.0009`](../../../../backend/apps/evidence/migrations/0009_ai_chunk_crosswalk.py):
  Crosswalk·Page 순서·Constraint·Index
- [`evidence.0010`](../../../../backend/apps/evidence/migrations/0010_backend_ai_rag_chunks_view.py):
  PostgreSQL 보안 경계 View

View 제공 필드는 다음 8개뿐이다.

```text
chunk_id, metadata, content, embedding,
model_code, product_generation, verification_status, allowed_use
```

View는 활성·검증 Crosswalk, 승인 MVP 문서·Page·모델 Scope, 활성 Embedding,
미해결 Data Quality Issue 0건을 모두 만족할 때만 행을 제공한다.

## 4. 승인 7건 동기화

[`sync_ai_canonical_crosswalk`](../../../../backend/apps/evidence/management/commands/sync_ai_canonical_crosswalk.py)는
다음을 fail-closed로 검증한다.

- 정확히 7개 Canonical Chunk와 중복 0건
- `BAAI/bge-m3`
- Revision `5617a9f61b028005a4858fdac845db406aefb181`
- 1024차원, `exact_search`
- Manifest·Document·Chunk-set Hash
- 공식 문서·Page·제품 세대·Chunk·Embedding 일치
- 승인된 비어 있지 않은 `evidence_summary`
- 미해결 Data Quality Issue 0건

```powershell
Set-Location C:\python-src\Final_PROJECT\SKN29-FINAL-4TEAM\backend
\.venv\Scripts\python.exe manage.py sync_ai_canonical_crosswalk `
  --settings=config.settings.local
```

실제 적용은 활성 합성 Operator와 `--apply --verified-by`가 필요하며 한 Transaction과
PostgreSQL Advisory Lock으로 처리한다. 공식 Backend Evidence 7건이 적재되지 않은 DB에서
Dry-run/Apply를 PASS로 기록하면 안 된다.

## 5. Runtime Verifier와 EvidenceLink

[`EvidenceReferenceVerifier`](../../../../backend/apps/evidence/services/evidence_reference_verifier.py)는
AI 응답 전체를 all-or-none으로 확인한다.

- 모든 Canonical ID가 활성·검증 Crosswalk에 존재
- 한 응답 안의 Manifest·Chunk-set·Index·Embedding Identity가 하나로 일치
- 문서·Revision·Page·제품·Hash·Embedding·DQ 상태 일치
- AI Reference 상태가 `official_verified`

성공 시 Backend Public UUID만 반환한다. 실패·혼합·예외는 빈 목록으로 닫는다.

[`InquiryAIService`](../../../../backend/apps/inquiries/services/inquiry_ai_service.py)는
기본 Verifier를 자동 사용한다. 검증 성공 시 `EvidenceLink`에 다음 Snapshot을 저장한다.

- Inquiry, Guidance, AIRun, DocumentChunk
- 문서 코드·제목·기관·Revision·공식 URL·SHA-256
- 승인 `evidence_summary`, 인용 Chunk 원문, Page, Section, 제품 코드
- 검증자와 검증 시각

검증 또는 Link 저장 실패 시 Assessment·Guidance 초안은 보존하되 다음처럼 처리한다.

```text
EvidenceLink=0
Inquiry.evidence_ids=[]
requires_fallback=true
SAFE_GUIDANCE_READY 미적용
```

Replay는 기존 AIRun 결과를 반환하므로 Guidance·EvidenceLink를 추가 생성하지 않는다.

## 6. AI 전용 Readonly Role

[`provision_team_integration.py`](../../../../scripts/database/provision_team_integration.py)는
`waterbridge_ti_ai_readonly`의 전체 Table·Sequence 권한을 회수한 뒤,
View가 존재할 때만 `public.backend_ai_rag_chunks_v1`의 `SELECT`를 부여한다.

| 대상 | AI Role |
| --- | --- |
| View SELECT | 허용 |
| View INSERT/UPDATE/DELETE/TRUNCATE | 거부 |
| Base Table SELECT·DML | 거부 |
| Sequence | 거부 |
| Schema CREATE·DDL | 거부 |
| 기본 Transaction | Read only |

Migration 전 최초 Provisioning은 View가 없어도 실패하지 않는다. Migration 후 Provisioning을
다시 실행하고 PostgreSQL Role Test로 실제 권한을 확인해야 한다.

## 7. AIRun Identity

Backend는 다음 설정을 AIRun에 저장한다.

```text
AI_MODEL_PROVIDER
AI_MODEL_NAME
AI_PROMPT_VERSION
mode
timeout_seconds=30
backend_max_retries=0
```

단위 Test는 `openai / gpt-4.1-mini / e2e-baseline-v1` 주입값이 그대로 저장됨을 확인한다.
실제 운영값은 이동윤 후보의 Runtime Manifest를 받은 뒤 환경변수로 일치시키고 공동 Smoke에서
AIRun Row로 재확인한다.

## 8. 작성자 검증 결과

| 검증 | 결과 |
| --- | --- |
| Crosswalk·Verifier·EvidenceLink·AIRun Identity·Safety·Provisioning 표적 | `53 passed` |
| EvidenceLink·Submit·Follow-up·Role 표적 | `80 passed, 3 skipped` |
| Root Contract Test | `38 passed` |
| State/Crosswalk/OpenAPI/Example/Code Validator | 모두 PASS |
| Django Check | PASS |
| Migration Drift | `No changes detected` |
| 로컬 PostgreSQL evidence Migration | `0009·0010 applied` |
| 로컬 View | 8개 Column 일치, `0 rows` |
| 실제 Crosswalk Dry-run | Exit 1, 공식 문서 또는 제품 모델 미적재로 BLOCKED |
| Backend 전체 | `1100 passed, 19 skipped, 0 failed` |
| `git diff --check` | PASS |

Skip 19건은 PostgreSQL 구조·Row Lock·Role 17건, 실제 AI Uvicorn Socket 1건 등 환경 전용
Case다. PASS로 환산하지 않는다.

## 9. 아직 남은 Gate

1. 공식 Backend Evidence 7건 적재 후 Crosswalk Dry-run·Apply·Replay
2. PostgreSQL Migration 0009·0010 및 View Row·Column 확인
3. AI Role의 View SELECT와 Base Table/View DML 거부 독립 재현
4. 이동윤 AI Runtime의 View Target·Readonly DSN 적용
5. 실제 BGE-M3·pgvector·gpt-4.1-mini 공동 HTTP Smoke
6. AIRun·Guidance·EvidenceLink·Correlation DB 추적
7. 고객 Guidance/Public Evidence 계약 결정과 별도 Runtime 구현
8. 김은진 독립 QA와 PM 최종 Gate

## 10. Safety 변경 경계

Danger Rule 후보는 기존 State Guard의 fail-closed 검증을 보강하지만, 공식 Safety 정책은 별도다.
State 계약·DB 제약·AI 온수 Rule의 `PARTIAL_STOP/TOTAL_STOP/PENDING_CONSULTATION` 정합을
PM·AI와 확정하기 전 Safety 전체 완료를 주장하지 않는다. 출수량 저하 Happy Path의
Crosswalk·Evidence 구현과 Safety 정책 승인을 구분한다.

## 11. 공개 API 차단 사유

- `contracts/api/paths/evidence.yaml`은 빈 계약
- Evidence Card 준비 문서는 `PREPARATION_ONLY / runtime_implemented=false`
- `CustomerInquirySnapshot`은 `additionalProperties:false`
- Mobile DTO에도 Guidance/Evidence가 없음

따라서 PM·계약 Owner가 Snapshot 확장 또는 별도 Endpoint, PENDING Guidance 공개 여부,
공개 Evidence 필드, 미생성 응답 정책을 결정하기 전 Public API를 임의 구현하지 않는다.
