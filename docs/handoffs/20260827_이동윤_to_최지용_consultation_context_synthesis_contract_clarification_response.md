# Consultation Context Synthesis Backend 연동 사전 협의 회신

- 작성일: 2026-08-27
- 발신: 이동윤
- 수신: 최지용
- 공동 검토 필요: 윤승혁(Harness·Handoff)
- 회신 대상: `20260827_최지용_to_이동윤_consultation_context_synthesis_contract_clarification_request.md`
- AI 확인 기준: `dongyoon` / `faf1688e8eed4bae0d3c9ca0e6d1d3b132eb9f6f`
- Backend 검토 기준: `main` / `62c9ba98b8d5ee814f88d5e6e525399fa53e3603`

---

## 1. 결론

검토 의견대로 현재 상태에서 Backend v2 구현과 AI Handoff Client allowlist 개방을 바로 진행하지 않겠습니다.

기존 요청서는 구현 방향을 설명한 자연어 제안서였으며, 실제 서비스 간 SSOT로 사용할 기계 판독 Schema, 외부 전송 DTO, 오류별 재시도 계약과 Backend 승인 Run 판정이 아직 없었습니다. 따라서 현재 상태를 다음과 같이 유지합니다.

```text
ready_for_ai_allowlist=NO
status=HOLD_CONTRACT_REQUIRED
```

다만 아래 정책은 이번 회신으로 방향을 확정합니다.

- Handoff 전용 Envelope는 AI 분석 계약 `4.0.0`과 분리한다.
- 새 Handoff Envelope 버전은 `2.0.0`으로 한다.
- 실제 상담 Handoff 사유는 v2 최상위 `routing_reason`으로 항상 보존한다.
- 알려진 맥락정리 실패는 결정론적 `FALLBACK brief`를 사용한다.
- 예상하지 못한 맥락정리·Mapper 실패는 `context_synthesis=null`로 기본 Handoff를 보존한다.
- AI 내부 `source_ids`와 Provider 실행 메타데이터는 Backend 전송 DTO에서 제외한다.
- 1차 상담사 Projection은 `SUMMARY_ONLY`로 제한한다.
- v1 저장 후 같은 `ai_request_id`로 v2를 보내는 업그레이드는 허용하지 않는다.
- 기존 bounded retry를 1차 연결에 유지하되, 영구 전달 보장으로 표현하지 않는다.

`HARNESS_ESCALATE`와 Human Review 거절을 Backend가 어떤 권위 있는 상담 경로로 승인할지는 아래 미결 항목에서 공동 확정이 필요합니다.

---

## 2. Handoff 전용 계약과 소유권

### 2.1 계약 버전

- AI 공개 분석 계약: 기존 `4.0.0` 유지
- AI → Backend 상담 Handoff Envelope: `2.0.0`
- v1과 v2는 Backend가 명시적으로 분기하며, 필드 존재 여부로 버전을 추정하지 않는다.

### 2.2 SSOT 경로

기계 판독 계약은 다음 경로에 추가하는 방향으로 진행합니다.

```text
contracts/ai/handoff/ConsultationHandoffRequest.schema.json
contracts/ai/examples/handoff/v1-request.json
contracts/ai/examples/handoff/v2-succeeded-request.json
contracts/ai/examples/handoff/v2-fallback-request.json
contracts/ai/examples/handoff/v2-null-context-request.json
```

Schema에는 JSON Schema Draft `2020-12`, `$id`, `x-contract-version`, `additionalProperties=false`를 적용합니다.

현재 이 파일들은 아직 생성되지 않았습니다. Schema와 예제가 같은 Commit으로 추가되고 Backend 검수를 통과하기 전까지 이 회신문만으로 v2 구현 완료나 계약 동결 완료를 선언하지 않습니다.

### 2.3 역할

