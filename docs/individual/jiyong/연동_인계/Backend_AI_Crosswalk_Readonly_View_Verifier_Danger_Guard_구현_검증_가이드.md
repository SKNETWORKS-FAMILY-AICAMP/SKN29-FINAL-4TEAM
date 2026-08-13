# Backend·AI G1-B Crosswalk·Readonly View 사전점검 가이드

> 최신 검증: 2026-08-13 KST
>
> 작성 기준 main: `920176ebd77c9b5285ca62aea5f76671f9816997`
>
> Backend G1-B 구현 기준: `df9c01ccc4f6de748dec4503bb08f53aa42efe76`
>
> AI 공동검증 후보: `f1691df17dfdbc82283982379d9422d6a31e3c68`
>
> 상태: `AUTHOR_PREFLIGHT_PASS / LOCAL_DATA_BLOCKED / JOINT_E2E_PENDING`

## 1. 목적

G1-B 공동 Smoke 전에 Backend PostgreSQL이 AI/RAG 조회에 필요한 조건을 모두 갖췄는지
한 명령으로 확인한다. 도구는 `SELECT/SHOW`만 수행하고 Host·DSN·사용자·비밀번호를
출력하지 않는다.

제품 Runtime, AI 소유 코드, 공개 Guidance/Evidence API는 이번 작업에서 변경하지 않았다.

## 2. Backend 준비물

| 항목 | 구현·정본 |
| --- | --- |
| Canonical ID ↔ Backend Chunk | [`AIChunkCrosswalk`](../../../../backend/apps/evidence/models/ai_chunk_crosswalk.py) |
| Crosswalk Migration | [`evidence.0009`](../../../../backend/apps/evidence/migrations/0009_ai_chunk_crosswalk.py) |
| AI 조회 View | [`evidence.0010`](../../../../backend/apps/evidence/migrations/0010_backend_ai_rag_chunks_view.py) |
| 공식 7건 동기화 | [`sync_ai_canonical_crosswalk`](../../../../backend/apps/evidence/management/commands/sync_ai_canonical_crosswalk.py) |
| AI Reference 검증 | [`EvidenceReferenceVerifier`](../../../../backend/apps/evidence/services/evidence_reference_verifier.py) |
| Guidance·AIRun Evidence 저장 | [`InquiryAIService`](../../../../backend/apps/inquiries/services/inquiry_ai_service.py) |
| AI 최소권한 Role | [`provision_team_integration.py`](../../../../scripts/database/provision_team_integration.py) |
| G1-B 사전점검 | [`audit_backend_ai_g1b_readiness.py`](../../../../scripts/database/audit_backend_ai_g1b_readiness.py) |

View 공개 열은 다음 8개로 고정한다.

```text
chunk_id, metadata, content, embedding,
model_code, product_generation, verification_status, allowed_use
```

내부 PK, Backend Public UUID, 서버 경로, 전체 원문 파일은 AI View 계약 밖으로 내보내지 않는다.

## 3. READY 판정

다음 조건을 같은 PostgreSQL DB에서 모두 만족해야 `READY`다.

1. `evidence.0009`, `evidence.0010` Migration 적용
2. 활성·검증 Crosswalk 정확히 7건
3. 7건 모두 `BAAI/bge-m3`와 승인 Revision 사용
4. `backend_ai_rag_chunks_v1` 존재, 8개 열 순서 일치
5. View 행 7건, `chunk_id` 중복 0건
6. `waterbridge_ti_ai_readonly`가 안전한 Login Role
7. AI Role의 기본 Transaction이 read-only
8. AI Role은 View SELECT만 허용
9. AI Role의 Schema CREATE, View DML, Base Table SELECT는 거부

한 항목이라도 다르면 `BLOCKED`이며 완료로 확대하지 않는다.

## 4. 실행 명령

저장소 루트에서 현재 설정 DB를 보고서 형태로 확인한다. `BLOCKED`여도 진단 명령은 Exit 0이다.

```powershell
.\backend\.venv\Scripts\python.exe -B `
  .\scripts\database\audit_backend_ai_g1b_readiness.py
