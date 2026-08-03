# Django REST API·OpenAPI 계약·구현·보안 검증 가이드

> 기준일: 2026-08-02
> 유지 책임: Backend·Database 담당
> 적용 원칙: API Method·Path·DTO·오류는 기계 계약과 실제 Runtime을
> source of truth로 삼고, 구현은 `작업 → 검증` 단위로 진행한다.

## 0. 문서 책임·협업·검토

| 항목 | 내용 |
| --- | --- |
| 문서 상태 | 현행 API 계약 개발·인계 기준 |
| 관련 WBS | `T-016`, `T-017`, `T-022`, `T-023` |
| 작성·유지 책임 | Backend·Database 담당 |
| 계약 의사결정 역할 | Backend·Database: API Method·Path·DTO·오류 계약과 Django·PostgreSQL 반영 기준. PM: State Machine 업무 규칙. AI·RAG: Backend↔AI Schema·실패 경계 |
| 협업 책임 | PM: 계약·State 연계, Data·QA: Contract·Integration QA, AI·RAG: AI Schema, Web·Mobile: Client 소비 |
| 검토 요청 대상 | PM: 계약·State 정합성, Data·QA: 계약·PostgreSQL 재현, AI·RAG·Web·Mobile: 각 소비 영역 호환성 |
| 검토 상태 | 미요청 또는 증거 미확인 |
| PR 병합 담당 | PM, 비작성자 1명 이상 리뷰 후 |
| 인계 대상 | PM, Data·QA, AI·RAG, Web, Mobile |

위 검토는 ERD·테이블 명세·API 명세·Django·PostgreSQL의 source of
truth를 각 영역이 재현·소비할 수 있는지 확인하는 절차다. 구현 착수
승인과 소비자 호환성 검토를 구분하고, 불일치가 있으면 재현 사례와
계약 차이를 기록한다.

### 0.1 2026-08-02 현재 판정

이 절은 기준일에 확인한 실행 스냅샷이다. 이후 변동한 Route와 회귀 결과는
[API Runtime 구현 상태](../../../api/runtime_implementation_status.md)를
우선한다.

| 항목 | 현재 값 | 해석 |
| --- | --- | --- |
| OpenAPI Operation | 10 | 2026-08-02 기계 계약에 선언된 범위 |
| Django Runtime | 8 | Account·Inquiry 실제 Route/View가 있는 범위 |
| OpenAPI-only | 2 | 계약은 있으나 실제 Route가 없는 범위 |
| T-022 Slice A | 작성자 구현·검증 완료, 팀 기준선 반영 전 | 자연어 단독 Submit, 상태 이력, Replay, Rollback, PostgreSQL 동시성 포함 |
| 현재 전체 회귀 | SQLite `778 passed, 13 skipped`; PostgreSQL `791 passed` | 작성자 검증 증거이며 비작성자 재현·PM 병합 전 |
| 공통 로그 보안 | 집중 `14 passed` 기록 | 현재 Request·Exception 로그 경로만 해당 |

2026-07-29의 OpenAPI 9개·Runtime 7개와 당시 테스트 수치는 역사
스냅샷이다. 현재 계약·Runtime 수와 섞지 않는다. T-022는 작성자 검증을
통과했지만 계약 PR·구현 PR·독립 재현·PM 병합 전에는 팀 공용
Runtime으로 표시하지 않는다.

## 1. 문서 목적

이 문서는 API source of truth를 OpenAPI, Django URL, Serializer,
Service, Model과 테스트에 일관되게 반영하는 절차를 정의한다. 구현
여부와 실행 검증 여부를 분리해 표시한다.

## 2. 단일 원본

