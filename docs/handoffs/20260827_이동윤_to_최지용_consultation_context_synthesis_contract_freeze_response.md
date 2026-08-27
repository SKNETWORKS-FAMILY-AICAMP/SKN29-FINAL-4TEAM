# Consultation Context Synthesis Handoff 2.0 Contract Freeze 후보 회신

- 작성일: 2026-08-27
- 발신: 이동윤
- 수신: 최지용
- 공동 검수 요청: 윤승혁(PM, Harness·Handoff)
- 회신 대상: `20260827_최지용_to_이동윤_consultation_context_synthesis_backend_decision_response.md`
- Contract 후보 Branch: `dongyoon`
- Contract Freeze 후보 Commit:
  `fd51326c8e468fc836bcfdcf0754effd6d5f9e0c`
- 포함된 원격 `main` 기준:
  `9d338e3c2c238d0d337ae4e928daacd72c3c7732`

---

## 1. 결론

회신에서 요청한 상담 Handoff Envelope `2.0.0` JSON Schema, v1 호환 예시,
v2 예시 4종과 Contract 검증 테스트를 위 Commit으로 작성했습니다.

현재 상태는 다음과 같습니다.

```text
contract_freeze_candidate=READY_FOR_REVIEW
contract_freeze_approved=NO
target_commit=fd51326c8e468fc836bcfdcf0754effd6d5f9e0c
backend_v2_implementation=NOT_STARTED
ai_v2_external_mapper=NOT_STARTED
ready_for_ai_allowlist=NO
runtime_e2e=NOT_RUN
status=HOLD_CONTRACT_REVIEW_REQUIRED
```

이번 Commit은 기계 판독 계약과 예시를 검수 가능한 상태로 만든 후보입니다.
최지용·윤승혁의 검수 전에는 공식 Contract Freeze 완료, Backend v2 완료 또는
AI allowlist 개방으로 표시하지 않겠습니다.

---

## 2. 추가한 Contract 파일

```text
contracts/ai/handoff/ConsultationHandoffRequest.schema.json
contracts/ai/handoff/README.md
contracts/ai/examples/handoff/v1-request.json
contracts/ai/examples/handoff/v2-succeeded-request.json
contracts/ai/examples/handoff/v2-fallback-request.json
contracts/ai/examples/handoff/v2-null-context-request.json
contracts/ai/examples/handoff/v2-human-review-rejected-request.json
ai/tests/contract/test_consultation_handoff_contract_v2.py
```

기존 공통 AI 계약 문서와 테스트도 Handoff Envelope가 분석 계약 `4.0.0`과
분리된 `2.0.0`임을 인식하도록 함께 갱신했습니다.

```text
contracts/ai/README.md
contracts/ai/CHANGELOG.md
ai/tests/unit/test_schemas_and_configs.py
```

---

## 3. v1·v2 Envelope 규칙

### v1

- 현재 AI Client payload에는 `schema_version`이 없습니다.
- Backend의 기존 동작대로 생략된 v1은 `1.0.0`으로 정규화합니다.
- v1 요청에는 `state_version`, `routing_reason`, `context_synthesis`를 허용하지
  않습니다.

### v2

다음 네 필드를 모두 필수로 고정했습니다.

```text
schema_version=2.0.0
state_version>=1
routing_reason
context_synthesis=object|null
```

`routing_reason`은 다음 세 값만 허용합니다.

- `DANGER_HANDOFF`
- `FAIL_CLOSED_CONSULTATION`
- `HARNESS_ESCALATE`

`PRE_SEND_HUMAN_REVIEW`는 최초 가이드 검토 시작점이며 실제 Handoff가 아니므로
Schema 단계에서 거절합니다.

같은 `ai_request_id`로 저장된 v1 payload를 v2 payload로 변경해 재전송하는
업그레이드도 허용하지 않습니다.

---

## 4. `context_synthesis` 외부 DTO 규칙

외부 DTO는 아래 세 필드만 가집니다.

```text
status
fallback_reason
brief
```