| 범위 | 주관 | 검수 |
| --- | --- | --- |
| Handoff v2 필드 의미·Schema·예제 | 이동윤 | 최지용·윤승혁 |
| Backend Serializer·저장·Replay·Projection | 최지용 | 이동윤·윤승혁 |
| AI 외부 DTO Mapper·`state_version` 전파·Client allowlist·재시도 | 윤승혁 | 이동윤·최지용 |
| 실행 환경 enable·Base URL·Token·callback canary | 배포 환경 담당 | 윤승혁·최지용 |

AI 내부 Agent 결과를 그대로 HTTP payload에 직렬화하지 않습니다.

---

## 3. Handoff v2 최상위 계약

v2는 기존 v1 필드에 아래 필드를 추가합니다.

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `schema_version` | 문자열 | 필수, 정확히 `2.0.0` |
| `state_version` | 정수 | 필수, 원래 AI 분석 요청의 값, 1 이상 |
| `routing_reason` | Enum | 필수, 실제 상담 Handoff 사유 |
| `context_synthesis` | 객체 또는 `null` | 필수 키, 예상하지 못한 합성 실패에만 `null` 허용 |

`routing_reason`은 아래 세 값만 허용합니다.

- `DANGER_HANDOFF`
- `FAIL_CLOSED_CONSULTATION`
- `HARNESS_ESCALATE`

`PRE_SEND_HUMAN_REVIEW`는 최초 가이드 검토 단계이므로 v2 Handoff Schema에서 허용하지 않습니다.

`routing_reason`을 `context_synthesis` 바깥에도 두는 이유는 `context_synthesis=null`이어도 Backend가 실제 Handoff 분기를 검증할 수 있게 하기 위해서입니다. 외부 DTO에서는 중첩 `context_synthesis.routing_reason`을 제거해 중복 값을 만들지 않습니다.

---

## 4. 외부 `context_synthesis` DTO

외부 DTO에는 상담 업무에 필요한 필드만 포함합니다.

```json
{
  "status": "SUCCEEDED",
  "fallback_reason": null,
  "brief": {
    "safety_constraints": [],
    "issue_summary": {"text": "상담사가 먼저 확인할 핵심 문제"},
    "customer_reported_facts": [],
    "attempted_actions_and_outcomes": [],
    "unresolved_questions": [],
    "evidence_based_findings": [],
    "consultant_priority_checks": [],
    "uncertainty_notes": []
  }
}
```

외부 DTO에서 제외하는 값은 다음과 같습니다.

- `provider_called`
- `model_name`
- `prompt_version`
- `tokens_used`
- `latency_ms`
- `should_use_deterministic_handoff`
- Provider Prompt와 원문 응답
- Exception과 Stack Trace
- 검색 점수와 Embedding Vector
- AI 내부 `source_ids`

### 4.1 Brief 규칙

- `context_synthesis`가 객체이면 `brief`는 항상 필수다.
- `issue_summary.text`는 항상 비어 있지 않아야 한다.
- 나머지 목록은 빈 배열을 허용한다.
- 일반 문장은 외부 DTO에서 `text`만 가진다.
- Evidence 기반 문장만 `text`와 `source_chunk_ids`를 가진다.
- `source_chunk_ids`는 최상위 `source_chunk_ids`의 부분집합이어야 한다.
- 알려지지 않은 필드는 거절한다.

AI 내부 `source_ids`는 한 번의 합성 실행에서 원문 Source를 선택·그룹화하기 위한 임시 식별자입니다. Backend가 권위 있게 해석할 수 있는 ID가 아니므로 외부 계약에 포함하지 않습니다.

---

## 5. 상태·Fallback·라우팅 조합

| 최상위 `routing_reason` | `context_synthesis.status` | `fallback_reason` | `brief` |
| --- | --- | --- | --- |
| `DANGER_HANDOFF` | `FALLBACK`만 허용 | `DANGER_BYPASS`만 허용 | 필수 |
| `FAIL_CLOSED_CONSULTATION` | `SUCCEEDED` | `null` | 필수 |
| `FAIL_CLOSED_CONSULTATION` | `FALLBACK` | 허용 Fallback Enum | 필수 |
| `HARNESS_ESCALATE` | `SUCCEEDED` | `null` | 필수 |
| `HARNESS_ESCALATE` | `FALLBACK` | 허용 Fallback Enum | 필수 |
| 위 세 Handoff 사유 | `context_synthesis=null` | 해당 없음 | 해당 없음 |

