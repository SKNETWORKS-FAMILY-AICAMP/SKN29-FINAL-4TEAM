# 상담 Handoff 2.0 AI 전송 구현 요청서

- 작성일: 2026-08-27
- 발신: 이동윤
- 수신: 윤승혁
- Backend 협업: 최지용
- 기준 Branch: `main`
- 기준 Commit: `9862bac3749118f81ab2770016f61630b0f189e2`
- Contract 정정 Commit: `be456afa56f12c602f44f37336e89466263032c1`
- Contract SSOT: `contracts/ai/handoff/ConsultationHandoffRequest.schema.json`
- 대상 Contract Version: `2.0.0`

---

## 1. 요청 요약

현재 AI 내부 Handoff에 붙어 있는 `context_synthesis`를 확정된 외부 Handoff
`2.0.0` DTO로 안전하게 변환하고 Backend Client가 전송하도록 구현해 주세요.

핵심은 다음 네 가지입니다.

1. 실제 상담 Handoff가 확정된 경우에만 v2 요청을 만듭니다.
2. 내부 합성 객체를 그대로 전송하지 않고 외부 전용 DTO로 축소합니다.
3. 맥락 합성이 실패해도 기존 상담 이관은 유지합니다.
4. Backend가 아직 준비되지 않았으므로 구현·단위 검증까지만 하고 실제
   활성화는 하지 않습니다.

현재 상태는 아래와 같습니다.

```text
contract_2_0=APPROVED_AND_MERGED
context_synthesis_internal_handoff=CONNECTED
ai_v2_external_mapper=NOT_STARTED
backend_v2_runtime=최지용 구현 대기
protected_http_e2e=NOT_RUN
AI_HANDOFF_BACKEND_ENABLED=false 유지
```

---

## 2. 호출 시점은 변경하지 않음

맥락정리 Agent와 v2 전송은 실제 Handoff가 만들어진 다음 세 분기에서만
사용합니다.

```text
DANGER_HANDOFF
FAIL_CLOSED_CONSULTATION
HARNESS_ESCALATE
```

다음 경우에는 호출하거나 전송하지 않습니다.

```text
AUTO_GUIDANCE
CUSTOMER_INPUT_PENDING
최초 PRE_SEND_HUMAN_REVIEW
Human Review 승인 후 자동답변
```

`PRE_SEND_HUMAN_REVIEW`는 상담 인계가 아니라 가이드 검토 시작점입니다. 기존
HITL 시작 동작을 v2 Handoff로 바꾸지 마세요.

---

## 3. 수정 요청 범위

윤승혁 주관 Handoff·Harness·Backend Handoff Client와 해당 테스트만 수정해
주세요.

```text
ai/app/orchestration/handoff/handoff_input.py
ai/app/orchestration/handoff/handoff_result.py
ai/app/orchestration/handoff/consultation_handoff_agent.py
ai/app/orchestration/handoff/__init__.py
ai/app/orchestration/harness/runner.py
ai/app/integrations/backend/handoff_client.py
ai/tests/unit/handoff/**
ai/tests/unit/harness/**
```

외부 v2 DTO와 Mapper는 Handoff 소유 경로에 새 파일로 분리해도 됩니다. 내부
`ConsultationHandoffResult`를 그대로 `model_dump()`하여 외부 계약으로 사용하는
방식은 피해주세요.

다음 공유·타인 경로는 이번 구현에서 수정하지 않는 것을 원칙으로 합니다.

```text
backend/**
contracts/ai/handoff/**
ai/app/orchestration/pipeline_router.py
ai/app/orchestration/pipeline_context.py
ai/app/orchestration/pipeline_result.py
ai/app/orchestration/pipelines/**
ai/app/orchestration/stages/**
ai/app/interfaces/http/routes/analysis_routes.py
ai/app/orchestration/hitl/**
ai/app/orchestration/agents/consultation_context_synthesis_agent.py
ai/app/generation/consultation_summary/**
ai/.env.example
Web/Mobile 공개 DTO 및 화면
```

현재 BackgroundTask는 `pipeline_result.handoff`만 전달하므로, `state_version`과
`routing_reason`은 가능하면 Handoff 입력·결과 안에서 완결해 주세요. 공유 HTTP
Route나 Pipeline 파일 수정이 불가피하면 먼저 변경 이유와 최소 수정 범위를
이동윤·최지용에게 알리고 편집자를 정한 뒤 진행해 주세요.

