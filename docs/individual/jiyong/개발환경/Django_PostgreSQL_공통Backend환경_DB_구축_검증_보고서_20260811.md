# 공통 Backend 환경·Backend/DB 구축·검증 보고서

> 후속 상태: 이 문서에서 발견한 PostgreSQL Demo Login 500은 수정·재검증됐다.
> 현재 판단은 [공통 인증 Row Lock 수정·재검증 보고서](../인증_권한/Django_PostgreSQL_공통인증_RowLock_수정_재검증_보고서_20260811.md)를 우선한다.

## 1. 문서 정보

| 항목 | 내용 |
|---|---|
| 작성일 | 2026-08-11 |
| 작성자 | 최지용 — Backend·DB |
| 검증 기준 | `origin/main@92b0674cd1a3376a2c058715cd5ef32222125755` |
| 검증 당시 상태 | `ENVIRONMENT_READY / VERIFICATION_CHANGE_REQUIRED / FRONTEND_HANDOFF_HOLD` |
| 이번 범위 | 공통 Backend 환경 준비, 최지용 Backend·DB 검증 |
| 이번 범위 아님 | Backend 결함 수정, Web/Mobile 소스 수정, 인계서 작성, Commit/Push |

## 2. 당시 한 문장 결론

전용 PostgreSQL DB의 Migration·합성 Seed와 주요 API/계약 회귀는 정상이나,
실제 PostgreSQL에서 Demo Login이 500으로 실패하는 공통 인증 결함이 확인되어
Web·Mobile 공동 Smoke와 각 담당자 인계를 보류했다.

이 결함의 현재 해결 상태는 문서 상단의 후속 보고서를 기준으로 한다.

## 3. 이번 작업에서 지킨 경계

- 기존 작업자가 사용하는 Checkout과 변경 파일을 건드리지 않았다.
- 기존 로컬 DB `waterbridge`에는 Migration·Seed를 적용하지 않았다.
- Web와 Mobile 소스는 수정하지 않았다.
- Backend 소스와 계약도 수정하지 않고 검증과 원인 분석만 수행했다.
- Web·Mobile 인계문서는 사용자의 확인 전이므로 작성하지 않았다.
- 테스트용 임시 프로세스는 종료했고 8000 포트는 닫힌 상태로 정리했다.

## 4. 검토한 요청·경과 문서

원본 요청·경과 문서는 저장소 밖 `Daily_Process/20260811`에 보존한다.

- `양정현_5주차_Mobile_경과보고서_2026-08-11.md`
- `20260811_한예나_to_최지용_Web_상담사_문의조회_Runtime_공동Smoke_재검증_회신_v0.4.md`

두 문서의 공통 요구는 새 화면 구현이 아니라,
같은 PostgreSQL과 같은 Backend Runtime에서 인증 후 실제 API를 호출할 수 있는지 확인하는 것이다.

## 5. 검증 기준선과 격리 환경

### 5.1 Git 기준선

- 검증용 Worktree: `C:\python-src\Final_PROJECT\.codex_worktrees\backend_shared_smoke_20260811`
- HEAD와 `origin/main`이 모두 `92b0674cd1a3376a2c058715cd5ef32222125755`임을 확인했다.
- 검증 시작과 종료 시 `git status --short`는 빈 값이었다.
- 따라서 다른 작업자의 미커밋 변경이 테스트 결과에 섞이지 않았다.

### 5.2 Python·PostgreSQL

- Python: 기존 Backend `.venv`의 Python 3.13.13 재사용
- PostgreSQL: 16.14
- Schema: `public`
- DB Timezone: UTC
- PostgreSQL은 Docker에서 `127.0.0.1:5432`로만 노출되어 있다.
- Frontend는 PostgreSQL에 직접 접속하지 않고 Backend HTTP만 사용해야 한다.

### 5.3 전용 검증 DB

- 생성한 DB: `waterbridge_shared_smoke_20260811`
- 목적: 기존 개인 DB와 분리한 Migration·Seed·공동 Smoke 준비
- 기존 DB `waterbridge`는 검증 후에도 다음 상태가 그대로였다.
  - `accounts.0005_account_lifecycle_and_audit`: 미적용
  - `inquiries.0011_split_followup_question_metadata_and_answers`: 미적용
- 즉 기존 DB를 변경하지 않았다는 것을 전후 상태로 확인했다.

## 6. Migration 검증

전용 DB에 최신 Migration 전체를 정식 Django Migration으로 적용했다.

- `accounts.0005_account_lifecycle_and_audit`: 적용 완료
- `inquiries.0011_split_followup_question_metadata_and_answers`: 적용 완료
- 전체 Migration 적용 결과: PASS
- `MigrationExecutor` 미적용 Plan: `0`
- `manage.py migrate --check`: PASS
- `manage.py makemigrations --check --dry-run`: `No changes detected`
- `manage.py check`: `System check identified no issues`

관련 코드:

