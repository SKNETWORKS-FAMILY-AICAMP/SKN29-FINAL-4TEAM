# 상담 Handoff 2.0 Backend 구현 요청서

- 작성일: 2026-08-27
- 발신: 이동윤
- 수신: 최지용
- 공동 검수: 윤승혁(PM, Harness·HITL·Handoff)
- 기준 Branch: `main`
- 기준 Commit: `9862bac3749118f81ab2770016f61630b0f189e2`
- Contract 정정 Commit: `be456afa56f12c602f44f37336e89466263032c1`
- Contract SSOT: `contracts/ai/handoff/ConsultationHandoffRequest.schema.json`
- 대상 Contract Version: `2.0.0`

---

## 1. 요청 요약

확정·병합된 상담 Handoff `2.0.0` 계약을 Backend가 실제로 수신하고 검증·저장할
수 있도록 구현해 주세요.

핵심은 다음 세 가지입니다.

1. 기존 v1 Handoff는 지금 허용하던 범위를 그대로 유지합니다.
2. v2 요청에만 강화된 검증, AIRun·상태·Evidence 결속을 적용합니다.
3. 실제 Consultation이 있을 때만 상담사 요약으로 연결하고, 그렇지 않은 요청은
   Handoff 원장에만 저장합니다.

현재 상태는 아래와 같습니다.

```text
contract_2_0=APPROVED_AND_MERGED
backend_v1_runtime=EXISTS
backend_v2_runtime=NOT_STARTED
ai_v2_delivery=NOT_STARTED
protected_http_e2e=NOT_RUN
AI_HANDOFF_BACKEND_ENABLED=false 유지
```

Contract 테스트 통과는 Backend 구현 완료 증거가 아닙니다. 이번 작업의 완료
기준은 Backend v2 코드와 Backend 표적 테스트까지이며, 실제 AI 호출 E2E와 운영
활성화는 후속 공동 검증으로 분리합니다.

---

## 2. 구현 기준

다음 파일을 계약의 기계 판독 기준으로 사용해 주세요.

```text
contracts/ai/handoff/ConsultationHandoffRequest.schema.json
contracts/ai/handoff/README.md
contracts/ai/examples/handoff/v1-request.json
contracts/ai/examples/handoff/v2-succeeded-request.json
contracts/ai/examples/handoff/v2-fallback-request.json
contracts/ai/examples/handoff/v2-null-context-request.json
contracts/ai/examples/handoff/v2-human-review-rejected-request.json
```

구현 과정에서 계약 의미가 불명확하거나 기존 Backend 상태 머신과 충돌하는
부분이 발견되면 Serializer에서 임의로 완화하지 말고, 정확한 필드와 충돌 이유를
회신해 주세요. 확정 계약 자체의 변경은 이번 요청 범위가 아닙니다.

---

## 3. 수정 요청 범위

다음 Backend 수신 경로와 관련 테스트가 주 대상입니다.

```text
backend/apps/consultations/api/handoff_serializers.py
backend/apps/consultations/api/views.py
backend/apps/consultations/services/consultation_handoff_service.py
backend/apps/consultations/repositories/consultation_handoff_repository.py
backend/common/exceptions/error_codes.py
contracts/error-codes/error-codes.yaml
backend/tests/api/test_ai_consultation_handoff_runtime.py
backend/tests/api/test_common_error_registry_contract.py
```

필요한 경우 Handoff 전용 Backend 테스트 파일은 새로 추가해도 됩니다.
공통 오류 계약 구조상 필요하면 `contracts/error-codes/categories/**`도 같은 오류
코드 변경에 한해 함께 갱신해 주세요.

`backend/tests/integration/test_ai_handoff_live_socket_e2e.py`는 AI·Backend 공유
통합 검증 파일이므로 이번 Backend 단독 구현에 섞지 않습니다. 두 구현이 모두
병합된 뒤 공동 E2E 단계에서 편집자를 정해 갱신합니다.

현재 `ConsultationHandoff`에는 `schema_version`, `sanitized_payload`,
`ai_draft_summary`가 이미 있으므로 DB Migration은 기본 요청 범위가 아닙니다.
새 Column이나 Migration이 꼭 필요하다고 판단되면 먼저 이유와 대안을 회신한 뒤
별도 승인받아 주세요.

이번 작업에서 수정하지 않을 범위는 다음과 같습니다.

```text
ai/**
contracts/ai/handoff/**
Web/Mobile 공개 DTO 및 화면
Inquiry 상태 머신 의미
AI Provider·Prompt·Context Synthesis Agent
운영 환경의 AI_HANDOFF_BACKEND_ENABLED 값
```