```

공동 환경 Gate는 DB명까지 확인하고, READY가 아니면 Exit 1로 닫는다.

```powershell
.\backend\.venv\Scripts\python.exe -B `
  .\scripts\database\audit_backend_ai_g1b_readiness.py `
  --require-ready --require-team-database
```

환경변수는 외부에서 안전하게 주입한다. `.env`, DSN, Password, Token을 명령·문서·로그에
복사하지 않는다.

## 5. 2026-08-13 로컬 실측

| 확인 | 결과 |
| --- | --- |
| PostgreSQL | `16.14`, 로컬 작성자 DB |
| Migration 0009·0010 | `APPLIED` |
| View 존재·열 | `YES`, 8/8 일치 |
| 활성·검증 Crosswalk | `0/7` |
| View 행 | `0/7` |
| AI Role | 존재·Role 속성 안전 |
| 현재 DB의 AI Role read-only/View SELECT | 미적용 |
| 보고서 명령 | `BLOCKED`, Exit 0 |
| 강제 Gate 명령 | `BLOCKED`, Exit 1 |

현재 Blocker는 다음과 같다.

```text
ACTIVE_VERIFIED_CROSSWALK_COUNT_NOT_7
BASELINE_EMBEDDING_IDENTITY_COUNT_NOT_7
BACKEND_AI_RAG_VIEW_ROW_COUNT_NOT_7
AI_READONLY_DEFAULT_TRANSACTION_NOT_READ_ONLY
AI_READONLY_VIEW_SELECT_DENIED
```

이는 제품 코드 실패가 아니다. 로컬 작성자 DB에 공식 Evidence 7건과 팀 통합 DB용 권한을
적용하지 않았다는 정확한 사전점검 결과다.

## 6. 작성자 검증

| 검증 | 결과 |
| --- | --- |
| 신규 Audit 판정·비밀 보호 + Provisioning 단위 | `25 passed` |
| 실제 Role 통합 Test 수집 | `1 skipped` |
| Django Check | `0 issues` |
| Python 구문 검사 | PASS |
| `git diff --check` | PASS |

통합 Test Skip은 `TEAM_INTEGRATION_POSTGRES_TEST=1`과 폐기 가능한 팀 PostgreSQL 환경이
없어 의도적으로 미실행한 것이다. PASS로 계산하지 않는다.

검증 Test:

- [`test_backend_ai_g1b_readiness.py`](../../../../backend/tests/unit/database/test_backend_ai_g1b_readiness.py)
- [`test_team_integration_provision.py`](../../../../backend/tests/unit/database/test_team_integration_provision.py)
- [`test_team_integration_roles_postgresql.py`](../../../../backend/tests/integration/database/test_team_integration_roles_postgresql.py)

## 7. 공동 환경에서 남은 순서

1. 김은진이 동일 후보의 팀 PostgreSQL·pgvector와 최소권한 Role 준비
2. 공식 Backend Evidence 7건 적재
3. Crosswalk Dry-run → Apply → Replay로 신규 0 확인
4. Provisioning 재실행 후 본 가이드의 강제 Gate `READY` 확인
5. 이동윤 AI Runtime이 readonly DSN과 `backend_ai_rag_chunks_v1`을 조회
6. Backend→AI→RAG→LLM→Backend 저장 공동 HTTP Smoke
7. AIRun·Guidance·EvidenceLink·Correlation을 같은 요청으로 추적
8. 김은진 독립 QA와 PM 최종 Gate

## 8. 변경 금지 경계

- AI 후보의 Vector Store·LLM 코드는 이동윤 소유이므로 여기서 수정하지 않는다.
- 공식 7건이 없는 DB에서 Crosswalk Apply나 READY를 주장하지 않는다.
- Public Guidance/Evidence Path·DTO는 계약 확정 전 추가하지 않는다.
- Danger Safety 정책과 G1-B 출수량 저하 Happy Path를 하나의 완료로 묶지 않는다.
- 실제 Role 통합 Test 없이 최소권한을 최종 PASS로 선언하지 않는다.

업무 범위는 [최지용 E2E 집중 지침](../../../weekly-task/최지용_5주차_8월13-14일_E2E_집중_업무_지침서.md)의
G1-B Backend 수직 연동 사전검증에 한정한다.
