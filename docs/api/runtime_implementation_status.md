# WaterBridge API Runtime 구현 상태

> 기준일: 2026-08-02
>
> 유지관리 역할: Backend·API 담당
>
> 문서 상태: 작성자 검증본 — 독립 재현·팀 검토 전

## 1. 현재 판정

현재 OpenAPI에는 Operation 10개가 등록돼 있다. 실제 Django Route와
View가 있는 Operation은 8개이고, 나머지 2개는 기계 계약만 존재하는
`OPENAPI_ONLY` 상태다.

| 구분 | 수량 | 판정 |
|---|---:|---|
| OpenAPI Operation | 10 | 기계 계약 등록 |
| Django Runtime | 8 | 실제 Route·View 존재 |
| OpenAPI-only | 2 | 계약은 있으나 Runtime 미구현 |
| Runtime 경계 자동 검증 | 10 | Runtime 8개와 미구현 경계 2개를 테스트로 구분 |
| 오류 Registry | 10 | 대표 오류 코드와 Runtime HTTP 매핑 등록 |
| 팀 검토 완료 | 0 | 비작성자 독립 재현·PM 통합 검토 전 |

`x-contract-status: CONFIRMED`는 Method·Path·Schema가 기계 계약에
등록됐다는 뜻이며 Runtime 구현 완료를 의미하지 않는다.

## 2. Operation별 지원 상태

| 상태 | Method | OpenAPI Path | `operationId` | 실제 Runtime Path | View |
|---|---|---|---|---|---|
| `RUNTIME_REVIEW_PENDING` | GET | `/health` | `getProvisionalHealth` | `/health` | `health` |
| `RUNTIME_REVIEW_PENDING` | POST | `/auth/demo-login` | `demoLogin` | `/api/v1/auth/demo-login` | `DemoLoginView` |
| `RUNTIME_REVIEW_PENDING` | POST | `/auth/refresh` | `refreshAuthToken` | `/api/v1/auth/refresh` | `TokenRefreshView` |
| `RUNTIME_REVIEW_PENDING` | POST | `/auth/logout` | `logout` | `/api/v1/auth/logout` | `LogoutView` |
| `RUNTIME_REVIEW_PENDING` | GET | `/me` | `getCurrentUser` | `/api/v1/me` | `MeView` |
| `RUNTIME_REVIEW_PENDING` | POST | `/inquiries` | `startInquiry` | `/api/v1/inquiries` | `CreateInquiryView` |
| `RUNTIME_REVIEW_PENDING` | POST | `/inquiries/{id}/submit` | `submitSymptom` | `/api/v1/inquiries/{inquiry_id}/submit` | `SubmitSymptomView` |
| `RUNTIME_REVIEW_PENDING` | POST | `/inquiries/{id}/cancel` | `cancelInquiry` | `/api/v1/inquiries/{inquiry_id}/cancel` | `CancelInquiryView` |
| `OPENAPI_ONLY` | PATCH | `/inquiries/{id}/questionnaire` | `accumulateInquiryQuestionnaire` | 없음 | 없음 |
| `OPENAPI_ONLY` | POST | `/inquiries/{id}/action-results` | `createInquiryActionResult` | 없음 | 없음 |

OpenAPI 기본 Server는 `/api/v1`이며 `/health`만 Operation별 Server `/`를
사용한다. 구현된 문의 Endpoint의 Public ID와 Django Path Parameter는
UUID다. OpenAPI-only 두 Operation은 Runtime 착수 전에 Path ID Schema를
현행 UUID 원칙과 다시 정합화해야 한다.

## 3. Runtime 구성 근거

| Operation | 주요 Serializer·응답 조립 | 집중 검증 파일 |
|---|---|---|
| `/health` | 200, 빈 본문 | `test_health.py`, `test_openapi_common_contract.py` |
| Auth 4개 | Auth Request Serializer와 Session 응답 | `test_auth_contracts.py`, `test_auth_api.py` |
| 문의 생성 | `CreateInquirySerializer`, `InquiryResponseSerializer` | `test_openapi_inquiry_contract.py`, `test_t022_create_inquiry.py` |
| 증상 제출 | `SymptomSubmissionSerializer`, `SubmitSymptomResponseSerializer` | `test_t022_submit_symptom.py`, `test_t022_submit_symptom_serializer.py` |
| 문의 취소 | `CancelInquirySerializer`, `CancelInquiryResponseSerializer` | `test_cancel_inquiry_contract.py`, `test_t023_cancel_inquiry.py` |

## 4. 오류와 JSON 예시