허용 Fallback Enum은 다음과 같습니다.

- `CONFIGURATION`
- `PROVIDER_TIMEOUT`
- `PROVIDER_UNAVAILABLE`
- `OUTPUT_INVALID`
- `REFUSED`
- `DANGER_BYPASS`
- `INPUT_TOO_LARGE`
- `INPUT_NOT_ELIGIBLE`
- `SAFETY_NOT_VERIFIED`
- `RUNTIME_PRODUCT_NOT_APPROVED`

추가 규칙은 다음과 같습니다.

- `SUCCEEDED`이면 `fallback_reason=null`이어야 한다.
- `FALLBACK`이면 `fallback_reason`이 반드시 있어야 한다.
- `DANGER_BYPASS`는 `DANGER_HANDOFF`에서만 허용한다.
- `DANGER_HANDOFF`에서는 Provider 성공 결과를 허용하지 않는다.
- `PRE_SEND_HUMAN_REVIEW`는 Handoff v2 요청 자체를 거절한다.

---

## 6. 맥락정리 실패와 요청 원자성

기존 Handoff를 보존한다는 원칙은 **AI 내부 맥락정리 실패가 기본 Handoff 생성을 막지 않는다**는 의미로 한정합니다. Schema·PII·식별자·Evidence가 잘못된 외부 요청까지 Backend가 저장해야 한다는 의미는 아닙니다.

처리 순서는 다음과 같습니다.

```text
기본 Handoff 생성
→ 맥락정리 실행
   ├─ 성공: SUCCEEDED brief
   ├─ 알려진 실패·우회: FALLBACK 결정론적 brief
   └─ 예상하지 못한 예외: context_synthesis=null
→ 외부 DTO Mapper가 기본 Handoff와 맥락을 각각 검증
   ├─ 맥락만 Mapper 검증 실패: 맥락을 null로 바꾸고 기본 Handoff 유지
   └─ 기본 Handoff 검증 실패: 전송 중단
→ Backend는 도착한 v2 전체를 엄격하게 검증
```

Backend까지 도착한 요청에 다음 문제가 있으면 전체 요청을 거절하고 저장하지 않습니다.

- DTO 또는 unknown-field 오류
- PII 잔존
- Inquiry·Correlation·AI Request·Model·State 불일치
- 승인되지 않은 AIRun
- 승인되지 않은 Evidence
- 동일 Idempotency Key의 다른 payload

Backend가 잘못된 맥락을 조용히 폐기하고 나머지만 저장하는 방식은 사용하지 않습니다. AI 전송 전 Mapper가 `context_synthesis=null`로 안전하게 축소하는 책임을 가집니다.

Backend 거절 후 다른 payload로 자동 재전송하는 방식도 사용하지 않습니다. 동일 `ai_request_id`의 payload 의미가 호출 도중 바뀌는 것을 방지하기 위해서입니다.

---

## 7. 권위 있는 AIRun과 오래된 결과

### 7.1 공통 검증 규칙

Handoff는 최소한 아래 값을 같은 AIRun과 정확히 대조해야 합니다.

- `inquiry_id`
- `correlation_id`
- `ai_request_id`
- `state_version == AIRun.input_payload.state_version`
- `model_code`
- 허용된 AI Task Type과 종료 상태

`state_version`을 Handoff 수신 시점의 현재 Inquiry 버전과 단순 비교하지 않습니다. AI 결과 적용 뒤 Inquiry 버전이 증가했을 수 있기 때문입니다.

`FAILED` 상태의 AIRun을 종료 상태라는 이유만으로 자동 승인하지 않습니다. 검증된 AI 결과 또는 Backend의 승인된 상담 전환 근거가 없는 실패 Run은 Handoff 권위가 없습니다.

### 7.2 Backend 승인 근거