| 구분 | 원본 | 용도 |
| --- | --- | --- |
| Public API 설명 | [WaterBridge API 명세](../../../api/waterbridge_api_specification.md) | Public 후보 42개의 Method·Path·입출력 기준 |
| 기획 기준 | [API 명세서](../../../planning/md/API명세서.md) | 업무 요구사항과 API ID 연결 |
| 기계 계약 | [OpenAPI](../../../../contracts/api/openapi.yaml) | 자동 검증 가능한 Path·Schema·Header |
| 공통 코드 | [공통 코드 계약](../../../../contracts/codes) | 역할·상태·위험도·사용 안내 코드 |
| 오류 코드 | [오류 코드 계약](../../../../contracts/error-codes) | 공개 오류 코드와 HTTP 상태 |
| Django Runtime | [Backend](../../../../backend) | URL·Serializer·Service·Repository·Model |

사람용 명세와 OpenAPI를 별도 후보안으로 운영하지 않는다. 기계 계약과
승인된 사람용 명세의 우선순위를 확인하고 OpenAPI와 Runtime을 같은
필드·코드·제약으로 맞춘다.

## 3. 현재 상태와 실행 증거의 단일 원본

이 가이드에는 수시로 변하는 Endpoint 수, 테스트 수와 다음 작업 순서를
복제하지 않는다. 현재 구현 상태와 실행 증거는 목적별 문서에서 확인한다.

| 확인 목적 | 단일 원본 |
| --- | --- |
| Auth 계약·Route·Token 동작과 API 통합 회귀 | [Django JWT·RBAC 로그인·계정관리 구현·검증 가이드](../인증_권한/Django_JWT_RBAC_로그인_계정관리_구현_검증_가이드.md) |
| PostgreSQL·Migration·Seed 구현 경계 | [T-005 테이블 구현 및 변경 이력](../데이터베이스/Django_PostgreSQL_테이블_구현_변경이력_20260730.md) |
| 새 환경 실행·재현 순서 | [워터브리지 백엔드 설치·Migration·Seed·복구 가이드](../개발환경/Django_PostgreSQL_로컬개발환경_설치_실행_복구_가이드.md) |
| OpenAPI·Runtime 현재 지원 경계 | [API Runtime 구현 상태](../../../api/runtime_implementation_status.md) |
| 오류 Registry·JSON 예시 | [오류 코드 계약](../../../../contracts/error-codes)과 [API Runtime 구현 상태](../../../api/runtime_implementation_status.md) |
| T-022 문의·`SUBMIT_SYMPTOM` 계약 Gap | [문의·증상 제출 구현·검증·인계서](Django_REST_API_문의_증상제출_구현_검증_인계서.md) |
| Workflow 현재 구현·후속 Gate | 이 문서 8.1절과 [API Runtime 구현 상태](../../../api/runtime_implementation_status.md) |

이 문서는 위 결과를 다시 요약하는 보고서가 아니라, 어떤 API에도 반복
적용하는 계약 작성·구현·검증 절차의 단일 원본으로 유지한다.

## 4. 계약 상태 표기

| 한국어 판정 | 보조 상태 코드 | 기준 |
| --- | --- | --- |
| 명세 확정 | `SPEC_CONFIRMED` | 승인된 명세와 기계 계약에 Method·Path·필드가 정의됨 |
| OpenAPI 정의 | `OPENAPI_DEFINED` | 기계 계약과 `$ref`가 작성됨 |
| Runtime 구현 | `RUNTIME_IMPLEMENTED` | Django URL부터 저장 계층까지 구현됨 |
| Runtime 검증 | `RUNTIME_VERIFIED` | 실제 PostgreSQL·HTTP·자동 회귀를 통과함 |
| Runtime 미구현 | `NOT_IMPLEMENTED` | 명세는 확정됐지만 Runtime이 아직 없음 |

`OPENAPI_DEFINED`를 Runtime 완료로 계산하지 않는다. Runtime이 없는
항목은 다음 구현 순서에 배치한다.

## 5. 작업·검증 절차

실제 PostgreSQL·HTTP 검증을 시작하기 전에
[워터브리지 백엔드 설치·Migration·Seed·복구 가이드](../개발환경/Django_PostgreSQL_로컬개발환경_설치_실행_복구_가이드.md)의
5장에 따라 PostgreSQL과 Django를 실행한다. 이 가이드에는 서버
시작·종료 명령을 중복하지 않는다.

### 5.1 작업

