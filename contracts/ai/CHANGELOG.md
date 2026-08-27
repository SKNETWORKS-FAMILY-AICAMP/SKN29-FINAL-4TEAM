# AI Contract Changelog

## Consultation Handoff Envelope 2.0.0 - 2026-08-27

- 기존 무버전 v1 Handoff 요청과 명시적 `schema_version=2.0.0` 요청을 함께
  검증하는 `ConsultationHandoffRequest` Draft 2020-12 Schema 추가
- v2에 원래 분석 요청의 `state_version`, 실제 Handoff `routing_reason`,
  외부 공개용 nullable `context_synthesis`를 필수로 추가
- `PRE_SEND_HUMAN_REVIEW`를 금지하고 Danger·Fail-closed·Harness의
  상태/Fallback 조합을 Schema로 고정
- AI 내부 `source_ids`와 Provider 메타데이터를 외부 Brief에서 제거하고,
  Evidence Chunk 결속 규칙을 명시
- `HARNESS_ESCALATE` 권위를 `AIRun.validated_output_payload`의
  `fallback_reason_code × failure_stage` Crosswalk로 고정
- Human Review 거절 결속과 Backend 오류별 bounded retry 정책을 계약
  Metadata 및 예시로 추가

## 4.0.0 Routing clarification - 2026-08-26

- 공개 Schema 필드 추가 없이 danger, caution 검토 초안, general 자동 안내,
  Fail-closed 상담의 판독 순서와 조건을 명시
- 추가 문진 대기는 `CUSTOMER_INPUT_PENDING`으로 기존 흐름을 보존
- Danger 근거를 Safety Rule 본문 정합성으로, Replay 무호출을 Backend 결합
  검증 책임으로 명확화

## 4.0.0 - 2026-08-21

- `SymptomAnalysisResponse.model_code`를 필수 필드로 추가해 요청 제품과 응답
  판정 제품을 대조할 수 있게 함
- `fallback_reason_code`를 필수 nullable 필드로 추가하고 제품 미승인,
  No-Evidence, MCP 실패, 출력 Schema 실패와 미분류 Fallback을 분리
- Backend가 `failure_stage`만으로 제품 미승인이나 `NO_EVIDENCE`를 추정하지
  않도록 응답 Mapper 불변식 강화
- strict 응답 Schema에 필수 필드를 추가하는 호환성 파괴 변경이므로 계약 Major
  Version을 갱신

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
