# AI Contract Changelog

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
