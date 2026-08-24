# Backend AI View 53건 정합화 및 evidence.0014 구현·검증·인계

- 작업일: 2026-08-24
- 주담당: 최지용(Backend·DB)
- 요청 연계: 김은진(Data QA)
- 대상 View: `public.backend_ai_rag_chunks_v1`
- 결론: **격리 PostgreSQL 검증 기준 READY**
- 운영 RDS 상태: **미적용** — `main` 병합 SHA를 기준으로 김은진 작업자가 증분 적용·QA 필요

## 1. 작업 목적

Evidence, Crosswalk, Page Link에는 공식 3모델 데이터 53건이 존재하지만 기존
AI View는 `catalog_product_model.is_supported_mvp = TRUE`를 조회 조건으로 사용했다.
그 결과 Public MVP인 `WPUJAC104DWH` 15건만 보이고, Public MVP가 아닌
`WPUIAC425SNW`, `WPUIAC606SNW` 38건은 AI 검색 대상에서 빠졌다.

이번 변경은 **Public 제품 지원 범위**와 **검증된 AI 검색 Evidence 범위**를
분리한다. IAC 두 모델을 Public MVP로 활성화하지 않고, 검증된 3모델
Crosswalk 53건만 AI 전용 View에 노출한다.

## 2. 변경 전·후 비교

| 검증 항목 | 변경 전(0013) | 변경 후(0014) | 판정 |
|---|---:|---:|---|
| Crosswalk 활성·검증 건수 | 53 | 53 | 유지 |
| Crosswalk Page Link | 53 | 53 | 유지 |
| AI View 전체 행 | 15 | 53 | 정상화 |
| AI View 고유 `chunk_id` | 15 | 53 | 정상화 |
| 완전한 검색 계보 | 15 | 53 | 정상화 |
| `WPUJAC104DWH` | 15 | 15 | 유지 |
| `WPUIAC425SNW` | 0 | 19 | AI View에만 추가 |
| `WPUIAC606SNW` | 0 | 19 | AI View에만 추가 |
| IAC425 Public MVP | `false` | `false` | 변경 없음 |
| IAC606 Public MVP | `false` | `false` | 변경 없음 |
| 감사 상태 | `BLOCKED` | `READY` | 정상화 |
| 감사 blockers | View·Migration 관련 | `[]` | 해소 |

## 3. 핵심 설계 판단

### 3.1 Public MVP와 AI 검색 허용 조건 분리

0014는 `is_supported_mvp`를 갱신하지 않으며, 새 View 정의에서도 이 플래그를
AI 검색 허용 조건으로 사용하지 않는다. 다음 세 모델과 검증된 3모델 child
chunk 계약을 동시에 만족할 때만 조회한다.

- `WPUJAC104DWH`
- `WPUIAC425SNW`
- `WPUIAC606SNW`
- `chunking_version = rag_child_chunks_3model/1.0.0`
- 모델·페이지와 일치하는 `CHILD-{model}-P{page}-...` canonical ID
- 기존 0013의 Crosswalk 검증, 문서·페이지 승인, 1024차원 embedding,
  Data QA 차단 조건 모두 유지

단순히 `Public MVP OR 3모델`로 구성하지 않았다. 그렇게 하면 향후 다른
Public MVP 제품이 추가될 때 별도 AI 검증 없이 View 범위가 자동 확장될 수
있기 때문이다. 새 모델을 AI 검색 범위에 추가하려면 별도 계약·Migration·QA가
필요하도록 fail-closed로 고정했다.

### 3.2 이미 적용된 Migration 보존

- `evidence.0010`, `evidence.0013` 파일은 수정하지 않았다.
- 신규 [`evidence.0014`](../../../../backend/apps/evidence/migrations/0014_decouple_ai_view_product_eligibility.py)로만 처리했다.
- `CREATE OR REPLACE VIEW`를 사용해 기존 View Grant를 보존한다.
- 역Migration은 0013의 Public MVP 필터 View로 복구한다.
- `visits.0005_replace_visit_result_assignment_fk`는 P1 HOLD 상태로 적용하지 않았다.