---

## 4. 상세 구현 요구사항

### 4.1 v1과 v2를 명시적으로 분리

- `schema_version`이 없으면 기존 방식대로 v1 `1.0.0`으로 정규화합니다.
- `schema_version=1.0.0`도 v1로 처리합니다.
- `schema_version=2.0.0`만 v2 Serializer로 처리합니다.
- v2 필드가 섞여 있다는 이유로 무버전 요청을 v2로 추정하지 않습니다.
- 지원하지 않는 버전과 알 수 없는 필드는 거절합니다.
- 같은 `ai_request_id`로 이미 저장된 v1 payload를 v2 payload로 바꾸어 다시
  저장하지 않습니다.

v1에는 v2의 강화 제한을 적용하지 않습니다. 특히 아래 기존 허용 범위를
보존해 주세요.

- 배열 6종 생략 가능 및 빈 배열 기본값
- 배열 개수에 대한 v2 최대 개수 제한 미적용
- `safety_level`은 기존처럼 비어 있지 않은 50자 이하 문자열 허용
- `evidence[].page` 키 생략 또는 `null` 허용

### 4.2 v2 Envelope 검증

v2에서는 아래 값을 모두 필수로 검증해 주세요.

```text
schema_version=2.0.0
state_version>=1
routing_reason
questionnaire_answers
self_help_actions
evidence
safety_notes
consultant_priority_checks
source_chunk_ids
context_synthesis=object|null
```

배열 최대 개수는 계약 그대로 적용합니다.

| 필드 | 최대 개수 |
| --- | ---: |
| `questionnaire_answers` | 30 |
| `self_help_actions` | 20 |
| `evidence` | 10 |
| `safety_notes` | 20 |
| `consultant_priority_checks` | 30 |
| `source_chunk_ids` | 10 |

`safety_level`은 `general`, `caution`, `danger`, `unknown`만 허용하고,
v2 `evidence[].page`는 키가 반드시 존재하되 값은 `null`일 수 있어야 합니다.

`routing_reason`은 다음 세 값만 허용합니다.

```text
DANGER_HANDOFF
FAIL_CLOSED_CONSULTATION
HARNESS_ESCALATE
```

`PRE_SEND_HUMAN_REVIEW`는 실제 상담 Handoff가 아니라 최초 가이드 검토 시작점이므로
거절해야 합니다.

### 4.3 Inquiry·AIRun·상태 결속

v2 요청은 같은 실행의 권위 있는 Backend 기록과 대조해 주세요.

- URL의 `inquiry_id`, Body의 `inquiry_id`, AIRun의 Inquiry가 같아야 합니다.
- Header와 Body의 `correlation_id`, `ai_request_id`가 AIRun과 같아야 합니다.
- `state_version`은 원래 AI 분석에 사용된 Inquiry 상태 버전과 같아야 합니다.
- `model_code`는 Inquiry 구독 제품과 AIRun의 판정 제품에 맞아야 합니다.
- AIRun이 아직 Handoff 검증에 필요한 상태로 확정되지 않은 일시적 경우와,
  이미 오래된 상태 버전인 영구 거절을 구분해야 합니다.

단순히 AIRun이 존재한다는 이유만으로 v2 요청을 승인하지 말고, 아래 분기별
권위 조건도 확인해 주세요.

### 4.4 분기별 권위 검증

#### `DANGER_HANDOFF`

- 위험 판정에 해당하는 동일 AIRun 결과와 결속합니다.
- `context_synthesis`가 객체이면 반드시
  `status=FALLBACK`, `fallback_reason=DANGER_BYPASS`여야 합니다.
- 예상하지 못한 AI 합성·Mapper 실패를 위한 `context_synthesis=null`은
  허용하되, 위험 Handoff 자체는 그대로 처리합니다.

#### `HARNESS_ESCALATE`

HTTP 오류 응답이 아니라 같은 `AIRun.validated_output_payload`의 아래 조합만
1차 승인 근거로 사용해 주세요.

| `fallback_reason_code` | `failure_stage` | 처리 |
| --- | --- | --- |
| `MCP_TOOL_FAILURE` | `VALIDATING` | Handoff 원장만 저장 |
| `OUTPUT_SCHEMA_INVALID` | `VALIDATING` | Handoff 원장만 저장 |
| `UNSPECIFIED_FALLBACK` | `VALIDATING` | Handoff 원장만 저장 |