다음 경로는 기존 Backend 근거와 결속할 수 있습니다.

- `DANGER_HANDOFF`: 같은 `ai_request_id`의 `DANGER_DETECTED` 적용 이력
- 제품 미승인 Fallback: `PRODUCT_VALIDATION_FAILED` 적용 이력
- No Evidence: `NO_EVIDENCE` 적용 이력
- AI Timeout: `AI_PROCESSING_TIMEOUT` 적용 이력
- Human Review 거절: 같은 Inquiry·AI Run에 결속된 `HumanReview.REJECTED` 결정

`HARNESS_ESCALATE`의 MCP·Harness·출력 검증 실패는 현재 별도의 Backend State Event가 없습니다. 이 실패를 `NO_EVIDENCE`로 바꾸지는 않습니다.

이 항목은 아래 두 안 중 하나를 윤승혁·최지용과 확정해야 합니다.

1. `AI_PROCESSING_FAILED`와 같은 별도 Backend State Event를 추가하고 같은 `ai_request_id` TransitionHistory를 권위로 사용한다.
2. Handoff 원장 저장은 허용하되, Backend 상담 상태 또는 고객 상담 요청이 실제로 확정되기 전에는 Consultation에 연결하거나 상담사 초안을 갱신하지 않는다.

안전하고 추적 가능한 단일 기준을 위해 1안을 우선 권고합니다. 다만 State Machine·오류 매핑 범위가 늘어나므로 PM·Backend 승인 전 확정 구현하지 않습니다.

### 7.3 과거 Run과 Replay

- 권위 검증을 통과한 과거 Handoff는 감사 원장으로 저장할 수 있다.
- 더 최신의 권위 있는 Handoff가 존재하면 과거 Handoff는 현재 Consultation의 `ai_draft_summary`를 덮지 않는다.
- 과거 Handoff Replay는 기존 원장만 반환하며 Projection을 다시 갱신하지 않는다.
- 같은 `ai_request_id`와 같은 payload는 기존 멱등 Replay를 유지한다.
- 같은 `ai_request_id`인데 payload가 다르면 `DUPLICATE-EVENT-01`로 거절한다.
- 같은 `ai_request_id`로 v1을 저장한 뒤 v2로 업그레이드하지 않는다. v2는 전환 이후 생성되는 새 AI Request부터 사용한다.

---

## 8. Evidence 결속

최상위 Handoff Evidence는 다음 조건을 모두 만족해야 합니다.

1. 같은 AIRun의 검증 완료 `validated_output_payload.evidence_references`에 존재
2. `chunk_id`, 문서 제목, Page 등 식별 정보가 같은 Run의 값과 일치
3. Backend의 활성·검증 `AIChunkCrosswalk`와 문의 제품에 일치
4. Backend가 검증·저장한 Evidence 범위를 벗어나지 않음

`brief.evidence_based_findings[].source_chunk_ids`는 검증된 최상위 Handoff Evidence의 부분집합만 허용합니다.

맥락정리 결과는 계속 `AI 상담 초안`으로 취급합니다. `source_chunk_ids`가 있더라도 이를 새로운 EvidenceCard, 확정 사실 또는 진단으로 승격하지 않습니다.

---

## 9. 오류와 재시도 계약

현재 모든 `409`를 같은 방식으로 재시도하는 동작은 변경해야 합니다. 아래 코드를 Handoff 전용 Error Registry에 추가하는 방향을 제안합니다.

| 상황 | 제안 HTTP | 제안 `error.code` | AI 재시도 |
| --- | ---: | --- | --- |
| matching AIRun이 아직 종료·저장되지 않음 | 409 | `AI_HANDOFF_NOT_READY` | 1회 허용 |
| 오래됐거나 승인되지 않은 AIRun | 409 | `AI_HANDOFF_STALE` | 금지 |
| 같은 `ai_request_id`의 다른 payload | 409 | `DUPLICATE-EVENT-01` | 금지 |
| 동일 AIRun·Crosswalk와 맞지 않는 Evidence | 422 | `AI_HANDOFF_EVIDENCE_REJECTED` | 금지 |
| DTO·unknown field·PII 오류 | 422 | `VALIDATION_ERROR` | 금지 |
| 내부 Token 불일치 | 403 | `FORBIDDEN` | 금지 |
| Backend 일시 불가 | 503 | `AI_HANDOFF_BACKEND_UNAVAILABLE` | 1회 허용 |
| Network·Timeout | 해당 응답 없음 | AI Transport 분류 | 1회 허용 |
| `429` | 429 | Backend 표준 Rate Limit 코드 | 1회 허용 |