## 4. 변경 파일과 역할

| 구분 | 파일 | 내용 |
|---|---|---|
| Migration | [`0014_decouple_ai_view_product_eligibility.py`](../../../../backend/apps/evidence/migrations/0014_decouple_ai_view_product_eligibility.py) | 3모델 전용 AI View 조건 및 0013 복구 로직 |
| 실제 PostgreSQL 회귀 | [`test_backend_ai_three_model_view_postgresql.py`](../../../../backend/tests/integration/database/test_backend_ai_three_model_view_postgresql.py) | 53건·계보·모델 분포·View 정의·권한 경계 검증 |
| Migration 단위 회귀 | [`test_migration_0014_ai_view_eligibility.py`](../../../../backend/tests/unit/evidence/test_migration_0014_ai_view_eligibility.py) | 기존 Migration 불변, 정확한 허용 조건, 역Migration 검증 |
| 감사기 | [`audit_backend_ai_g1b_readiness.py`](../../../../scripts/database/audit_backend_ai_g1b_readiness.py) | `three-model` 프로필, 제품 범위·53건·계보·권한 blocker 판정 |
| Allowlist | [`migrate_team_integration_allowlist.py`](../../../../scripts/database/migrate_team_integration_allowlist.py) | 승인 leaf를 evidence.0014로 갱신, visits.0005 HOLD 유지 |
| Backend 사전검증 | [`validate_backend_runtime.py`](../../../../scripts/deployment/production/validate_backend_runtime.py) | evidence.0014 필수, visits.0005 금지, pgvector 호환 확인 |
| AI Readonly 사전검증 | [`validate_ai_readonly_runtime.py`](../../../../scripts/deployment/production/validate_ai_readonly_runtime.py) | View 53건·계보 53·1024차원·Base Table 차단 확인 |
| 단위·배포 회귀 | 관련 unit/deployment test | 감사기, Allowlist, 배포 검증기 계약 보강 |

## 5. 작업→검증 반복 결과

| 순서 | 작업 | 검증 | 결과 |
|---:|---|---|---|
| 1 | 0014 미적용 격리 복제 DB 확인 | 감사기·Readonly 경계 확인 | View 15, Crosswalk/Page 53/53, 제품 플래그 정상, 권한 정상 |
| 2 | 0014 최초 적용 | Allowlist 적용·감사·실제 PostgreSQL 회귀 | View 53, 감사 READY |
| 3 | 0014를 0013으로 롤백 | View·제품 플래그·Grant 확인 | View 15로 복구, IAC false 유지, AI 권한 유지 |
| 4 | 정확한 3모델 허용 조건으로 재적용 | Plan→Apply→Grant 재조정 | 승인 Migration 92/92, 예상 외 Migration 0 |
| 5 | 최종 데이터 감사 | `three-model`, TEAM_INTEGRATION 강제 | READY, blockers `[]` |
| 6 | 실제 역할 Matrix | Runtime·Readonly·AI 계정 접속 회귀 | 2 passed |
| 7 | AI 운영 사전검증 | AI 전용 DSN으로 View/권한 확인 | PASS |
| 8 | 전체 관련 회귀 | Evidence·DB unit 및 배포 asset | 387 passed, 11 skipped |
| 9 | Django 상태 검사 | Migration drift·system check | No changes, 0 issues |

### 최종 격리 PostgreSQL 수치

| 항목 | 결과 |
|---|---:|
| PostgreSQL | 16.14 |
| 로컬 pgvector | 0.8.6 |
| 지원 pgvector 계약 | 0.8.2, 0.8.6 |
| View rows | 53 |
| distinct `chunk_id` | 53 |
| complete lineage | 53 |
| embedding dimensions | 1024 |
| 모델 분포 | JAC104 15 / IAC425 19 / IAC606 19 |
| Audit | READY |
| blockers | `[]` |

11건 skip은 PostgreSQL 전용 검사를 명시적 DB 실행 없이 수행한 일반 회귀의
정상 skip이다. 별도로 격리 PostgreSQL 플래그를 켠 실제 DB 회귀 2건은 모두
통과했다.