이 조합만으로 Inquiry 상태를 바꾸거나 Consultation을 만들지 않습니다. 실제
Backend 승인 Consultation이 생기기 전에는 `ai_draft_summary`에도 연결하지
않습니다.

#### `FAIL_CLOSED_CONSULTATION`

Human Review 거절 기반 요청은 다음 값을 모두 확인해 주세요.

```text
HumanReview.inquiry_id == request.inquiry_id
HumanReview.guidance.inquiry_id == request.inquiry_id
HumanReview.source_ai_request_id == request.ai_request_id
HumanReview.source_inquiry_state_version == request.state_version
HumanReview.status_code == REJECTED
HumanReview.decision_code == REJECT
```

`decision_correlation_id`와 원래 AI 분석 `correlation_id`의 동일성은 요구하지
않습니다. 검토 거절만으로 Inquiry 상태를 변경하거나 Consultation을 자동
생성하지 않습니다. Consultation이 아직 없다면 원장만 저장합니다.

### 4.5 Evidence 결속

아래 검증을 모두 적용해 주세요.

1. `source_chunk_ids`는 `evidence[].chunk_id`와 순서까지 같아야 합니다.
2. 최상위 Chunk ID는 중복될 수 없습니다.
3. `context_synthesis.brief.evidence_based_findings[].source_chunk_ids`는
   최상위 `source_chunk_ids`의 부분집합이어야 합니다.
4. 각 Chunk는 같은 AIRun에서 Harness가 승인한 Evidence여야 합니다.
5. 각 Chunk는 활성·검증된 `AIChunkCrosswalk`와 제품·문서·페이지가 맞아야
   합니다.

Payload 안의 Evidence만 보고 승인하거나, 불일치하는 맥락 일부를 조용히
삭제한 뒤 나머지만 저장하지 마세요. 검증에 실패하면 요청 전체를 거절해야
합니다.

### 4.6 저장·Replay·오류 코드

- 정규화·검증된 payload와 `schema_version`을 기존 Handoff 원장에 저장합니다.
- 같은 `ai_request_id`와 완전히 같은 payload의 Replay는 기존 결과를 반환합니다.
- 같은 `ai_request_id`로 payload를 변경하거나 v1에서 v2로 바꾼 요청은
  불변성 위반으로 거절합니다.
- AI가 거절 이후 payload를 고쳐서 재시도해야만 성공하는 동작을 만들지 않습니다.

아래 Handoff 전용 오류를 Backend Registry와 공통 오류 계약에 추가해 주세요.

| 오류 코드 | HTTP | 의미 | AI 재시도 |
| --- | ---: | --- | --- |
| `AI_HANDOFF_NOT_READY` | 409 | AIRun 확정 등 일시적 준비 지연 | 최대 1회 |
| `AI_HANDOFF_STALE` | 409 | 오래된 `state_version` 또는 권위 상실 | 금지 |
| `AI_HANDOFF_EVIDENCE_REJECTED` | 422 | Evidence·Crosswalk·동일 Run 결속 실패 | 금지 |

기존 `DUPLICATE-EVENT-01`, `VALIDATION_ERROR`, `FORBIDDEN`과 그 외 4xx도
비재시도 응답으로 유지합니다. 응답 Body의 `error.code`가 공통 오류 Envelope에
정확히 포함되는지 테스트해 주세요.

### 4.7 상담사 Projection

1차 공개 방식은 구조화 DTO가 아니라 기존 `Consultation.ai_draft_summary`에 넣는
`SUMMARY_ONLY`입니다.

- 일반 텍스트 최대 4,000자로 생성합니다.
- 내부 메타데이터, Prompt, 원문 Provider 응답, Stack Trace, Token, Latency,
  검색 점수, Vector를 포함하지 않습니다.
- 실제 Consultation이 존재하고 연결이 허용된 Handoff에만 Projection합니다.
- Ledger-only `HARNESS_ESCALATE`와 실제 Consultation이 없는 Human Review 거절은
  Projection하지 않습니다.
- 오래된 Handoff가 나중에 도착해 더 최신 상담 요약을 덮어쓰지 않도록
  비강등 조건을 둡니다.
- Handoff 저장만으로 Inquiry 상태 전환이나 Consultation 생성을 수행하지
  않습니다.

---

## 5. 필수 테스트

최소한 아래 Case를 Backend 테스트로 고정해 주세요.

### v1 회귀

