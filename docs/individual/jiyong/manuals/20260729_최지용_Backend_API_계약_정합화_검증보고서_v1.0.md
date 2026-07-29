# 2026-07-29 최지용 Backend API 계약 정합화 검증보고서 v1.0

> 작업 책임: 최지용(Backend·API·공통 오류 Registry)
> 입력 계약 책임: 윤승혁(PM, State·Allowed Action)
> 검증 협업 요청: 김은진(Data·통합 QA)
> 소비 호환성 확인 요청: 한예나(Web), 양정현(Mobile)
> AI 경계 확인: 이동윤(AI Schema·Runtime)
> 검토 상태: 로컬 자동 검증 완료, `jiyong` Push·PM 리뷰·`main` 병합 전
> 실행 원칙: `작업 → 집중 검증 → 증거 기록 → 다음 작업`

## 1. 목적과 기준

현재 구현을 늘리기 전에 OpenAPI·Django Route·공통 오류·JSON 예시의
기준을 맞춰 팀원이 서로 다른 계약을 소비하면서 생기는 연쇄 오류를
차단했다.

기준 원본:

- [OpenAPI](../../../../contracts/api/openapi.yaml)
- [Django Backend](../../../../backend/)
- [공통 오류 Registry](../../../../contracts/error-codes/error-codes.yaml)
- [PM Allowed Action](../../../../contracts/state-machine/allowed-actions.yaml)
- [API Runtime 상태](../../../api/runtime_implementation_status.md)

이번 작업에서는 Method·Path·`operationId`, Public UUID 의미,
`Idempotency-Key`, State Version, Token 정책과 PM State 전이를
변경하지 않았다. `contracts/state-machine/**`, `data/**`, `web/**`,
`mobile/**`, `ai/**`도 수정하지 않았다.

## 2. 순차 작업과 즉시 검증

### 2.1 OpenAPI 9개와 Runtime 7개 분리

OpenAPI Operation 9개를 실제 Django Route·View와 대조했다.

- Runtime 지원: 7개
- OpenAPI-only: 2개
  - `PATCH /api/v1/inquiries/{id}/questionnaire`
  - `POST /api/v1/inquiries/{id}/action-results`

추가한 자동 검증:

- [OpenAPI Runtime Coverage](../../../../backend/tests/api/test_openapi_runtime_coverage.py)
- [Runtime 상태표](../../../api/runtime_implementation_status.md)

미구현 2개는 등록되지 않은 Runtime URL에서 공통 404를 반환하는
경계까지 검사한다. `x-contract-status: CONFIRMED`를 Runtime 완료로
해석하지 않는다.

### 2.2 Runtime 공통 오류 4개 정합화

최상위 Registry에 없던 다음 코드를 기존 이름 변경 없이 가산했다.

| 코드 | Category | 대표 HTTP | 실제 Runtime 선택 규칙 |
|---|---|---:|---|
| `INVALID_REQUEST` | `validation` | 400 | 개별 override가 없는 4xx fallback |
| `RESOURCE_NOT_FOUND` | `persistence` | 404 | 404 개별 상태 override |
| `VALIDATION_ERROR` | `validation` | 422 | DRF `ValidationError` 예외 유형 override |
| `INTERNAL_ERROR` | `system` | 500 | 5xx fallback·처리되지 않은 예외 |

단일 `http_status`만 보고 405·503 등을 누락하지 않도록 Registry
최상위에 `runtime_http_mapping`을 추가했다. 이 계약은 다음 실제
Handler 순서를 표현한다.

1. `BackendError` 공개 값 통과
2. 예외 유형 override
3. 5xx 상태군 fallback
4. 개별 상태 override
5. 4xx 상태군 fallback
6. 처리되지 않은 예외

검증은 400~599 전체 범위, generic 422와 `ValidationError` 422의
서로 다른 코드, 처리되지 않은 500을 포함한다.

- [오류 Registry 계약 테스트](../../../../backend/tests/api/test_common_error_registry_contract.py)
- [공통 오류 Runtime 테스트](../../../../backend/tests/api/test_common_error_response.py)

Auth POST 3개가 실제로 반환할 수 있는 400·422도 OpenAPI에 가산하고
[422 공통 응답](../../../../contracts/api/components/responses/UnprocessableEntity.yaml)을
만들어 중복 인라인 정의를 제거했다.

### 2.3 구현 API JSON 예시 22개

신규 20개와 기존 Workflow 409 두 개를 모두 OpenAPI
`externalValue`로 연결했다.

| 디렉터리 | 수량 | 내용 |
|---|---:|---|
| [Auth](../../../../contracts/api/examples/auth/) | 7 | 요청 3·성공 4 |
| [Errors](../../../../contracts/api/examples/errors/) | 7 | 공통 400·401·403·404·422·500 |
| [Inquiries](../../../../contracts/api/examples/inquiries/) | 3 | START 요청·성공·Replay |
| [Workflow](../../../../contracts/api/examples/workflow/) | 5 | CANCEL 요청·성공·Replay·409 두 종류 |

의도적으로 만들지 않은 예시:

- `/health`: 200 No Body
- Auth 성공 Replay: 없음. 폐기된 Refresh Token 재사용은 401
- OpenAPI-only 2개: Runtime 미구현