## 6. AI Readonly 권한 경계

| 대상 | SELECT | INSERT/UPDATE/DELETE/TRUNCATE | 결과 |
|---|---:|---:|---|
| `backend_ai_rag_chunks_v1` | 허용 | 차단 | 정상 |
| Crosswalk Base Table | 차단 | 차단 | 정상 |
| Document Chunk Base Table | 차단 | 차단 | 정상 |
| Embedding Base Table | 차단 | 차단 | 정상 |
| `public` schema CREATE | 차단 | 해당 없음 | 정상 |
| 기본 Transaction | Read only | 쓰기 차단 | 정상 |

## 7. 재검증 명령과 판정 방법

비밀값은 팀 Runtime 환경 파일에서 주입하고 터미널·문서에 출력하지 않는다.
다음은 환경을 로드한 뒤 실행하는 핵심 명령의 형태다.

```powershell
python scripts/database/migrate_team_integration_allowlist.py `
  --confirm-database waterbridge_team_integration `
  --confirm-source-sha <병합_SHA> `
  --confirm-hold visits.0005=P1_HOLD_EXCLUDED
```

Plan에서 `remaining_plan`이 `evidence.0014` 하나인지, 또는 이미 적용 후 빈
목록인지 확인한다. 예상 외 Migration이 있으면 적용하지 않는다.

```powershell
python scripts/database/audit_backend_ai_g1b_readiness.py `
  --evidence-profile three-model `
  --require-team-database `
  --require-ready
```

반드시 `--evidence-profile three-model`을 사용한다. 기본 `baseline` 프로필은
기존 7건 계약을 검사하므로 53건 DB에서 의도적으로 BLOCKED가 된다.

```powershell
python scripts/deployment/production/validate_ai_readonly_runtime.py
```

성공 기준은 `AI_READONLY_RUNTIME_PREFLIGHT_PASS`, View 53, 계보 53,
Base Table DENIED, Transaction READ_ONLY다.

## 8. 운영 RDS 인계 순서

이번 작업은 격리 Docker PostgreSQL에만 적용했고 운영 RDS는 변경하지 않았다.
`main` 병합 후 김은진 작업자는 다음 순서로 증분 적용한다.

1. 병합 SHA와 RDS 현재 Migration 상태 확인
2. Backup 생성 및 복구 가능 여부 확인
3. Allowlist Plan 실행 — 예상 외 Migration 0, `visits.0005` HOLD 확인
4. `evidence.0014`만 적용
5. 역할·Grant 재조정
6. `three-model` Audit 실행
7. AI Readonly 표적 QA 실행
8. View 53, distinct 53, lineage 53, Crosswalk/Page 53/53,
   제품 Public 범위 불변, blockers `[]` 확인

Fresh E2E는 이번 증분 View 정합화의 완료 조건이 아니다. 요청대로 three-model
Audit과 AI Readonly 표적 QA만 수행하면 된다. RDS 적용 중 수치·Migration
Plan·제품 플래그 중 하나라도 다르면 즉시 중단하고 롤백한다.

## 9. 완료 범위와 남은 승인

| 항목 | 상태 | 담당 |
|---|---|---|
| 코드·Migration·검증기 | 완료 | 최지용 |
| 격리 PostgreSQL apply/rollback/reapply | 완료 | 최지용 |
| 로컬 Audit·Readonly 표적 QA | 완료 | 최지용 |
| `jiyong` 브랜치 공유 | 본 작업 커밋·푸시로 완료 | 최지용 |
| `main` 병합 | 미완료 | 팀 병합 절차 |
| 운영 RDS Backup·Plan·Apply | 미완료 | 김은진 |
| 운영 RDS 증분 Audit | 미완료 | 김은진 |
| `visits.0005` | P1 HOLD 유지 | 관련 담당 합의 전 금지 |

따라서 이 문서의 READY는 **격리 PostgreSQL 구현 검증 READY**이며,
운영 RDS 적용 완료나 `main` 병합 완료를 의미하지 않는다.