AI 내부에서만 사용하는 다음 값은 외부 요청에서 금지했습니다.

- `source_ids`
- `provider_called`
- `model_name`
- `prompt_version`
- `tokens_used`
- `latency_ms`
- `should_use_deterministic_handoff`
- Provider Prompt·원문 응답
- Exception·Stack Trace
- 검색 점수·Embedding Vector

상태 조합은 다음과 같이 고정했습니다.

| `routing_reason` | `context_synthesis.status` | `fallback_reason` |
| --- | --- | --- |
| `DANGER_HANDOFF` | `FALLBACK` | `DANGER_BYPASS` |
| `FAIL_CLOSED_CONSULTATION` | `SUCCEEDED` | `null` |
| `FAIL_CLOSED_CONSULTATION` | `FALLBACK` | `DANGER_BYPASS` 이외 허용 Enum |
| `HARNESS_ESCALATE` | `SUCCEEDED` | `null` |
| `HARNESS_ESCALATE` | `FALLBACK` | `DANGER_BYPASS` 이외 허용 Enum |
| 위 세 분기 | `null` | 해당 없음 |

알려진 합성 실패는 결정론적 `FALLBACK brief`를 사용합니다. 예상하지 못한 합성
예외 또는 AI 외부 DTO Mapper 실패만 `context_synthesis=null`로 축소합니다.
Backend가 도착한 잘못된 맥락만 조용히 제거해 나머지를 저장하는 방식은
허용하지 않습니다.

---

## 5. HARNESS_ESCALATE Crosswalk 정정

결정 회신의 다음 표현은 실제 AI 호출 경로와 맞지 않아 Contract에서는
정정했습니다.

```text
AI error.code × failure_stage
```

Handoff는 `/analyze`의 정상 Pipeline 결과가 만들어진 뒤 Background Callback으로
전송됩니다. 따라서 Backend가 같은 Run에서 검증할 값은 HTTP 오류 응답의
`error.code`가 아니라 다음 값입니다.

```text
AIRun.validated_output_payload.fallback_reason_code
AIRun.validated_output_payload.failure_stage
```

1차 `HARNESS_ESCALATE` Ledger-only 허용 조합은 현재 Runtime에서 실제 생성
가능한 다음 세 조합으로 고정했습니다.

| `fallback_reason_code` | `failure_stage` | Backend 1차 처리 |
| --- | --- | --- |
| `MCP_TOOL_FAILURE` | `VALIDATING` | Handoff 원장만 저장 |
| `OUTPUT_SCHEMA_INVALID` | `VALIDATING` | Handoff 원장만 저장 |
| `UNSPECIFIED_FALLBACK` | `VALIDATING` | Handoff 원장만 저장 |

`NO_EVIDENCE`, 제품 미승인, Danger처럼 기존 Backend State Event와 승인 근거가
있는 결과는 위 Ledger-only Harness 조합으로 바꾸지 않습니다.

`HARNESS_ESCALATE` 원장은 실제 Backend 승인 Consultation이 생기기 전까지
상담에 연결하거나 `ai_draft_summary`로 Projection하지 않습니다. 따라서 이
경로는 저장 즉시 상담사 화면에 노출되는 계약이 아닙니다.

---

## 6. Human Review 거절 결속

Human Review 거절 Handoff는 다음 조건을 모두 만족하도록 Contract Metadata와
예제에 반영했습니다.

```text
HumanReview.inquiry_id == request.inquiry_id
HumanReview.guidance.inquiry_id == request.inquiry_id
HumanReview.source_ai_request_id == request.ai_request_id
HumanReview.source_inquiry_state_version == request.state_version
HumanReview.status_code == REJECTED
HumanReview.decision_code == REJECT
request.routing_reason == FAIL_CLOSED_CONSULTATION
```

`decision_correlation_id`와 원래 AI 분석 `correlation_id`는 서로 다른 요청의
식별자이므로 동일값을 요구하지 않습니다.