새 Runtime 환경변수나 버전 선택 변수를 임의로 추가하지 마세요. 이번 AI Client
구현은 v2 전송을 목표로 하며, 병합 순서는 Backend v2 수신 구현이 먼저입니다.

---

## 4. 상세 구현 요구사항

### 4.1 외부 v2 DTO를 별도로 구성

외부 요청에는 아래 최상위 필드를 정확히 포함해 주세요.

```text
schema_version=2.0.0
inquiry_id
correlation_id
ai_request_id
state_version
model_code
product_family
routing_reason
customer_symptom_summary
questionnaire_answers
self_help_actions
evidence
safety_level
safety_requires_consultation
safety_notes
escalation_reason
consultant_priority_checks
source_chunk_ids
context_synthesis
```

v2 배열 필드는 값이 없어도 모두 빈 배열로 명시합니다. 모든 외부 필드와
개수·길이·Enum·교차 필드 규칙은 확정 JSON Schema를 만족해야 합니다.

`state_version`은 Handoff 전송 시점의 현재 값이 아니라, 원래 AI 분석 요청에
들어온 `ctx.trace_context.state_version`을 사용해 주세요.

### 4.2 `routing_reason`을 합성 결과와 분리해 보존

현재 내부 `routing_reason`은 `context_synthesis` 안에만 들어 있습니다. 합성 중
예외가 나서 `context_synthesis=None`이 되면 외부 Handoff의 최상위 분기까지
사라질 수 있습니다.

다음 순서로 바꿔 주세요.

1. 실제 Handoff 원인을 기준으로 최상위 `routing_reason`을 먼저 결정합니다.
2. 결정한 값을 Handoff 입력·결과에 독립적으로 보존합니다.
3. 그 다음 Context Synthesis를 실행합니다.
4. 합성 또는 외부 맥락 변환이 실패해도 최상위 `routing_reason`은 유지합니다.

분기 매핑은 다음과 같습니다.

| 실제 Handoff 원인 | 외부 `routing_reason` |
| --- | --- |
| Danger 판정 | `DANGER_HANDOFF` |
| Human Review 거절 또는 가이드 없는 Fail-closed | `FAIL_CLOSED_CONSULTATION` |
| Harness·MCP·출력 검증 Escalate | `HARNESS_ESCALATE` |

`PRE_SEND_HUMAN_REVIEW`를 외부 값으로 만들지 마세요.

### 4.3 외부 `context_synthesis` 축소

외부 `context_synthesis`에는 아래 세 필드만 허용합니다.

```text
status
fallback_reason
brief
```

일반 Brief 문장은 `{text}`만 전송하고, Evidence 기반 문장만
`{text, source_chunk_ids}`를 전송합니다.

아래 내부 값은 절대 전송하지 마세요.

```text
source_ids
provider_called
model_name
prompt_version
tokens_used
latency_ms
should_use_deterministic_handoff
Provider Prompt 또는 원문 응답
Exception 또는 Stack Trace
검색 점수
Embedding Vector
```

상태 조합은 다음과 같이 유지합니다.

| `routing_reason` | `context_synthesis.status` | `fallback_reason` |
| --- | --- | --- |
| `DANGER_HANDOFF` | `FALLBACK` | `DANGER_BYPASS` |
| `FAIL_CLOSED_CONSULTATION` | `SUCCEEDED` | `null` |
| `FAIL_CLOSED_CONSULTATION` | `FALLBACK` | `DANGER_BYPASS` 외 허용값 |
| `HARNESS_ESCALATE` | `SUCCEEDED` | `null` |
| `HARNESS_ESCALATE` | `FALLBACK` | `DANGER_BYPASS` 외 허용값 |
| 세 분기 공통 | `null` | 해당 없음 |

알려진 Provider Timeout·거절·출력 검증 실패는 기존 Agent의 결정론적
`FALLBACK brief`를 사용합니다. 예상하지 못한 합성 예외나 외부 맥락 Mapper
예외만 `context_synthesis=null`로 축소합니다.

단, 식별자·상태 버전·최상위 분기·Evidence 같은 기본 Envelope 자체가 유효하지
않으면 잘못된 payload를 보내면 안 됩니다. 이 경우 Background Delivery를
실패로 기록하되 고객 분석 응답과 기존 상담 이관 결정에는 예외를 전파하지
마세요.

### 4.4 Harness 승인 Evidence만 사용

