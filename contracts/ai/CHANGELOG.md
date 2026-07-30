# AI Contract Changelog

## 1.1.0 - 2026-07-30

- 모든 Schema에 `$id`와 `x-contract-version` 추가
- `inquiry_id`, `correlation_id`, `ai_request_id`, `state_version` 최상위 전달·Echo 확정
- `status`, `failure_stage`, `retry_count` 실행 결과 계약 추가
- 비어 있던 공통 Schema 5종과 상담·기사 요청/응답 Schema 구체화
- `AIErrorResponse` 및 정상·위험·근거 없음·검증 오류·Timeout 예시 확정
- 공개 응답에서 내부 `trace_context`, `model_metadata`, `processing_traces` 제외

## 1.0.0 - 2026-07-29

- 최초 증상 분석 요청·응답 및 안전·근거 공통 객체 정의
