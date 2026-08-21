# Web G4 r3·r4 Backend DB 증거 수집 구현·검증 가이드

- 작성일: 2026-08-21
- 담당: 최지용(Backend·DB)
- 구현 기준: `main@1044ca99b503f26bcb32338a994e25e215dd7b49`
- 상태: `IMPLEMENTATION_PASS / LOCAL_POSTGRESQL_RUNTIME_BLOCKED`

## 1. 목적

한예나 Web G4 실행의 DB 증거를 기존 데이터 변경 없이 수집한다.

- r3는 이미 끝난 실행의 최종 상태만 수집한다.
- r3에 없던 Replay 전후 수치를 추정하거나 소급 생성하지 않는다.
- r4는 새 `run_id`와 새 합성 Inquiry로 처음부터 수집한다.
- Inquiry·Consultation·TransitionHistory·IdempotencyRecord를 한 Inquiry 범위로 묶는다.
- Migration 상태와 Schema fingerprint를 실행 전후로 비교한다.
- 고객 원문·상담 원문·Idempotency-Key·Secret·로컬 경로는 출력하지 않는다.

## 2. 구현 파일

| 파일 | 역할 |
| --- | --- |
| `backend/apps/inquiries/management/commands/collect_web_g4_db_evidence.py` | r3/r4 DB·Migration·Schema 증거 수집과 비교 |
| `backend/tests/unit/inquiries/test_web_g4_db_evidence.py` | 무변경·정제·Replay·409·Schema 불변 검증 |

기존 `audit_synthetic_e2e_inquiry`와 Runtime Service·API·State Machine은
변경하지 않았다.

## 3. DB 안전 경계

1. PostgreSQL에서는 수집 Query를 `SET TRANSACTION READ ONLY` 안에서 실행한다.
2. 기존 Transaction 내부에서 PostgreSQL 수집을 시작하면 중단한다.
3. r3 수집은 한예나 보존 DB에서 읽기 전용으로만 실행한다.
4. r4 쓰기 재현은 폐기 가능한 로컬 QA PostgreSQL에서만 실행한다.
5. 팀 공용 DB·RDS·한예나 보존 Volume을 초기화하지 않는다.
6. `visits.0005_replace_visit_result_assignment_fk`는 적용하지 않는다.
7. 예상하지 않은 Pending Migration이 있으면 Migration Gate를 차단한다.
8. 기존 증거 파일을 덮어쓰지 않는다.

## 4. r3 최종 Snapshot 수집

```powershell
python manage.py collect_web_g4_db_evidence `
  --inquiry-id <R3_INQUIRY_UUID> `
  --run-id <R3_RUN_ID> `
  --source-ref <40_CHAR_MAIN_SHA> `
  --phase r3-final `
  --output-dir <EMPTY_R3_EVIDENCE_DIR> `
  --require-migration-ready
```

r3 결과는 다음만 판정한다.

- 최종 Inquiry 상태·버전
- Consultation 행·상태·결과
- event/from/to/state_version/actor 역할
- Idempotency Operation·응답 상태·완료 여부
- Migration 상태와 Schema fingerprint

`historical_replay_evidence=NOT_CAPTURED`이면 Replay PASS로 승격하지 않는다.

## 5. r4 단계별 수집

동일한 `inquiry-id`, `run-id`, `source-ref`, 출력 폴더를 유지한다.

```text
r4-before-first-write
r4-after-first-write
r4-after-replay
r4-before-conflict
r4-after-conflict
r4-compare
```

각 단계 직후 다음 형식으로 실행한다.

```powershell
python manage.py collect_web_g4_db_evidence `
  --inquiry-id <R4_INQUIRY_UUID> `
  --run-id <R4_RUN_ID> `
  --source-ref <40_CHAR_MAIN_SHA> `
  --phase <PHASE> `
  --output-dir <R4_EVIDENCE_DIR> `
  --require-migration-ready
```

`r4-compare`의 PASS 조건은 다음과 같다.

- 첫 쓰기에서 예상된 History·Idempotency·state_version만 1회 증가
- 동일 요청 Replay 뒤 추가 행 0건
- Replay 전후 기존 행 Timestamp·내용 Snapshot hash 동일
- 409 전후 추가 행 0건
- 409 전후 기존 행 Timestamp·내용 Snapshot hash 동일
- Idempotency 중복 Scope 0건
- 추가 Consultation 0건
- Migration 상태 불변
- Schema fingerprint 불변

## 6. 정제 출력

출력에는 다음만 남긴다.

- 공개 Inquiry·Consultation UUID
- 상태·버전·Event·actor 역할
- Correlation ID
- Idempotency-Key의 SHA-256
- 원문 존재 여부와 원문 SHA-256이 아닌 Boolean 상태
- 생성·변경·완료 시각
- 행 수·Snapshot SHA-256·Schema SHA-256

다음은 출력하지 않는다.

- 고객 문의 원문과 답변 원문
- 상담 기록·요약·고객 안내 원문
- 사용자명·전화번호·이메일
- Raw Idempotency-Key
- DB Host·계정·Password·DSN
- 로컬 절대 경로

각 Capture 후 정제 검사와 `SHA256SUMS.txt`를 갱신한다.

## 7. 재문의 상태 전이 증거

현재 Runtime의 다음 흐름은 유효하다.

```text
COMPLETION_PENDING
-- CUSTOMER_REPORTED_UNRESOLVED / CUSTOMER --> REOPENED
-- RESUME_CONSULTATION / CONSULTANT --> CONSULTATION_REQUIRED
-- START_CONSULTATION / CONSULTANT --> CONSULTATION_IN_PROGRESS
```

수집기는 `changed_by_type_code`와 `actor_role_code`를 함께 기록하므로,
별도 Production 변경 없이 실제 event/from/to/actor 증거를 만들 수 있다.

## 8. 작성자 검증 결과

| 검증 | 결과 |
| --- | --- |
| 신규 수집기+기존 감사+재문의 표적 | `12 passed` |
| 상담 Runtime·Replay·409·재문의 관련 회귀 | `50 passed, 1 skipped` |
| Skip | PostgreSQL Row Lock 전용 1건 |
| Django Check | `0 issues` |
| Migration drift | `No changes detected` |
| Python Compile | PASS |
| 로컬 PostgreSQL 실제 수집 | `BLOCKED` |

로컬 PostgreSQL은 `127.0.0.1:5432`가 열려 있지 않고 Docker daemon도
중지되어 있었다. 이 검증을 위해 Container·Volume을 새로 만들거나
초기화하지 않았다. 따라서 PostgreSQL Runtime PASS는 주장하지 않는다.

## 9. 남은 실행

1. 한예나 PC 보존 DB에서 r3 최종 Snapshot을 읽기 전용 수집한다.
2. 폐기 가능한 로컬 PostgreSQL QA DB에서 새 r4를 실행한다.
3. `r4-compare`와 정제 검사 결과를 한예나·김은진에게 전달한다.
4. PostgreSQL에서 `visits.0005` HOLD와 예상 밖 Pending 0건을 재확인한다.

## 10. 범위 외

- `PRODUCT_VALIDATION_FAILED` Backend 매핑
- `danger + PARTIAL_STOP` 정책·Constraint 변경
- Web Playwright 수정
- Mobile·AI·Data·CI 수정
- 팀 공용 DB Migration·Seed·Reset