- [accounts 0005 Migration](../../../../backend/apps/accounts/migrations/0005_account_lifecycle_and_audit.py)
- [inquiries 0011 Migration](../../../../backend/apps/inquiries/migrations/0011_split_followup_question_metadata_and_answers.py)

## 7. 합성 Seed 준비와 반복 실행

다음 순서로 전용 DB에 Seed를 적용했다.

1. `seed_common_codes`
2. `seed_demo_accounts`
3. `seed_demo_products`
4. `seed_demo_subscriptions`
5. `seed_demo_care_records`
6. `seed_demo_consultant_inquiry`

같은 순서를 두 번 실행했다.

- 1회차: 필요한 합성 데이터 생성
- 2회차: 신규 중복 생성 없이 Update/Upsert 처리
- 상담사 계정: `DEMO-CONSULTANT-001`
- Web 고정 문의 UUID: `4f829120-ecbb-5b30-9365-bf02f9044c3b`

2회 실행 후 주요 행 수:

| 구분 | 행 수 |
|---|---:|
| 사용자 | 5 |
| 고객 프로필 | 2 |
| 제품 | 2 |
| 구독 | 2 |
| 케어 이력 | 3 |
| 문의 | 1 |
| Mobile 추가질문 | 0 |
| Mobile 추가답변 | 0 |

`seed_common_codes`는 미확정 매핑을 임의 추론하지 않았다.
`risk-levels.yaml`의 소문자 값과 Common Code 대문자 CHECK 충돌,
`ai-stages.yaml`의 미확정 Group Mapping은 기존 정책대로 적재하지 않았다.
현재 상담사 조회 Seed 자체를 막지는 않지만 별도 계약 정합화 대상이다.

## 8. 자동 검증 결과

### 8.1 PostgreSQL 표적 Runtime 1차

대상: Web 상담사 실제 Socket Smoke, 상담사 문의 목록·상세,
Mobile 고객 문의 Snapshot·질문·추가답변·멱등·상태 충돌,
`inquiries.0011` Forward/Reverse, Visit 자기 행 잠금 회귀

결과: `31 passed, 2 failed`

실패 두 건은 아래 9장에서 서로 다른 원인으로 분리했다.

### 8.2 PostgreSQL 표적 Runtime 분리 재검증

Demo Login 실제 Socket 실패를 제외하고,
테스트 설정과 같은 UTC 조건으로 나머지 DB/API 범위를 재실행했다.

결과: `32 passed`

이는 다음을 의미한다.

- 상담사 목록·상세의 Route·권한·Projection 로직은 표적 테스트에서 정상이다.
- Mobile Snapshot·질문·추가답변 로직은 PostgreSQL에서 정상이다.
- Migration 0011과 Visit self-row lock 회귀도 정상이다.
- 그러나 로그인 전에 막히므로 Frontend 공동 Runtime이 준비됐다는 뜻은 아니다.

### 8.3 Backend OpenAPI·Runtime Coverage

대상: `test_openapi_inquiry_contract.py`, `test_openapi_runtime_coverage.py`,
`test_runtime_examples_contract.py`

결과: `21 passed`

### 8.4 저장소 Root 기계계약

대상: `test_action_operation_crosswalk.py`, `test_week5_e2e_action_contract.py`,
`test_contract_validators.py`

결과: `12 passed, 1 warning`

Warning은 Windows 권한으로 `.pytest_cache`를 만들지 못했다는 내용이며
계약 검증 실패가 아니다.

## 9. 발견한 문제와 당시 판정

### 9.1 P0 — PostgreSQL Demo Login 500

당시 상태: `BACKEND_CHANGE_REQUIRED / COMMON_SMOKE_BLOCKED`

실제 Socket 요청:

```text
POST /api/v1/auth/demo-login
→ HTTP 500
→ NotSupportedError
```

로그 증거:

```text
correlation_id=381bed28-1740-4031-af47-c6157b64745a
route=/api/v1/auth/demo-login
status_code=500
exception_type=NotSupportedError
```

원인:

- User 행을 잠그기 위해 `select_for_update()`를 사용한다.
- 동시에 선택 관계인 `customer_profile`을 `LEFT OUTER JOIN`으로 조회한다.
- PostgreSQL은 nullable Outer Join 측까지 `FOR UPDATE`로 잠그는 것을 허용하지 않는다.
- SQLite는 이 제약을 재현하지 않아 기존 일반 테스트에서 발견되지 않았다.

관련 코드:

- [Account Repository](../../../../backend/apps/accounts/repositories/account_repository.py)
- [Authentication Service](../../../../backend/apps/accounts/services/authentication_service.py)
- [CustomerProfile 관계](../../../../backend/apps/accounts/models/customer_profile.py)

당시 영향:

- Web 상담사 Demo Login이 실패한다.
- Mobile 고객·기사 Demo Login도 같은 Token 발급 경로를 사용하므로 실패한다.
- 로그인 이후 목록·상세·답변 API까지 Frontend가 도달할 수 없다.
- 같은 구조를 쓰는 Refresh/Logout 잠금 경로도 PostgreSQL 재검증이 필요하다.