- 무버전 v1과 명시적 `1.0.0` 정상 수신
- v2 최대 개수를 넘는 기존 v1 배열도 기존 계약 범위에서는 정상 수신
- v2 Enum 밖의 기존 `safety_level` 문자열 정상 수신
- `evidence[].page` 생략 및 `null` 정상 수신
- v2 전용 필드가 섞인 무버전 요청 거절

### v2 계약

- 계약 예시 4종 정상 수신
- 필수 배열 생략, 최대 개수 초과, 잘못된 Safety Enum, page 키 생략 거절
- 알 수 없는 필드와 `PRE_SEND_HUMAN_REVIEW` 거절
- Danger·Fallback·Null Context 조합 검증
- 내부 전용 메타데이터 필드 유입 거절

### Backend 권위

- Inquiry·AIRun·Header·Body 식별자 불일치 거절
- AIRun 준비 전 `AI_HANDOFF_NOT_READY`
- 오래된 `state_version`에 `AI_HANDOFF_STALE`
- HARNESS 허용 조합 3종과 비허용 조합 거절
- Human Review 거절 결속 성공·실패
- 동일 AIRun 승인 Evidence 성공, 다른 Run·비활성 Crosswalk·페이지 불일치 거절

### 저장·Projection

- 같은 payload Replay 성공, 변경 payload 거절
- v1 저장본을 같은 `ai_request_id`의 v2로 업그레이드하는 요청 거절
- 실제 Consultation이 없는 Harness·검토 거절은 Ledger-only
- 실제 Consultation이 있으면 4,000자 이내 요약 연결
- 오래된 Handoff가 최신 Projection을 덮어쓰지 않음

SQLite 표적 테스트와 PostgreSQL 동시성·Row Lock 검증을 구분해 보고해 주세요.
SQLite PASS만으로 PostgreSQL Replay·Lock 동작까지 PASS로 표시하지 않습니다.

---

## 6. 실행 요청

구현 후 최소한 다음 검사를 실행해 주세요. 실제 명령은 Backend 환경에 맞게
조정할 수 있지만, 회신에는 실행한 정확한 명령과 결과를 남겨 주세요.

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend\tests\api\test_ai_consultation_handoff_runtime.py -q
.\backend\.venv\Scripts\python.exe -m pytest backend\tests\api\test_common_error_registry_contract.py -q
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\contract\test_consultation_handoff_contract_v2.py -q
git diff --check
```

PostgreSQL Handoff 통합 테스트를 실행할 수 없는 환경이면 `NOT_RUN`으로 남기고,
필요한 DB·환경 담당자와 실행 조건을 적어 주세요.

---

## 7. 완료 기준

아래를 모두 충족하면 AI v2 연결 준비 완료로 회신해 주세요.

- v1 기존 허용 범위 회귀 PASS
- v2 Serializer와 교차 필드 검증 PASS
- AIRun·State Version·Harness·Human Review·Evidence 결속 PASS
- 신규 오류 코드와 HTTP 응답 계약 PASS
- 원장 Replay·불변성·Projection 비강등 PASS
- 계약 파일 및 `ai/**` 미수정
- 운영 활성화 값 미변경
- 변경 Commit과 검사 결과 전달

이 단계의 상태명은 `READY_FOR_AI_V2_INTEGRATION`입니다. 아직 실제 AI→Backend
HTTP E2E나 운영 활성화 `PASS`는 아닙니다.

---

## 8. 회신 형식

아래 형식으로 회신 부탁드립니다.

```text
base_main_commit=9862bac3749118f81ab2770016f61630b0f189e2
backend_implementation_commit=<40자리 SHA>
contract_version=2.0.0
v1_regression=PASS | FAIL
v2_serializer=PASS | FAIL
airun_state_binding=PASS | FAIL
harness_crosswalk=PASS | FAIL
human_review_binding=PASS | FAIL
evidence_binding=PASS | FAIL
error_registry=PASS | FAIL
replay_and_projection=PASS | FAIL
postgresql_integration=PASS | FAIL | NOT_RUN
protected_ai_backend_e2e=NOT_RUN
AI_HANDOFF_BACKEND_ENABLED=false
status=READY_FOR_AI_V2_INTEGRATION | HOLD
blocker=<없음 또는 정확한 원인·담당자·완료 조건>
executed_commands=<실행 명령과 결과>
```

Backend 준비 회신 뒤 윤승혁의 AI v2 전송 구현과 동일 Inquiry 통합 검증을
연결하겠습니다. 두 구현이 모두 병합되기 전에는
`AI_HANDOFF_BACKEND_ENABLED=true`로 변경하지 말아 주세요.
