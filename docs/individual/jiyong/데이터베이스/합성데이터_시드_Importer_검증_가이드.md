# 합성데이터 Seed·Importer 검증 가이드

> 관련 업무: 합성 데이터 적재·재현
> 범위: 실제 고객·운영 Dump 제외

## 1. 목적

승인된 합성 Fixture를 PostgreSQL에 결정적으로 적재하고, Dry-run·Apply·Replay와
원장·상태·감사 정합성을 재현한다.

## 2. 주요 경로

- `data/synthetic/fixtures/**`
- `data/config/handoff/backend_import_crosswalk.json`
- `data/processed/metadata/**`
- `backend/apps/operations/**`
- `backend/apps/operations/management/commands/import_synthetic_handoff.py`
- `backend/tests/integration/operations/**`

## 3. 데이터 경계

- 공개 식별자는 Fixture의 Canonical ID와 Crosswalk로 연결한다.
- Fixture 정수 ID를 Django PK에 직접 주입하지 않는다.
- 직접 저장되지 않는 항목은 `PROJECTED`로 명시한다.
- Hash·Dataset Version·Mapping Version을 Import 원장에 남긴다.
- 충돌을 자동 병합하거나 오류 행만 건너뛰지 않는다.

## 4. 재현 절차

새 빈 PostgreSQL QA DB에서만 수행한다.

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py migrate --noinput

.\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
  --profile full --dry-run
.\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
  --profile full
.\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
  --profile full