최상위 [오류 코드 Registry](../../contracts/error-codes/error-codes.yaml)는
10개 코드를 제공한다. `INVALID_REQUEST`의 기타 4xx fallback과
`INTERNAL_ERROR`의 5xx fallback은 `runtime_http_mapping`의 우선순위로
판정하므로 대표 `http_status` 하나만으로 정합성을 판단하지 않는다.

| 예시 디렉터리 | JSON 수량 | 범위 |
|---|---:|---|
| `auth` | 7 | 요청 3·성공 4 |
| `errors` | 7 | 400·401·403·404·422 두 종류·500 |
| `inquiries` | 6 | 문의 생성과 증상 제출의 요청·성공·Replay |
| `workflow` | 5 | 문의 취소 요청·성공·Replay·409 두 종류 |
| 합계 | 25 | Runtime Operation에만 연결 |

`/health`는 200과 빈 본문을 반환하므로 JSON 예시가 없다. OpenAPI-only
두 Operation에도 구현 예시를 연결하지 않는다.

## 5. 변경 금지선

현재 정합 작업에서는 다음 계약을 문서만으로 변경하지 않는다.

- Method·Path·`operationId`
- `Idempotency-Key` Header 위치와 Replay 의미
- Public UUID와 `state_version`의 의미
- JWT 수명·Rotation·폐기 정책
- `START_INQUIRY`, `SUBMIT_SYMPTOM`, `CANCEL_INQUIRY`의 상태·409 의미
- State Machine의 전이·종료·재개 정책

차이가 발견되면 OpenAPI, Route, Serializer, State 계약과 테스트 중 어느
기준이 다른지 먼저 기록하고 관련 담당 역할의 검토를 거친다.

## 6. 검증 기록

저장소 루트에서 실행하는 기본 검증 명령은 다음과 같다.

```powershell
$python = ".\backend\.venv\Scripts\python.exe"
$env:PYTHONDONTWRITEBYTECODE = "1"

& $python -m pytest `
  backend/tests/api `
  backend/tests/unit/accounts/test_auth_contracts.py `
  -q -p no:cacheprovider

& $python -m pytest `
  backend/tests/unit/accounts/test_permissions.py `
  backend/tests/api/test_t022_create_inquiry.py `
  backend/tests/api/test_t023_cancel_inquiry.py `
  -q -p no:cacheprovider

& $python .\backend\manage.py check --settings=config.settings.test
& $python -m pytest backend/tests -q -p no:cacheprovider
```

아래 수치는 **2026-08-02 작성자 검증 기록**이다. 이 문서 리팩터링에서
테스트를 새로 실행한 결과가 아니며, 팀 완료 판정에는 비작성자의 동일
환경 재현이 필요하다.

| 검증 범위 | 기록된 결과 |
|---|---|
| 자연어 단독 Submit 포함 집중 | SQLite `30 passed, 2 skipped`; PostgreSQL `22 passed` |
| 계약·Runtime·예시·권한 집중 | `72 passed, 2 skipped` |
| Django System Check | `System check identified no issues` |
| Migration drift·미적용 | `No changes detected`; `migrate --check` PASS |
| Backend 전체 SQLite | `778 passed, 13 skipped` |
| Backend 전체 PostgreSQL 격리 실행 | `791 passed` |

PostgreSQL 재현에서는 Demo Login과 CORS의 개발용 `.env` 값이 테스트
기대값을 덮어쓰지 않도록 테스트 전용 값을 Process 범위에만 적용한다.
실제 비밀값은 명령·문서·로그에 기록하지 않는다. 상세 재현 조건은
[Backend 작성자 구현·보안검증 가이드](../individual/jiyong/API/Django_REST_API_OpenAPI_계약_구현_보안검증_가이드.md)를
따른다.

## 7. 팀 검토 Gate

다음 조건이 모두 확인되기 전에는 `VERIFIED` 또는 팀 완료로 표시하지
않는다.

1. Backend 담당이 OpenAPI·Runtime·예시·테스트 변경 범위를 제공한다.
2. 비작성 검토자가 새 테스트 DB에서 집중 검증과 전체 회귀를 재현한다.
3. State 변경은 PM·기술 통합 담당이 State 계약과의 정합성을 검토한다.
4. Web·Mobile 담당이 실제 소비 DTO와 오류 처리를 확인한다.
5. QA 담당이 결과, 미구현 경계와 회귀 위험을 기록한다.
6. 승인된 변경이 팀 기준 Branch에 반영된 뒤 같은 기준으로 재검증된다.

Web·Mobile·QA는 OpenAPI-only 두 Operation을 구현 API로 소비하면 안 된다.
팀별 인계 흐름은 [통합 인계 허브](../handoffs/README.md)를 따른다.
