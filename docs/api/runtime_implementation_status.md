# WaterCare API Runtime 구현 상태

> 기준일: 2026-07-29
> 작성·유지 책임: 최지용(Backend·API OWNER)
> 문서 상태: `CURRENT` — 현재 OpenAPI와 Django Route의 지원 상태 기준
> 실행 원칙: `작업 → 집중 검증 → 증거 기록 → 다음 작업`

## 1. 판정

현재 기계 계약에는 OpenAPI Operation 9개가 등록돼 있다. 이 중 실제
Django Runtime Route가 있는 Operation은 7개이고, 2개는 계약만
확정된 `OPENAPI_ONLY` 상태다.

| 구분 | 수량 | 판정 |
|---|---:|---|
| OpenAPI Operation | 9 | 기계 계약 등록 |
| Django Runtime | 7 | 실제 Route·View 존재 |
| OpenAPI-only | 2 | 계약은 있으나 Runtime 미구현 |
| 자동 계약 검증 | 9 | Runtime 7개와 미구현 경계 2개 모두 통과 |
| 팀 리뷰 완료 | 0 | `jiyong` Push·PM 검토·`main` 병합 전 |

`x-contract-status: CONFIRMED`는 Method·Path·Schema의 OWNER 계약이
확정됐다는 뜻이며 Runtime 구현 완료를 의미하지 않는다.

## 2. Operation별 매핑

| 구분 | Method | OpenAPI Path | `operationId` | 실제 Runtime Path | View | 주요 Serializer | 집중 검증 |
|---|---|---|---|---|---|---|---|
| Runtime | GET | `/health` | `getProvisionalHealth` | `/health` | `common.api.health.health` | 없음, 200 No Body | `test_health.py`, `test_openapi_common_contract.py` |
| Runtime | POST | `/auth/demo-login` | `demoLogin` | `/api/v1/auth/demo-login` | `DemoLoginView` | 요청 `DemoLoginRequestSerializer`; 응답 `_session_data()` 직접 조립 | `test_auth_contracts.py`, `test_auth_api.py` |
| Runtime | POST | `/auth/refresh` | `refreshAuthToken` | `/api/v1/auth/refresh` | `TokenRefreshView` | 요청 `RefreshTokenRequestSerializer`; 응답 `_session_data()` 직접 조립 | `test_auth_contracts.py`, `test_auth_api.py` |
| Runtime | POST | `/auth/logout` | `logout` | `/api/v1/auth/logout` | `LogoutView` | 요청 `RefreshTokenRequestSerializer`; 응답 `revoked` 직접 조립 | `test_auth_contracts.py`, `test_auth_api.py` |
| Runtime | GET | `/me` | `getCurrentUser` | `/api/v1/me` | `MeView` | Runtime Serializer 없음; `AccountService.user_data()` 직접 조립 | `test_auth_contracts.py`, `test_auth_api.py` |
| Runtime | POST | `/inquiries` | `startInquiry` | `/api/v1/inquiries` | `CreateInquiryView` | `CreateInquirySerializer`, `InquiryResponseSerializer` | `test_openapi_inquiry_contract.py`, `test_t022_create_inquiry.py` |
| Runtime | POST | `/inquiries/{id}/cancel` | `cancelInquiry` | `/api/v1/inquiries/{inquiry_id}/cancel` | `CancelInquiryView` | `CancelInquirySerializer`, `CancelInquiryResponseSerializer` | `test_cancel_inquiry_contract.py`, `test_t023_cancel_inquiry.py` |
| OpenAPI-only | PATCH | `/inquiries/{id}/questionnaire` | `accumulateInquiryQuestionnaire` | 없음 | 없음 | 계약 Schema만 존재 | Runtime으로 표시하거나 예시를 만들지 않음 |
| OpenAPI-only | POST | `/inquiries/{id}/action-results` | `createInquiryActionResult` | 없음 | 없음 | 계약 Schema만 존재 | Runtime으로 표시하거나 예시를 만들지 않음 |

