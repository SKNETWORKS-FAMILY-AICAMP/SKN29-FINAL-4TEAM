# AI Contracts

Backend와 AI 서비스 사이의 요청·응답 JSON Schema 단일 진실원칙(SSOT)이다.

## 현재 버전

- 계약 버전: `1.1.0`
- JSON Schema: Draft 2020-12
- 분석 Endpoint: `POST /api/v1/ai/analyze`
- 추가 속성: 모든 공개 요청·응답에서 금지

각 `*.schema.json`은 `$id`와 `x-contract-version`을 가진다. 계약을 변경할
때는 Runtime Pydantic 모델, 실제 JSON 예시, 검증 테스트와 이 문서를 같은
Commit에서 갱신한다.

## 추적·멱등·상태 버전

모든 AI 작업 계약은 다음 필드를 최상위에 둔다. 별도 `trace_context`는
공개 요청·응답에 중복 노출하지 않는다.

- `inquiry_id`: Backend가 발급한 Public UUID. 내부 정수 PK와 업무 코드는 금지
- `correlation_id`: Backend → AI → 응답·오류·`X-Correlation-ID` Header 추적값
- `ai_request_id`: Backend가 발급하는 AI 호출 멱등 키. 같은 논리 요청 재전송 시 재사용
- `state_version`: 호출 시작 시점 버전. AI가 변경하지 않고 응답에 Echo

AI 응답의 `state_version`은 상태 전환 결과가 아니다. Backend가 현재 문의
버전과 다시 비교한 뒤 결과 적용 여부를 결정한다.

## 실행 결과

- `status`: `SUCCEEDED` 또는 `FALLBACK`
- `failure_stage`: `contracts/codes/ai-stages.yaml` 표준 코드 또는 `null`
- `retry_count`: AI 내부 실제 재시도 횟수, `0..1`

AI는 증상 구조화·안전 평가·사용 안내·근거 참조 또는 요약 초안만 반환한다.
업무 상태·권한·최종 EvidenceCard·DB 기록은 Backend가 담당한다.

## 오류 계약

`common/AIErrorResponse.schema.json`을 사용한다.

| 코드 | HTTP | retryable | 대표 Stage |
| --- | ---: | --- | --- |
| `AI-VALIDATION-01` | 400 또는 422 | false | `STRUCTURING` |
| `AI-FAILED-01` | 503 | false | `RETRIEVING` — Vector Store 필수 설정 누락 |
| `AI-FAILED-01` | 503 | true | `RETRIEVING` — 일시적 검색 Provider 오류가 내부 1회 재시도 후에도 지속 |
| `AI-FAILED-01` | 503 | false | `RETRIEVING` — 비일시적 검색 결과·검증 오류 |
| `AI-FAILED-01` | 503 | true | `FAILED` — 분류되지 않은 내부 실행 실패 |
| `AI-TIMEOUT-01` | 504 | true | `CANCELLED` |

오류 응답에도 사용 가능한 추적 식별자를 보존한다. 입력 원문, Prompt,
Stack Trace, Secret, 개인정보는 오류 상세에 포함하지 않는다.

정상적으로 검색을 완료했지만 근거가 0건이면 오류가 아니다. HTTP 200,
`status=FALLBACK`, `failure_stage=RETRIEVING`, 빈 `evidence_references`와
`PENDING_CONSULTATION`을 반환한다. Vector Store 설정이 없어 검색을 시작하지
못한 경우에는 같은 0건으로 처리하지 않고 HTTP 503과
`AI-FAILED-01`, `retryable=false`, `failure_stage=RETRIEVING`을 반환한다.

검색 Provider가 `ConnectionError`, `TimeoutError`, PostgreSQL
`OperationalError`·`InterfaceError` 계열의 일시적 오류를 반환하면 AI가
검색 Stage 안에서 최대 1회만 재시도한다. 두 번째 시도를 실제 시작한 경우
성공 응답 또는 최종 오류의 `retry_count=1`로 기록한다. 설정·Schema·정책
오류와 위험 우선 분기는 재시도하지 않는다. Backend 자동 재시도는 0회다.

## 디렉토리

- `requests/`: Backend → AI
- `responses/`: AI → Backend
- `common/`: 공통 하위 객체 및 오류 응답
- `examples/`: 정상·위험·근거 없음·검증 오류·Timeout·요약 예시

변경 이력은 [CHANGELOG.md](CHANGELOG.md)를 따른다.