1. API source of truth에서 Method·Path·역할·필수 필드·오류를 확인한다.
2. OpenAPI Path와 Schema를 같은 이름과 제약으로 작성한다.
3. Model·Migration을 먼저 구현해 저장 원장을 확정한다.
4. Repository·Service에 조회 범위, Transaction과 업무 규칙을 둔다.
5. Serializer·View·URL을 연결한다.
6. 상태 변경 API는 State Machine과 멱등성 경계를 함께 적용한다.

### 5.2 즉시 검증

1. OpenAPI 문법, `$ref`, operation ID 중복을 검사한다.
2. `makemigrations --check --dry-run`으로 Model drift를 검사한다.
3. 실제 PostgreSQL에서 `migrate --check`를 실행한다.
4. 정상·검증 실패·401·403·404·409 시나리오를 실행한다.
5. Runtime 응답과 OpenAPI Schema를 비교한다.
6. 관련 테스트를 통과한 뒤 전체 Backend 회귀를 실행한다.

저장소 루트 기준 예시는 다음과 같다.

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate --check
.\.venv\Scripts\python.exe -m pytest -q
```

## 6. Endpoint 구현 체크리스트

- [ ] `/api/v1` Prefix와 복수형 `kebab-case` Path를 사용한다.
- [ ] 내부 PK·비밀값·개인정보를 Public DTO에 노출하지 않는다.
- [ ] Request 필수·선택·조건부 필드를 OpenAPI와 Serializer에 같이 둔다.
- [ ] 공통 성공·오류 Wrapper와 `X-Correlation-ID`를 유지한다.
- [ ] 목록은 `page >= 1`, `1 <= size <= 100`, `total >= 0`을 지킨다.
- [ ] 고객 소유·기사 배정 범위를 서버에서 검사한다.
- [ ] 상태 변경은 Service를 통해 수행하고 상태 이력을 남긴다.
- [ ] 중복 요청은 `idempotency_key`와 Payload 일치 여부를 검사한다.
- [ ] Token·Authorization·Cookie·요청 본문을 로그에 남기지 않는다.
- [ ] 실제 PostgreSQL과 전체 회귀 결과를 기록한다.

## 7. 인증 회귀 기준

인증 변경 시 최소한 다음을 다시 검증한다.

| 영역 | 시나리오 |
| --- | --- |
| 로그인 | 합성 사용자 성공, 잘못된 코드·비활성 사용자 거부 |
| Access | 정상 `/me`, 미인증·만료·변조 Token 거부 |
| Refresh | 새 Pair 발급, 기존 Refresh 즉시 폐기 |
| Logout | 제출 Refresh 폐기, 폐기 Token 재사용 거부 |
| 권한 | 고객 본인 객체와 기사 배정 객체만 허용 |
| 응답 | Password·전화·주소·Token 비노출 |
| 로그 | Secret·Token·개인정보 비노출 |

인증의 현재 테스트 수와 실행 결과는 이 가이드에 복제하지 않고
[Django JWT·RBAC 로그인·계정관리 구현·검증 가이드](../인증_권한/Django_JWT_RBAC_로그인_계정관리_구현_검증_가이드.md)를
기준으로 한다. 변경 PR에는 과거 수치를 재사용하지 않고 해당 변경에서
실제로 다시 실행한 결과만 기록한다.

## 8. 업무별 구현 상태와 후속 Gate

| 업무 | 현재 상태의 단일 원본 |
| --- | --- |
| DB Model·Migration 선행 작업 | [T-005 데이터베이스 스키마 변경 실행 가이드](../데이터베이스/Django_PostgreSQL_스키마_변경_가이드.md)와 [T-005 테이블 구현 및 변경 이력](../데이터베이스/Django_PostgreSQL_테이블_구현_변경이력_20260730.md) |
| T-022 문의·증상 제출 수직 흐름 | [T-022 증상 제출 API 설계 및 계약 Gate](Django_REST_API_문의_증상제출_구현_검증_인계서.md) |
| T-023 Workflow·이력·멱등성 | [API Runtime 구현 상태](../../../api/runtime_implementation_status.md)와 아래 8.1절 |

구체적인 우선순위와 완료 수치는 위 업무 문서와 승인된 WBS에서 관리한다.
이 공통 가이드에는 별도의 작업 Queue를 만들어 같은 상태를 이중 관리하지
않는다.

### 8.1 Workflow 현재 유효 Gap과 후속 구현 Gate

2026-07-27 착수 전 문서에 기록됐던 “Engine·Model·Migration 없음”은
현행 사실이 아니다. 현재 저장소에는 다음 기반이 존재한다.

- State Machine 계약 `v1.0.0 TEAM_APPROVED`
- Fail-closed Loader·Validator
- State Machine·Guard Evaluator·Allowed Action Resolver
- 상태 이력·멱등성 Model과 번호 Migration
- Row Lock·Transaction을 사용하는 Repository·Service
- 문의 생성 `START_INQUIRY`와 취소 `CANCEL_INQUIRY` Runtime

따라서 남은 Workflow 작업은 위 기반을 다시 만드는 것이 아니라, 아직
Runtime으로 노출되지 않은 행동을 동일 경계로 연결하고 검증하는 것이다.

| 현재 유효 Gap | 구현 Gate | 완료 증거 |
| --- | --- | --- |
| Runtime 행동 Endpoint 부족 | 행동별 Method·Path·요청·응답을 OpenAPI에 먼저 확정하고 URL·View·Serializer·Service 연결 | OpenAPI Coverage와 행동별 API 테스트 |
| OpenAPI-only 문진·자가조치 API | `PATCH /inquiries/{id}/questionnaire`, `POST /inquiries/{id}/action-results`를 Model·Transaction과 함께 구현 | 같은 문의 누적·Rollback·PostgreSQL Smoke |
| 상태·멱등성의 행동별 적용 | `state_version`, `Idempotency-Key`, 상태 이력, 저장된 Replay 응답을 모든 상태 변경 Service에 적용 | 같은 Key Replay 1회, 다른 Payload 409, stale version 409 |
| 권한·존재 숨김 | 역할 부족 403과 타 사용자 리소스 404를 구분 | 고객 본인·기사 배정·타 사용자 통합 테스트 |
| Client 소비 | Web·Mobile이 `allowed_actions`와 최신 409 Snapshot을 소비 | 입력 보존·새 Key 재시도·중복 이력 0 |
| AI 효과 경계 | AI는 이벤트 후보만 반환하고 Backend Guard를 거쳐 적용 | DB 직접 변경 0, Timeout·stale 결과 안전 차단 |
| PostgreSQL 동시성 | SQLite 단위 검증과 분리해 실제 Row Lock·Rollback·Unique 충돌 확인 | 빈 DB Migration·동시 요청·전체 회귀 |

후속 구현에서도 다음 금지사항을 유지한다.

- PM State 계약 값을 Backend 코드에 복제하거나 임의 변경하지 않는다.
- View·Serializer·Model `save()`에서 상태를 직접 변경하지 않는다.
- 상태 이력 없이 현재 상태만 갱신하지 않는다.
- stale version과 동일 Key의 다른 Payload를 신규 정상 요청으로 처리하지
  않는다.
- SQLite 테스트만으로 PostgreSQL 동시성 완료를 주장하지 않는다.
- AI 결과가 State Machine Guard 없이 문의 상태를 직접 변경하게 하지
  않는다.

## 9. Request·Exception 로그 보안

현재 Request 로그는 민감값을 나중에 마스킹하는 방식이 아니라 처음부터
안전한 필드만 기록하는 Allowlist 방식이다.

| 로그 항목 | 정책 |
| --- | --- |
| Method·Route Template·Status·Duration | 기록 허용 |
| Correlation ID | 요청·응답·구조화 로그 연결용으로 기록 |
| Query String·Authorization·Cookie | 기록 금지 |
| Request·Response Body | Password·전화번호·고객 원문·Token 유출 방지를 위해 기록 금지 |
| Exception | Type만 허용하고 Message·Stack은 외부 JSON 로그에서 제외 |

요청 로그 Middleware, JSON Formatter, Request Context Filter, 전역 예외
Handler를 대상으로 한 2026-07-31 집중 검증은 `14 passed`였다. 이 결과는
현재 Request·Exception 경로에만 적용되며 T-024의 AI·RAG·계정 변경·업무
감사 전체가 구현됐다는 뜻이 아니다.

새 `logger.*` 호출을 추가할 때는 같은 변경에 Token·PII·고객 원문
비노출 테스트를 추가한다. AI Prompt·Evidence 원문·DSN·환경변수 전체를
로그 인자로 넘기지 않고, 필요한 경우 업무 식별자·모델 버전·안전한
상태 코드·처리 시간·Correlation ID만 기록한다.

## 10. 인계 사항

| 대상 | 전달 항목 | 다음 행동 | 완료 확인 | 현재 상태 |
| --- | --- | --- | --- | --- |
| PM | Method·Path·DTO·오류 계약, State 영향 Endpoint, 미구현 범위 | State 업무 규칙과 API 경계를 대조하고 비작성자 리뷰 후 PR 병합 | 계약·State 불일치 0건 또는 재현 사례·결정 기록 | 검토 미요청 또는 증거 미확인 |
| Data·QA | OpenAPI 변경, Contract·PostgreSQL 검증 명령, 정상·오류 Fixture와 최신 테스트 결과 | 계약·DB 테스트를 같은 변경 기준으로 재현 | 실행 명령·환경·결과가 기록되고 핵심 테스트 통과 | 검토 미요청 또는 증거 미확인 |
| AI·RAG | Backend↔AI Request·Response Schema, Timeout·Fallback·오류 경계 | AI Schema와 Adapter 필드·Enum·실패 응답을 대조 | Schema 검증과 정상·누락·실패 Fixture 통과 | 검토 미요청 또는 증거 미확인 |
| Web | Web용 Method·Path·목록 DTO·오류·`409` 예시 | Web Mock을 동일 계약으로 교체하고 호환성 차이를 사례로 보고 | Web 요청·응답과 오류 처리가 OpenAPI와 일치 | Runtime별 인계 전 또는 증거 미확인 |
| Mobile | Mobile용 인증 Header·문의 DTO·상태·`allowed_actions`·오류 예시 | Mobile Mock을 동일 계약으로 교체하고 호환성 차이를 사례로 보고 | Mobile 요청·응답과 오류 처리가 OpenAPI와 일치 | Runtime별 인계 전 또는 증거 미확인 |

각 인계에는 Runtime 구현 파일과 변경 Migration, 역할·객체 범위,
상태·동시성·멱등성 영향, 실행 명령, 해당 변경에서 다시 실행한 테스트
결과와 의도적으로 미구현한 범위를 포함한다. source of truth에 기록된
기준의 재확정을 반복하지 않고, 소비자는 OpenAPI와 Runtime의 동일
버전을 사용한다.

## 11. 유지보수 원칙과 완료 조건

- Method·Path·Schema·오류가 바뀌면 OpenAPI와 오류 코드 계약을 먼저
  갱신하고 같은 변경 묶음에서 Runtime·테스트·사람용 명세를 맞춘다.
- Endpoint 수와 실행 수치는 이 문서에 반복 저장하지 않고
  [API Runtime 구현 상태](../../../api/runtime_implementation_status.md)의
  최신 Route·실행 증거를 따른다.
- 역할·State·AI Schema의 책임 경계를 바꾸는 결정은 해당 기계 계약과
  결정 기록에 남긴다.
- API 작업은 OpenAPI 문법·Coverage, 실제 PostgreSQL, 정상·오류·권한,
  로그 민감정보 비노출 검증을 모두 통과해야 작성자 검증 완료로 표시한다.
- 비작성자 재현과 소비자 호환성 검토, PM 병합 증거가 확인된 뒤에만 팀
  기준선 반영 완료로 표시한다. 보조 상태 코드는 이 완료 조건을 대체하지
  않는다.