```

## 5. 성공 조건

| 단계 | 성공 조건 |
| --- | --- |
| Dry-run | 도메인·Batch·Item 저장 0 |
| 최초 Apply | 입력이 CREATED 또는 명시적 PROJECTED |
| Replay | 비의도 CREATED·UPDATED 0 |
| 원장 | Batch와 모든 Source Item의 provenance 존재 |
| 상태 | Aggregate의 최종 상태·버전이 최신 History와 일치 |
| 감사 | 상태 이력과 Audit Event 연결 불일치 0 |
| 무결성 | Unique·FK·Check 오류 0 |

## 6. Seed와 Importer 구분

기본 Demo Seed는 개발 계정·제품·최소 시나리오를 준비한다. Synthetic Importer는
전체 합성 Handoff와 provenance를 검증한다. 두 절차를 같은 명령이나 같은
기본 DB에 혼합하지 않는다.

## 7. 안전 경계

- 기본 개발 DB에서 Importer와 Dry-run을 실행하지 않는다.
- Dry-run도 Sequence를 소비할 수 있으므로 새 QA DB를 사용한다.
- `dropdb`, Volume 삭제, 운영 Dump 적재는 이 가이드 범위가 아니다.
- 결과 문서에 DB Password·DSN·JWT·개인정보를 기록하지 않는다.

## 8. 판정

Fresh Migration, Dry-run, Apply, Replay, 원장·상태·감사 검증이 모두 통과하면
합성데이터 적재 기능은 작성자 검증 완료다. 소비자 E2E와 독립 QA는 별도다.

## 9. 2026-08-19 3제품 Fixture 선택 적재 보완

### 9.1 문제와 원인

Data/RAG 계보 확장으로 `products.json`의 물리 제품은 다음 3건이 됐다.

- `WPUJAC104DWH`: 기존 Backend 적재 대상
- `WPUIAC425SNW`: RAG 준비·Backend 계약 차단
- `WPUIAC606SNW`: RAG 준비·Backend 계약 차단

기존 Importer는 물리 파일을 읽을 때부터 제품 수를 1건으로 강제했다. 이 때문에
`LOAD_FILTERED` 선택 전 `Fixture count mismatch: products 3 != 1`로 중단됐다.

### 9.2 구현 내용

- 물리 Fixture 기대값과 DB Profile 선택 기대값을 분리했다.
- 물리 입력은 369행·제품 3건을 모두 식별자·분류 기준으로 검증한다.
- `db-smoke`, `db-full`은 CustomerProduct가 참조하는 제품만 선택한다.
- 현재 두 Profile의 선택 결과는 JAC104 제품 1건·전체 367행이다.
- IAC425·IAC606 ProductModel, 고객제품, 구독, 문의는 생성하지 않는다.
- 신규 제품을 삭제하거나 Backend Runtime 지원으로 승격하지 않았다.
- Model·Migration·OpenAPI 변경은 없다.

변경 경로:

- `backend/apps/operations/services/operations_service.py`
- `backend/tests/integration/operations/test_synthetic_handoff_import.py`
- `data/config/handoff/backend_import_crosswalk.json`
- `data/processed/metadata/consumer_handoff_manifest.json`
- `data/processed/metadata/final_dataset_manifest.json`

Data 파일 3개는 기능 데이터를 수동 수정한 것이 아니라, 변경된 Importer 소스
해시를 공식 동기화 도구로 갱신한 결정적 생성 산출물이다.

### 9.3 작성자 검증 결과

| 검증 | 결과 |
| --- | --- |
| 기존 실패 재현 | 5 failed, 모두 제품 물리 건수 불일치 |
| 수정 후 Importer 표적 | 6 passed, 0 failed |
| Django Check | PASS, issue 0 |
| Migration Drift | NONE |
| 최신 main Backend 전체 회귀 | 1302 passed, 0 failed, 34 skipped |
| Data QA·결정적 재생성 | PASS, 오류 0·경고 0·Drift 0 |
| Source Hash 재검사 | PASS, stale 0 |
| Diff 검사 | PASS |

34건의 Skip은 실제 PostgreSQL 구조·Row Lock, AI Uvicorn, 팀 Role Credential이
필요한 기존 별도 Gate다. 이번 변경은 SQLite Test Settings에서 작성자 회귀를
마쳤으며, Fresh PostgreSQL Apply·Replay는 비작성자 독립 QA에서 확인한다.
Windows 공용 Pytest 임시폴더 ACL로 발생한 Setup Error 5건은 전용 `basetemp`로
재실행해 해당 파일 7건과 전체 회귀가 모두 PASS함을 확인했다.

### 9.4 QA 확인 항목

1. 물리 제품 3건이 입력 검증을 통과하는지 확인한다.
2. Dry-run 후 도메인·Batch·Item 저장이 0건인지 확인한다.
3. `db-full` Apply 결과가 367 source, 355 created, 12 projected인지 확인한다.
4. ProductModel에는 `WPUJAC104DWH` 한 건만 적재되는지 확인한다.
5. IAC425·IAC606 관련 DB 행이 생성되지 않는지 확인한다.
6. Replay의 비의도 created·updated가 0건인지 확인한다.
7. 식별자 충돌 시 전체 Transaction이 Rollback되는지 확인한다.

## 10. 현재 판정

Backend 코드와 작성자 회귀는 `AUTHOR_READY`다. 신규 두 모델의 Runtime 활성화,
Vector DB 적재와 성능 평가는 포함하지 않는다. PostgreSQL 독립 QA가 PASS한 뒤
Importer 소비자 Gate를 완료로 판정한다.

## 11. 2026-08-19 상담사 Dashboard 로컬 Seed

Canonical Handoff Importer와 별개인 로컬 UI 연동용 합성 Seed다. 기존 문의 Runtime
DTO의 개인정보 비노출 경계를 바꾸지 않고 `operations` 읽기 Projection으로 제공한다.

### 11.1 제공 데이터

- 상담사 연락처 8건, 방문기사 연락처 4건
- 새 문의·처리 중·완료 문의 각 30건
- 상태별 긴급·주의·일반 문의 각 10건, 합계 90건
- 문의 제목·상세·합성 연락처·주소·고객코드·제품·보증·이전 방문 횟수
- 공지사항 6건과 본문
- 모든 이메일은 `.example`, 모든 행은 합성 식별자 Prefix로 격리

### 11.2 로컬 PostgreSQL 적용

전체 Migration을 실행하지 않는다. Plan에 `visits.0005`가 없는지 확인한 뒤 아래
Target만 선택 적용한다.

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py migrate operations 0002 --plan
.\.venv\Scripts\python.exe manage.py migrate operations 0002
.\.venv\Scripts\python.exe manage.py seed_consultant_dashboard --dry-run
.\.venv\Scripts\python.exe manage.py seed_consultant_dashboard
.\.venv\Scripts\python.exe manage.py seed_consultant_dashboard
```

Replay 성공 기준은 `created_count=0`, `updated_count=0`, 문의 90건이다. 기존 행을
삭제하거나 초기화하지 않는다.

### 11.3 Web 소비 API

- `GET /api/v1/consultant/dashboard`
- 인증: 활성 `CONSULTANT`
- 범위: 현재 상담사에게 배정된 합성 문의와 합성 공지·연락처만 반환
- 기존 `GET /api/v1/inquiries`는 상태 작업과 상세 이동에 계속 사용

Web은 `DASHBOARD_NOTICES`, `DASHBOARD_EMPLOYEE_CONTACTS`,
`DASHBOARD_VISIT_TECHNICIAN_CONTACTS` 및 Design Scenario 자동 대체를 제거하고 실제
API 응답을 사용한다. 이번 단계는 로컬 PostgreSQL 전용이며 RDS 적재는 포함하지 않는다.
