# AI Contract Changelog

## 3.0.0 - 2026-08-10

- `SafetyAssessment.matched_safety_rule_ids`를 필수 배열로 추가
- 안전 설정의 내부 키와 Backend Guard가 소비할 안정 Rule ID를 분리
- 위험·주의 규칙의 안정 ID 형식과 중복을 Runtime 시작 시 검증
- 엄격한 응답 Schema에 필수 필드를 추가하는 호환성 파괴 변경이므로 계약
  Major Version을 갱신

## 2.0.0 - 2026-08-10

- 시스템 Canonical `correlation_id`를 일반 문자열에서 UUID로 제한
- 요청·응답·오류 JSON Schema, Pydantic 모델과 모든 공개 예시를 함께 정합화
- Body와 `X-Correlation-ID` Header에는 같은 UUID만 허용
- 비UUID 입력 검증 오류는 잘못된 값을 Echo하지 않고
  `correlation_id=null`로 반환
- 입력 범위를 좁히는 호환성 파괴 변경이므로 계약 Major Version을 갱신

## 2026-08-04 — 1.1.0 내부 재시도 Runtime 활성화

- 공개 Schema 변경 없이 기존 `retry_count=0..1` 의미를 Runtime에 연결
- 검색 Provider의 일시적 연결·Timeout 오류만 최대 1회 재시도
- 설정·Schema·정책 오류와 위험 우선 분기는 재시도 대상에서 제외
- 재시도 소진 검색 실패 예시를 `retry_count=1`로 갱신

## 2026-08-04 — 1.1.0 검색 결과·장애 의미 명확화

- 공개 Schema 필드 변경 없이 정상 검색 0건과 Vector Store 설정 누락을 분리
- 정상 0건은 HTTP 200 `FALLBACK`, 설정 누락은 HTTP 503
  `AI-FAILED-01`·`retryable=false`로 예시 고정
- 실제 검색 실패는 HTTP 503 `AI-FAILED-01`·`retryable=true`, Timeout은 기존
  HTTP 504 계약을 유지
- `vector-not-configured-error.json`, `retrieval-failed-error.json` 예시 추가

## 2026-07-30 — 1.1.0 Runtime parity correction

- `inquiry_id`를 Backend Public UUID로 강제
- 요청 배열 개수와 항목 문자열 길이를 Pydantic Runtime에도 동일 적용
- 오류 응답의 `success=false`, 오류 코드, 메시지 길이, 실패 Stage를 Runtime에서 강제
- 안전 우선순위와 근거 검증 상태를 Runtime Enum으로 강제
- 다중 페이지 근거 보존을 위한 선택적 `page_refs` 추가

## 1.1.0 - 2026-07-30

- 모든 Schema에 `$id`와 `x-contract-version` 추가
- `inquiry_id`, `correlation_id`, `ai_request_id`, `state_version` 최상위 전달·Echo 확정
- `status`, `failure_stage`, `retry_count` 실행 결과 계약 추가
- 비어 있던 공통 Schema 5종과 상담·기사 요청/응답 Schema 구체화
- `AIErrorResponse` 및 정상·위험·근거 없음·검증 오류·Timeout 예시 확정
- 공개 응답에서 내부 `trace_context`, `model_metadata`, `processing_traces` 제외

## 1.0.0 - 2026-07-29

- 최초 증상 분석 요청·응답 및 안전·근거 공통 객체 정의