- Handoff Evidence는 같은 Harness 결과의
  `accepted_evidence_chunk_ids`에 포함된 항목만 사용합니다.
- `source_chunk_ids`는 외부 `evidence[].chunk_id`와 같은 순서로 정확히
  일치시킵니다.
- 중복 ID를 제거하더라도 Evidence와 ID 배열의 순서를 다르게 만들지 않습니다.
- `brief.evidence_based_findings[].source_chunk_ids`는 최상위 ID의 부분집합만
  허용합니다.
- Harness가 승인하지 않은 검색 결과를 맥락 Agent가 언급했더라도 외부 요청에
  포함하지 않습니다.

### 4.5 실패해도 기존 Handoff 유지

Context Synthesis는 상담사에게 전달할 내용을 보완하는 단계이지, 상담 이관
여부를 다시 결정하는 단계가 아닙니다.

- Context Synthesis Timeout·Provider 실패·검증 실패가 발생해도 기존
  `ConsultationHandoffResult` 생성은 계속합니다.
- 알려진 실패는 결정론적 Fallback Context를 사용합니다.
- 예상하지 못한 Context 변환 실패는 `context_synthesis=null`로 축소합니다.
- Context 실패 때문에 자동답변 경로로 되돌아가지 않습니다.
- `PipelineCancelledError`처럼 요청 취소 의미가 있는 예외는 기존 취소 정책을
  유지합니다.

### 4.6 Backend 오류 코드 기반 재시도

현재 Client는 모든 HTTP 409를 재시도 대상으로 봅니다. v2에서는 응답 Body의
`error.code`를 함께 읽어 다음 정책으로 좁혀 주세요.

| 조건 | 재시도 |
| --- | --- |
| HTTP 409 + `AI_HANDOFF_NOT_READY` | 최대 1회 |
| HTTP `429`, `500`, `502`, `503`, `504` | 최대 1회 |
| Network·Timeout | 최대 1회 |
| `AI_HANDOFF_STALE` | 금지 |
| `AI_HANDOFF_EVIDENCE_REJECTED` | 금지 |
| `DUPLICATE-EVENT-01` | 금지 |
| `VALIDATION_ERROR` | 금지 |
| `FORBIDDEN` | 금지 |
| 그 외 4xx와 다른 409 | 금지 |

전체 시도는 현재와 같이 최초 1회와 재시도 1회, 최대 2회입니다.

첫 시도 전에 v2 payload를 한 번만 완성하고, 재시도에서도 같은 payload를
그대로 사용해 주세요. Backend가 거절한 뒤 `context_synthesis`를 제거하거나
필드를 바꾸어 같은 `ai_request_id`로 다시 보내면 안 됩니다.

오류 응답 Body 자체가 JSON이 아니거나 `error.code`가 없으면 409를 재시도하지
않는 쪽으로 처리해 주세요. 로그와 Trace에는 Token, Payload 원문, 고객 문장,
Prompt, 내부 예외 상세를 남기지 않습니다.

### 4.7 활성화와 병합 순서

- 단위 테스트에서는 Fake HTTP Client로 v2 요청을 검증합니다.
- 최지용의 Backend v2 구현 준비 회신 전에 실제 Backend로 보내지 않습니다.
- Backend v2 수신 Commit을 먼저 병합한 뒤 AI v2 Client Commit을 병합합니다.
- 두 Commit이 같은 기준 main에 올라온 뒤 보호된 환경에서만 통합 E2E를
  실행합니다.
- E2E와 담당자 승인이 끝날 때까지 `AI_HANDOFF_BACKEND_ENABLED=false`를
  유지합니다.

---

## 5. 필수 테스트

최소한 아래 Case를 단위·계약 테스트로 고정해 주세요.

### 외부 DTO

- `schema_version`, 원래 `state_version`, 최상위 `routing_reason` 포함
- v2 필수 배열을 빈 배열로도 명시
- Succeeded·Fallback·Null Context 예시가 JSON Schema 통과
- 내부 메타데이터와 모든 `source_ids`가 외부 payload에 없음
- Evidence 문장만 `source_chunk_ids`를 가짐
- `source_chunk_ids == evidence[].chunk_id` 순서·중복 불변식
- Schema 최대 개수·Safety Enum·page 필수 규칙 위반 시 전송 전 실패

### 라우팅·Fallback