OpenAPI의 기본 Server는 `/api/v1`이다. `/health`만 Operation별
Server `/`를 사용한다. Django의 Path Parameter 이름
`inquiry_id`와 Public OpenAPI 이름 `id`는 모두 같은 문의 Public UUID를
받으며, 업무 표시 코드로 대체하지 않는다.

## 3. 순차 작업 결과

| 순서 | 작업 | 결과 | 다음 단계 진입 조건 |
|---:|---|---|---|
| 1 | OpenAPI 9개 ↔ Runtime 7개 매핑 | 지원 7개·OpenAPI-only 2개 고정 | Route·View·`operationId` 검증 통과 |
| 2 | Runtime 공통 오류 Registry 정합화 | 누락 4개 추가, 최상위 Registry 총 10개 | 대표 상태와 `runtime_http_mapping` 검증 통과 |
| 3 | 구현 API JSON 예시 | 신규 20개, 기존 409 2개, 총 22개 | JSON·Serializer·참조·비밀값 검증 통과 |
| 4 | 회귀 검증 | 계약 94건·권한 31건·전체 Backend 352건 통과 | Git 공유 범위 확인 가능 |

오류 코드별 `http_status`는 대표 상태다. `INVALID_REQUEST`의 기타
4xx fallback과 `INTERNAL_ERROR`의 5xx fallback은
[`runtime_http_mapping`](../../contracts/error-codes/error-codes.yaml)에
예외 유형·개별 상태·상태군 우선순위로 기록했다. 따라서 400·500 한
값만 비교해 정합성을 판정하지 않는다.

JSON 예시 구성:

| 디렉터리 | 수량 | 범위 |
|---|---:|---|
| `auth` | 7 | 요청 3·성공 4, 성공 Replay 없음 |
| `errors` | 7 | 400·401·403·404·422 두 종류·500 대표 |
| `inquiries` | 3 | START 요청·성공·Replay |
| `workflow` | 5 | CANCEL 요청·성공·Replay·기존 409 두 종류 |

`/health`는 200 No Body이므로 JSON 예시가 없다. OpenAPI-only 2개에도
구현 예시를 연결하지 않았다.

## 4. 변경 금지선

현재 정합 작업에서는 다음 항목을 바꾸지 않는다.

- Method·Path·`operationId`
- `Idempotency-Key` Header 위치
- `state_version`과 문의 Public UUID 의미
- Auth Token 수명·Rotation·폐기 정책
- START·CANCEL의 상태·409·Replay 의미
- PM 관할 State Machine의 전이·Terminal·Reopen 정책

차이가 발견되면 문서만 맞춰 쓰지 않고 OpenAPI·Route·Serializer·
테스트 중 어느 원본이 다른지 기록한 뒤 해당 단계에서 중단한다.

## 5. 검증 명령과 실제 결과

저장소 루트에서 실행한다.

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

2026-07-29 현재 작업트리에서 새로 실행한 결과:

| 검증 | Exit code | 결과 |
|---|---:|---|
| API·계약 + Auth 계약 | 0 | `94 passed in 4.45s` |
| 권한·소유권 + T-022·T-023 | 0 | `31 passed in 2.65s` |
| Django System Check | 0 | `System check identified no issues` |
| 전체 Backend | 0 | `352 passed in 23.72s` |

검증 묶음은 일부 테스트가 서로 겹치므로 수치를 합산하지 않는다.
최종 Git 공유 전에는 문서 변경까지 포함한 HEAD에서 전체 Backend와
`git diff --check`를 다시 실행한다.

## 6. 남은 공유 게이트와 인계

구현·자동 검증은 완료됐지만 팀 공용 완료 상태는 아니다. 남은 순서는
`jiyong` 범위 확인·Commit·Push → 윤승혁(PM) 검토·`main` 병합 →
PM의 40자리 `main` SHA 공유다.

Web·Mobile·QA 담당자는 OpenAPI-only 2개를 구현 API로 소비하지 않는다.
상세 변경·검증·팀별 다음 행동은
[Backend API 계약 정합화 검증보고서](../individual/jiyong/manuals/20260729_최지용_Backend_API_계약_정합화_검증보고서_v1.0.md)와
[팀 인계 진입점](../handoffs/README.md)을 따른다.