Human Review 거절만으로 Inquiry 상태를 바꾸거나 Consultation을 자동 생성하지
않습니다. 실제 Consultation이 없다면 Handoff 원장만 저장하고 상담사 Projection은
수행하지 않습니다.

---

## 7. Evidence 결속

다음 불변식을 Schema Metadata와 Contract 테스트로 고정했습니다.

1. `source_chunk_ids`는 `evidence[].chunk_id`와 순서까지 같아야 합니다.
2. 최상위 Chunk ID는 중복될 수 없습니다.
3. `brief.evidence_based_findings[].source_chunk_ids`는 최상위
   `source_chunk_ids`의 부분집합이어야 합니다.
4. 실제 Backend 구현은 같은 AIRun의 검증된 Evidence와 활성·검증
   `AIChunkCrosswalk`를 다시 대조해야 합니다.

맥락정리 결과의 Evidence 문장은 상담사 검토용 초안입니다. 새 EvidenceCard,
확정 사실 또는 진단으로 승격하지 않습니다.

---

## 8. Backend 오류와 AI 재시도

결정 회신의 오류별 정책을 Contract Metadata와 테스트에 반영했습니다.

| 조건 | AI Handoff 재시도 |
| --- | --- |
| `AI_HANDOFF_NOT_READY` | 최대 1회 |
| HTTP `429`, `500`, `502`, `503`, `504` | 최대 1회 |
| Network Error, Timeout | 최대 1회 |
| `AI_HANDOFF_STALE` | 금지 |
| `AI_HANDOFF_EVIDENCE_REJECTED` | 금지 |
| `DUPLICATE-EVENT-01` | 금지 |
| `VALIDATION_ERROR` | 금지 |
| `FORBIDDEN` | 금지 |
| 그 외 4xx | 금지 |

전체 전송은 최초 1회와 재시도 1회로 최대 2회입니다. Backend 거절 뒤 같은
`ai_request_id`의 payload를 변경해 다시 보내지 않습니다.

이 정책은 `BEST_EFFORT_BOUNDED_RETRY`이며 Outbox·Reconciliation이 없으므로
영구 전달 보장이 아닙니다.

---

## 9. 실행 검증

실행 환경은 Python `3.13.13`입니다.

### Handoff·분석 Contract

```powershell
.\ai\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider ai\tests\contract\test_consultation_handoff_contract_v2.py ai\tests\contract\test_symptom_analysis_contract_v4.py -q
```

```text
44 passed in 1.03s
```

### 맥락정리 Agent 회귀

```powershell
.\ai\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider ai\tests\unit\test_consultation_context_synthesis_agent.py -q
```

```text
45 passed in 0.97s
```

### 전체 AI Unit

```powershell
.\ai\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider ai\tests\unit -q
```

```text
668 passed, 4 warnings, 41 subtests passed in 30.45s
```

### 공통 Contract 검증

```powershell
.\ai\.venv\Scripts\python.exe -B scripts\contracts\validate_examples.py
.\ai\.venv\Scripts\python.exe -B -m unittest discover -s tests\contract -p "test_*.py" -v
git diff --check
```

```text
Contract Example validation PASSED
Root Contract Unit: 4 tests OK
git diff --check: PASS
```

위 결과는 Schema·예시·AI 내부 모델 경계의 Local 검증입니다. Backend 저장,
PostgreSQL 원장, Replay, Consultation 연결, 상담사 API 조회 또는 Web 소비 E2E
결과가 아닙니다.

---

## 10. 아직 구현하지 않은 범위

이번 Contract Commit에서는 다음 코드를 수정하지 않았습니다.

- Backend Serializer·Service·Model·Repository·Projection
- Backend Error Registry
- 윤승혁 소유 AI 외부 DTO Mapper
- `state_version`, `schema_version`, `routing_reason`, `context_synthesis` 전송
- Handoff Client v2 allowlist
- Backend `error.code` 기반 재시도 분기
- `AI_HANDOFF_BACKEND_ENABLED=true` 전환