최소 수정 방향:

```python
User.objects.select_for_update(of=("self",))
```

후속 보고서에서 두 잠금 메서드 수정과 PostgreSQL 재검증 완료를 확인한다.

### 9.2 비차단 — Snapshot 시간대 테스트 기대값

1차 PostgreSQL 실행에서 실제 응답은 `+09:00`, 테스트는 UTC `Z`만 기대해 실패했다.

- OpenAPI는 `format: date-time`만 요구하며 UTC `Z`로 고정하지 않는다.
- `+09:00`도 올바른 RFC3339 DateTime이다.
- Runtime 변경 대상이 아니라 테스트가 같은 순간인지 비교하도록 보완할 대상이다.
- UTC 테스트 조건 재실행에서는 해당 범위가 통과했다.

관련 파일:

- [Customer Snapshot Schema](../../../../contracts/api/components/schemas/inquiry/CustomerInquirySnapshot.yaml)
- [Customer Snapshot Serializer](../../../../backend/apps/inquiries/api/serializers/customer_inquiry.py)
- [Customer Inquiry Runtime Test](../../../../backend/tests/api/test_customer_inquiry_read_runtime.py)

### 9.3 Mobile 공동 Smoke Fixture 공백

공식 Seed에는 Mobile 추가질문 `InquiryQA`를 만드는 Command가 없다.

- Snapshot의 기본 데이터 준비는 가능하다.
- `질문 조회 → 답변 제출`의 지속 DB 실제 HTTP 검증은 공식 Seed만으로 불가능하다.
- 자동 테스트는 테스트 내부 격리 Fixture를 사용하므로 32건 재검증에는 포함됐다.
- 공유 Fixture를 임의 추가하지 말고 합성 데이터 소유 범위를 확인한 뒤 별도 결정해야 한다.

관련 테스트:

- [Customer Inquiry Read Runtime](../../../../backend/tests/api/test_customer_inquiry_read_runtime.py)
- [Follow-up Answer Runtime](../../../../backend/tests/api/test_t022_submit_followup_answers.py)

## 10. 당시 Frontend 연결 가능 상태

| 구분 | 구현·자동검증 | 실제 PostgreSQL 로그인 | 공동 Smoke | 당시 판정 |
|---|---|---|---|---|
| Web 상담사 목록·상세 | 표적 Runtime PASS | 500 | 진입 불가 | HOLD |
| Mobile Snapshot·질문·답변 | 표적 Runtime PASS | 500 | 진입 불가 | HOLD |
| 공통 OpenAPI·Crosswalk | PASS | 해당 없음 | 해당 없음 | 유지 |
| 공통 Correlation 로그 | 500도 동일 ID 기록 | 확인 | 성공 흐름 미검증 | 부분 확인 |

현재 판정은 문서 상단의 후속 보고서를 따른다.

## 11. 네트워크 환경의 남은 조건

이번 환경은 Backend PC 로컬 검증용이다.

- PostgreSQL은 `127.0.0.1:5432` 유지가 맞다.
- 다른 PC Web 또는 Galaxy가 Backend에 접근하려면 Backend를 `0.0.0.0:8000`에 Bind해야 한다.
- Backend PC의 LAN IP/Hostname을 `DJANGO_ALLOWED_HOSTS`에 추가해야 한다.
- Web의 정확한 `scheme://host:port`를 CORS Allowlist에 추가해야 한다.
- 방화벽은 사설 네트워크의 Backend 8000 포트만 필요한 범위로 허용해야 한다.
- 위 값은 실제 공동 Smoke 위치를 정한 뒤 적용해야 하므로 이번에는 임의 변경하지 않았다.

## 12. 후속 작업 기준

완료된 후속 작업:

- Account Repository의 PostgreSQL Row Lock 범위를 User 자기 행으로 제한
- Demo Login·Refresh·Logout PostgreSQL 회귀 추가
- Snapshot DateTime 테스트를 순간 동등 비교로 보완
- 실제 Socket 상담사 Login·목록·상세·403·404·422 재검증
- 요청/응답/JSON Log의 Correlation ID 동일성 재검증

남은 작업:

- Mobile 노출 가능 구독·추가질문 공식 Fixture 결정
- 고객 Answers 200·Replay·409 공통 DB 실제 HTTP 검증
- 같은 PC 또는 LAN 공동 Smoke 주소·Host·CORS 확정
- Web용 인계서와 Mobile용 인계서를 각각 작성

## 13. 이력 상태

```text
공통 Backend 환경 준비: LOCAL_READY
전용 PostgreSQL Migration: PASS
합성 Seed 반복 실행: PASS
최초 PostgreSQL Demo Login: FAIL_REPRODUCED
후속 공통 인증 수정: COMPLETE
후속 PostgreSQL 재검증: PASS
Frontend 인계문서: NOT_CREATED
```
