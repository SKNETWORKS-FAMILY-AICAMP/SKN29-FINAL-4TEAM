# Consultation Handoff Contract

AI 분석 응답 `4.0.0`과 별도로 관리하는 AI → Backend 내부 상담 Handoff
Envelope 계약이다. 기계 판독 SSOT는
`ConsultationHandoffRequest.schema.json`이다.

## 버전

- 기존 v1 Client payload는 `schema_version`이 없으며 Backend가 `1.0.0`으로
  정규화한다. 다른 v2 필드를 보고 버전을 추정하지 않는다.
- v2는 `schema_version=2.0.0`, `state_version`, `routing_reason`,
  `context_synthesis` 키를 모두 필수로 전송한다.
- 같은 `ai_request_id`로 저장된 v1 payload를 v2 payload로 바꾸어 재전송하지
  않는다.

### v1 호환 범위와 v2 강화 범위

v2의 강화 규칙은 기존 v1 요청에 적용하지 않는다. 두 버전은 최상위 공통
제약을 공유하지 않는 독립 객체 Schema로 검증한다.

| 항목 | 기존 v1 | v2 |
| --- | --- | --- |
| 배열 필드 6종 | 생략 가능, Backend가 빈 배열로 정규화 | 모두 필수 |
| 문진·도움 행동·근거·안전 메모·우선 확인·Chunk ID 개수 | 기존 계약대로 최대 개수 제한 없음 | 각각 `30/20/10/20/30/10` |
| `safety_level` | 비어 있지 않은 50자 이하 문자열 | `general`, `caution`, `danger`, `unknown` |
| `evidence[].page` | 키 생략 또는 `null` 허용 | 키는 필수, 값은 `null` 허용 |

배열 항목 자체의 문자열 길이, UUID 형식, 알 수 없는 필드 금지와 Evidence
Chunk 결속은 기존 v1에서도 유지한다. 이 호환 범위는 현재 AI
`ConsultationHandoffResult`와 Backend v1 Serializer가 정상 처리하던 요청을
새 v2 제한 때문에 거절하지 않기 위한 경계다.

## Handoff 분기와 합성 결과

| `routing_reason` | `context_synthesis.status` | `fallback_reason` |
| --- | --- | --- |
| `DANGER_HANDOFF` | `FALLBACK` | `DANGER_BYPASS` |
| `FAIL_CLOSED_CONSULTATION` | `SUCCEEDED` | `null` |
| `FAIL_CLOSED_CONSULTATION` | `FALLBACK` | `DANGER_BYPASS` 이외 허용 Enum |
| `HARNESS_ESCALATE` | `SUCCEEDED` | `null` |
| `HARNESS_ESCALATE` | `FALLBACK` | `DANGER_BYPASS` 이외 허용 Enum |
| 위 세 분기 | `context_synthesis=null` | 해당 없음 |

`PRE_SEND_HUMAN_REVIEW`는 최초 가이드 검토 시작점이며 실제 Handoff가 아니므로
허용하지 않는다. 알려진 합성 실패는 결정론적 `FALLBACK brief`를 전달한다.
예상하지 못한 합성 또는 AI 외부 DTO Mapper 실패만
`context_synthesis=null`로 축소한다.

## HARNESS_ESCALATE AIRun 권위

Backend는 HTTP 오류 응답의 `error.code`가 아니라 같은
`AIRun.validated_output_payload`의 다음 조합으로 Ledger-only 저장을 승인한다.

| `fallback_reason_code` | `failure_stage` | 1차 Backend 처리 |
| --- | --- | --- |
| `MCP_TOOL_FAILURE` | `VALIDATING` | Handoff 원장만 저장 |
| `OUTPUT_SCHEMA_INVALID` | `VALIDATING` | Handoff 원장만 저장 |
| `UNSPECIFIED_FALLBACK` | `VALIDATING` | Handoff 원장만 저장 |

실제 Backend 승인 Consultation이 생기기 전에는 상담 연결과
`ai_draft_summary` Projection을 수행하지 않는다. `NO_EVIDENCE`, 제품 미승인,
Danger처럼 기존 Backend 전환 근거가 있는 결과를 위 Ledger-only 조합으로
바꾸지 않는다.

## Human Review 거절

`FAIL_CLOSED_CONSULTATION` 거절 Handoff는 다음 조건을 모두 만족해야 한다.

- `HumanReview.inquiry_id == request.inquiry_id`
- `HumanReview.guidance.inquiry_id == request.inquiry_id`
- `HumanReview.source_ai_request_id == request.ai_request_id`
- `HumanReview.source_inquiry_state_version == request.state_version`
- `HumanReview.status_code=REJECTED`
- `HumanReview.decision_code=REJECT`

결정 요청의 `decision_correlation_id`와 원래 AI 분석 `correlation_id`가 같은
값일 필요는 없다. 거절만으로 Inquiry 상태를 바꾸거나 Consultation을 자동
생성하지 않는다.

## Evidence 및 외부 공개 제한

- `source_chunk_ids`는 `evidence[].chunk_id`와 순서까지 같아야 하며 중복을
  허용하지 않는다.
- `brief.evidence_based_findings[].source_chunk_ids`는 최상위
  `source_chunk_ids`의 부분집합이어야 한다.
- AI 내부 `source_ids`, Provider 호출 여부·모델·Prompt 버전·Token·Latency,
  Prompt 원문, 예외와 Stack Trace, 검색 점수와 Vector는 전송하지 않는다.
- Backend는 요청 전체를 엄격히 검증한다. 맥락 일부만 조용히 제거해 저장하지
  않는다.

## Backend 오류와 AI 재시도

전체 시도는 최초 1회와 재시도 1회, 최대 2회다.

| 조건 | 재시도 |
| --- | --- |
| `AI_HANDOFF_NOT_READY`, HTTP `429`, `500/502/503/504`, Network, Timeout | 최대 1회 |
| `AI_HANDOFF_STALE`, `AI_HANDOFF_EVIDENCE_REJECTED`, `DUPLICATE-EVENT-01`, `VALIDATION_ERROR`, `FORBIDDEN` | 금지 |
| 그 외 4xx | 금지 |

Backend가 요청을 거절한 뒤 같은 `ai_request_id`의 payload를 변경해 다시 보내지
않는다. 이 bounded retry는 영구 전달 보장이 아니다.

## 상담사 Projection

1차 구현은 `SUMMARY_ONLY`다. 구조화 객체를 상담사 공개 API에 추가하지 않고,
Backend가 기존 `ai_draft_summary`에 최대 4,000자의 일반 텍스트로 Projection한다.
실제 Consultation이 없는 `HARNESS_ESCALATE`와 Human Review 거절 원장은
Projection하지 않는다.