현재 Parity 검증은 다음 범위입니다.

- v1 전체 payload ↔ 기존 `ConsultationHandoffResult`: `PASS`
- v2 기존 Handoff 필드 ↔ `ConsultationHandoffResult`: `PASS`
- v2 Routing·Status·Fallback Enum ↔ 맥락 Agent 모델: `PASS`
- v2 외부 Brief 필드 ↔ 내부 `CounselorContextBrief`: `PASS`
- 실제 v2 외부 DTO Mapper Runtime: `NOT_STARTED`, 윤승혁 범위

따라서 이번 Commit 검수 후 윤승혁이 외부 DTO Mapper를 구현하고, 완성된 v2
Pydantic DTO와 JSON Schema의 최종 Parity를 다시 확인해야 합니다.

---

## 11. 최지용 검수 요청

Commit `fd51326c8e468fc836bcfdcf0754effd6d5f9e0c`에서 다음 항목을 확인해
주세요.

1. v1 무버전 요청을 `1.0.0`으로 정규화하는 호환 정책
2. v2 필수 필드와 `PRE_SEND_HUMAN_REVIEW` 금지
3. `context_synthesis` 상태·Fallback 조합
4. `HARNESS_ESCALATE`의
   `fallback_reason_code × failure_stage` Allowlist
5. Human Review 거절 결속 키
6. Evidence 결속 불변식
7. Backend 오류별 AI 재시도 여부
8. 실제 Consultation 전 Ledger-only·Projection 금지 정책

검수 승인 후 최지용 범위에서 다음 구현을 시작해 주세요.

- v1·v2 명시적 Serializer 분기
- 같은 AIRun·Inquiry·Correlation·State Version·Model 검증
- HARNESS Allowlist와 Human Review 거절 검증
- Evidence·Crosswalk 검증
- v2 원장 저장과 Replay 비강등
- 실제 Consultation 생성 뒤 최신 Handoff 연결
- `SUMMARY_ONLY`, 최대 4,000자 `ai_draft_summary` Projection
- 신규 Handoff Error Code의 Error Registry 등록
- 관련 Backend 표적 테스트

---

## 12. 윤승혁 검수 및 후속 요청

Contract 검수 승인 뒤 다음 항목을 구현·검증해 주세요.

- 외부 전송 DTO Mapper
- `schema_version=2.0.0` 전파
- 원래 분석 요청의 `state_version` 전파
- 최상위 `routing_reason` 전파
- 외부 `context_synthesis` 필드 축소
- 내부 `source_ids`·Provider 메타데이터 제거
- v2 Handoff Client allowlist
- `AI_HANDOFF_NOT_READY`만 409 재시도
- 최대 2회 bounded retry 유지

Backend 준비 회신 전에는 `AI_HANDOFF_BACKEND_ENABLED`를 `true`로 바꾸지
않습니다.

---

## 13. 요청 회신 형식

아래 형식으로 회신 부탁드립니다.

```text
reviewed_contract_commit=fd51326c8e468fc836bcfdcf0754effd6d5f9e0c
contract_review=APPROVED | CHANGES_REQUIRED
v1_compatibility=APPROVED | CHANGES_REQUIRED
v2_schema=APPROVED | CHANGES_REQUIRED
harness_airun_crosswalk=APPROVED | CHANGES_REQUIRED
human_review_binding=APPROVED | CHANGES_REQUIRED
error_retry_matrix=APPROVED | CHANGES_REQUIRED
backend_implementation_start=YES | NO
requested_changes=<없음 또는 정확한 필드·규칙>
```

검수 승인만으로 전체 연동 PASS가 되는 것은 아닙니다. 최종 판정은 아래 동일
Inquiry 흐름을 실제로 실행한 뒤 별도로 내립니다.

```text
AI v2 전송
→ Backend 검증·원장 저장
→ 동일 payload Replay 및 변경 payload 거절
→ 실제 Consultation 연결
→ 최신 Projection 비강등
→ 상담사 API 조회
→ DB·감사 근거 확인
```