제안된 신규 Error Code의 최종 명칭은 Backend Error Registry 규칙에 맞춰 최지용 검수 후 고정합니다. AI Client는 HTTP 상태만 보지 않고 고정 `error.code`를 함께 확인합니다.

전체 Handoff 전달 시도는 기존과 동일하게 최초 1회와 bounded retry 1회, 총 최대 2회로 제한합니다. 분석 API의 공개 `retry_count`와 Handoff Background Delivery 재시도 횟수는 합산하지 않습니다.

---

## 10. 상담사 Projection

1차 구현 범위는 `SUMMARY_ONLY`로 확정합니다.

- 기존 `Consultation.ai_draft_summary`와 상담사 상세 응답 위치를 유지한다.
- 구조화 `context_synthesis`를 상담사 공개 API에 추가하지 않는다.
- Web 항목별 UI 변경을 이번 최소 구현에 포함하지 않는다.
- 원본 구조화 v2 payload는 기존 `sanitized_payload`에 저장한다.
- `context_synthesis=null`이면 기존 v1 요약 생성 방식을 유지한다.

새 brief를 `ai_draft_summary`로 만들 때 우선순위는 다음과 같습니다.

1. 안전 제한
2. 핵심 문제 요약
3. 상담사 우선 확인 항목
4. 고객이 보고한 사실
5. 이미 시도한 조치와 결과
6. 미확인 질문
7. 근거 기반 확인 사항
8. 불확실성 메모

최대 길이는 기존 상담사 응답 계약에 맞춰 4,000자로 제한합니다. 길이를 초과하면 낮은 우선순위 항목부터 결정론적으로 제외하고 마지막에 `…(이하 생략)`을 표시합니다. HTML을 만들지 않고 일반 텍스트로 저장하며, Web은 기존 텍스트 렌더링·escaping 규칙을 유지합니다.

`STRUCTURED` Projection은 Web 담당자·권한·표시 계약을 별도 승인한 뒤 후속 작업으로 진행합니다.

---

## 11. 전송 신뢰성과 활성화 시점

1차 구현의 전송 정책은 다음과 같습니다.

```text
delivery_reliability_policy=BEST_EFFORT_BOUNDED_RETRY
maximum_attempts=2
durable_outbox=DEFERRED
reconciliation=DEFERRED
```

이는 기존 Handoff 경로와 같은 제한된 신뢰성 수준입니다. 두 번의 전송이 모두 실패하면 구조화 로그와 Telemetry를 남기지만 자동 영구 재처리를 보장하지 않습니다.

따라서 1차 코드·표적 테스트가 통과해도 운영상 `전달 보장 PASS`로 표시하지 않습니다. Outbox·Reconciliation·운영 알림은 별도 신뢰성 작업으로 분리합니다.

`AI_HANDOFF_BACKEND_ENABLED=true` 전환은 다음 순서를 모두 마친 통합환경에서만 수행합니다.

1. Backend가 v1·v2 동시 수신을 배포
2. AI 외부 DTO·Client allowlist·오류별 재시도 반영
3. 양쪽 표적 테스트 통과
4. 보호된 Base URL·공유 Token 주입
5. AI Process 재시작
6. 동일 Inquiry callback canary 및 저장·Replay 확인

공동 E2E가 통과하기 전 운영 활성 상태는 유지하지 않습니다.

---

## 12. Branch와 구현 기준 Commit