- Danger, Human Review 거절, Harness Escalate의 정확한 분기 매핑
- 최초 `PRE_SEND_HUMAN_REVIEW`에서 Handoff·합성·전송 없음
- 합성 예외여도 최상위 `routing_reason` 유지 및 `context_synthesis=null`
- 합성 실패가 자동답변으로 되돌아가지 않고 기존 Handoff를 유지
- Harness 승인 Evidence 외 항목 제외

### Client 재시도

- 409 `AI_HANDOFF_NOT_READY`는 한 번만 재시도
- 409 `AI_HANDOFF_STALE`와 알 수 없는 409는 재시도 없음
- 422 `AI_HANDOFF_EVIDENCE_REJECTED`, Validation, Forbidden 재시도 없음
- 429·지정 5xx·Network·Timeout은 최대 한 번 재시도
- 최대 시도 횟수 2회
- 두 시도의 JSON payload가 완전히 동일
- PII 감지와 기본 Envelope 변환 실패 시 HTTP 호출 0회
- 기능 비활성화 시 HTTP 호출 0회

### 회귀

- Handoff가 없는 Pipeline 결과는 BackgroundTask 예약 없음
- 실제 Handoff가 있는 경우에만 예약
- 기존 Human Review 승인·거절 흐름 회귀
- 기존 Context Synthesis Agent 표적 테스트
- AI 전체 Unit 회귀

현재 `test_backend_handoff_client.py`의 “`context_synthesis`를 전송하지 않는다”는
기대값은 v2 계약에 맞게 바꾸되, 내부 메타데이터가 전송되지 않는다는 별도
회귀를 반드시 남겨 주세요.

---

## 6. 실행 요청

구현 후 아래 검사를 실행해 주세요.

```powershell
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit\handoff -q
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit\harness -q
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\contract\test_consultation_handoff_contract_v2.py -q
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit -q
.\ai\.venv\Scripts\python.exe scripts\contracts\validate_examples.py
git diff --check
```

실제 Provider 호출이나 실제 Backend 전송은 이번 단위 구현 검증에 필요하지
않습니다. 실행하지 않은 Runtime·Provider·Backend E2E는 `NOT_RUN`으로
보고해 주세요.

---

## 7. 완료 기준

아래를 모두 충족하면 Backend 통합 대기 상태로 회신해 주세요.

- 외부 v2 DTO와 Mapper가 확정 JSON Schema를 만족
- 원래 `state_version`과 실제 Handoff `routing_reason`을 독립적으로 보존
- Context Synthesis 내부 메타데이터 제거
- 합성 실패 시에도 기존 Handoff 유지
- Harness 승인 Evidence만 전송
- Backend `error.code` 기반 재시도 Matrix와 최대 2회 보장
- 재시도 사이 payload 불변성 보장
- 최초 Human Review·자동답변·고객 답변 대기 경로에서 호출 없음
- Backend·계약·공유 Pipeline 파일 미수정
- 운영 활성화 값 미변경
- Handoff/Harness 표적 테스트와 AI 전체 Unit PASS

이 단계의 상태명은 `READY_FOR_BACKEND_V2_E2E`입니다. Backend 저장·상담사 조회
E2E 또는 운영 활성화 완료를 의미하지 않습니다.

---

## 8. 회신 형식

아래 형식으로 회신 부탁드립니다.

```text
base_main_commit=9862bac3749118f81ab2770016f61630b0f189e2
ai_v2_delivery_commit=<40자리 SHA>
contract_version=2.0.0
external_mapper=PASS | FAIL
state_version_binding=PASS | FAIL
routing_reason_binding=PASS | FAIL
context_internal_field_exclusion=PASS | FAIL
handoff_preserved_on_synthesis_failure=PASS | FAIL
accepted_evidence_only=PASS | FAIL
retry_error_code_matrix=PASS | FAIL
retry_payload_immutable=PASS | FAIL
handoff_targeted_tests=PASS | FAIL
ai_full_unit=PASS | FAIL
backend_v2_http_e2e=NOT_RUN
AI_HANDOFF_BACKEND_ENABLED=false
shared_files_changed=NONE | <경로와 승인자>
status=READY_FOR_BACKEND_V2_E2E | HOLD
blocker=<없음 또는 정확한 원인·담당자·완료 조건>
executed_commands=<실행 명령과 결과>
```

최지용의 Backend 준비 회신과 본 구현 회신을 모두 받은 뒤 동일 Inquiry 기준으로
전송, 원장 저장, Replay, Consultation 연결, 최신 Projection, 상담사 API 조회를
공동 검증하겠습니다.