Token은 실제 JWT가 아닌 `NOT_FOR_AUTHENTICATION` Placeholder만
사용한다. Header는 JSON 본문에 넣지 않으며
`Idempotency-Key` 누락 오류의 `details` 필드만 Header 이름을
표시한다.

예시 계약 테스트는 다음을 잠근다.

- JSON 22개 허용 목록·파싱
- 공통 Wrapper와 UUID `correlation_id`
- Runtime 요청·응답 Serializer
- Token·JWT 비밀값 부재
- 성공·Replay 데이터 불변성과 Replay Flag
- PM DRAFT/CUSTOMER `allowed_actions`
- 오류 코드·문구 Registry
- 모든 `externalValue`의 실제 상대경로
- 미구현 API·No-Body Health 예시 부재

- [JSON 예시 계약 테스트](../../../../backend/tests/api/test_runtime_examples_contract.py)

## 3. 최종 회귀 결과

저장소 루트에서 실행했다.

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

| 검증 | Exit code | 실제 결과 |
|---|---:|---|
| API·계약 + Auth 계약 | 0 | `94 passed in 4.45s` |
| 권한·소유권 + T-022·T-023 | 0 | `31 passed in 2.65s` |
| Django System Check | 0 | `System check identified no issues (0 silenced)` |
| 전체 Backend | 0 | `352 passed in 23.72s` |

각 묶음에는 겹치는 테스트가 있으므로 통과 수를 합산하지 않는다.
Git 공유 직전 문서까지 포함한 최종 HEAD에서 전체 Backend와
`git diff --check`를 다시 실행한다.

## 4. 완료 경계

완료:

- OpenAPI 9·Runtime 7·OpenAPI-only 2 상태 분리
- Runtime 공통 오류 4개와 Handler 선택 규칙 Registry 정합화
- 구현 API JSON 22개와 OpenAPI 상대 참조
- 계약·권한·전체 Backend 자동 검증

완료로 보고하지 않는 범위:

- OpenAPI-only 2개 Runtime
- 문의 목록·상세와 나머지 Workflow Action
- PM State Engine의 START·CANCEL 운영 Service 연결
- T-005 전체 32개 테이블
- Web·Mobile 실제 소비 검증
- AI Runtime·Backend AI Client
- PM 리뷰·`main` 병합

## 5. 팀별 인계 순서

### 5.1 윤승혁(PM)

1. 최지용의 `jiyong` 변경 범위가 Backend·API·오류·문서에 한정됐는지
   확인한다.
2. `contracts/state-machine/**`가 변경되지 않았는지 확인한다.
3. 9/7/2 경계와 미구현 2개에 예시가 없는지 검토한다.
4. PR을 `main`에 병합한다.
5. 팀에 병합된 40자리 `main` SHA와
   [팀 인계 진입점](../../../handoffs/README.md)을 전달한다.

### 5.2 김은진(Data·QA)

1. PM이 전달한 동일 `main` SHA를 반영한다.
2. 위 API·계약 94건과 전체 Backend 명령을 다시 실행한다.
3. JSON 22개·Registry 10개·400~599 Mapping 검증이 통과하는지
   확인한다.
4. 실패 시 Branch·SHA·명령·Exit code·응답의
   `correlation_id`를 최지용에게 전달한다.

### 5.3 한예나(Web)·양정현(Mobile)

1. PM `main` SHA에서 OpenAPI와 JSON 예시를 함께 반영한다.
2. Runtime 7개만 구현 Endpoint로 취급한다.
3. Questionnaire·Action Result 두 Operation은 계약 참고만 하고
   호출 코드를 만들지 않는다.
4. START·CANCEL은 JSON 본문과 별도로 새 `Idempotency-Key`를
   전송한다.
5. 성공 `allowed_actions` 객체와 두 종류 409를 서로 다른 DTO로
   처리한다.
6. 401·403·404·422·409에서 사용자 입력을 보존한 복구 흐름을
   검증한다.

### 5.4 이동윤(AI)

이번 변경은 `contracts/ai/**`와 AI Runtime을 수정하지 않았다.
AI 오류 Category를 정합화할 때 최상위 Registry의 기존 코드와
`runtime_http_mapping`을 삭제하거나 단일 HTTP 상태 목록으로
축소하지 않는다. AI Schema·Runtime Commit이 전달된 뒤 Backend
Client 연결은 별도 수직 작업으로 진행한다.

## 6. Git 공유 게이트

작업 시작 기준:

- Branch: `jiyong`
- 시작 HEAD·`origin/jiyong`:
  `540c4ce99eaa13fe66d7b321357b193e510ce6a2`

현재 보고서 작성 시점에는 최종 `jiyong` Push와 PM `main` SHA가
아직 없다. 팀원은 로컬 작업트리나 위 시작 SHA를 소비 기준으로
사용하지 않는다.

공유 순서:

1. 최지용이 범위·비밀값·상대 링크·전체 Backend를 최종 검증한다.
2. 작업 단위 Commit을 `jiyong`에 Push한다.
3. 윤승혁(PM)이 검토 후 `main`에 병합한다.
4. 팀원은 PM이 공유한 40자리 `main` SHA를 자기 Branch에 반영한다.

공식 Pull·검증 명령과 팀별 상세 인계는
[팀 인계 진입점](../../../handoffs/README.md)을 단일 원본으로
사용한다.