현재 `dongyoon@faf1688e...`와 `main@62c9ba98...`는 서로 직접 ancestor 관계가 아니므로 두 SHA 중 하나를 v2 최종 구현 기준으로 지정하지 않습니다.

진행 순서는 다음과 같습니다.

1. 이동윤 Branch에 최신 main을 동기화
2. Handoff v2 JSON Schema·예제·Parity 테스트 Commit 생성
3. 최지용·윤승혁이 해당 40자리 Commit 검수
4. 검수된 Commit을 Backend 및 Handoff Client 구현 기준으로 고정

따라서 현재 값은 다음과 같습니다.

```text
target_commit=PENDING_MAIN_SYNC_AND_CONTRACT_FREEZE_COMMIT
```

---

## 13. 공동 확정이 필요한 미결 항목

### 필수 미결

1. `HARNESS_ESCALATE`의 Backend 권위
   - 신규 `AI_PROCESSING_FAILED` State Event 사용 여부
   - 또는 원장 저장 후 실제 상담 상태 확정 시에만 Projection하는 방식
2. Human Review 거절과 Handoff의 정확한 결속 키
   - Inquiry·AI Run·Review·State Version 중 필수 조합
3. 제안 Error Code 명칭과 Backend Error Registry 반영

### 후속으로 분리

- Durable Outbox
- 실패 Handoff Reconciliation
- 운영 알림
- 구조화 상담사 API
- Web 항목별 UI

후속 항목은 1차 v2 Serializer·저장 구현을 막지 않지만, 실행하지 않은 상태에서 운영 전달 보장이나 전체 서비스 PASS를 선언하지 않습니다.

---

## 14. 최지용 요청 형식에 대한 회신

```text
contract_owner=이동윤(필드 의미·Schema), 최지용(Backend 검수), 윤승혁(외부 DTO·전송)
handoff_envelope_version=2.0.0
contract_schema_path=contracts/ai/handoff/ConsultationHandoffRequest.schema.json (아직 미생성)
context_failure_policy=알려진 실패는 FALLBACK 결정론적 brief, 예상하지 못한 합성·Mapper 실패는 context_synthesis=null, Backend 외부 검증 실패는 전체 거절
null_fallback_routing_matrix=PRE_SEND 제외, DANGER는 FALLBACK+DANGER_BYPASS, FAIL_CLOSED/HARNESS는 SUCCEEDED 또는 FALLBACK, null은 예상하지 못한 합성·Mapper 실패만 허용
authoritative_airun_rule=동일 Inquiry·Correlation·AI Request·입력 state_version·Model 및 Backend 승인 상담 근거 결속
latest_run_policy=과거 유효 원장은 저장 가능하나 최신 Consultation Projection을 덮지 않음, 같은 ai_request_id v1→v2 업그레이드 금지
evidence_binding_rule=동일 AIRun validated Evidence와 Backend 검증 Crosswalk에 결속, nested Chunk는 최상위 검증 Evidence의 부분집합
source_id_authority=AI_INTERNAL_ONLY_NOT_TRANSMITTED
error_retry_matrix=AI_HANDOFF_NOT_READY·429·503·Network·Timeout만 bounded retry, stale·duplicate·Evidence·DTO·PII·권한 오류는 재시도 금지
consultant_projection=SUMMARY_ONLY
ai_public_dto_owner=윤승혁 구현, 이동윤 계약 의미, 최지용 Backend 검수
handoff_client_owner=윤승혁
delivery_reliability_policy=BEST_EFFORT_BOUNDED_RETRY, Outbox·Reconciliation 후속
target_commit=PENDING_MAIN_SYNC_AND_CONTRACT_FREEZE_COMMIT
remaining_open_issue=HARNESS_ESCALATE Backend 권위, Human Review 거절 결속 키, 신규 Error Code 명칭
ready_for_ai_allowlist=NO
status=HOLD_CONTRACT_REQUIRED
```

위 세 가지 필수 미결 항목을 공동 확정하고 실제 JSON Schema Commit을 검수한 뒤 Backend v2 구현과 AI allowlist 작업을 시작하겠습니다.
