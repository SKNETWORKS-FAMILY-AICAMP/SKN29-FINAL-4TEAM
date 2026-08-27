# 이동윤 → 윤승혁: Consultation Context Synthesis Runtime 연결 요청 및 진행 상태

> 작성일: 2026-08-26  
> 정정일: 2026-08-27
> 송신: 이동윤 — Multi-Agent Core·RAG·Generation·Evaluation  
> 수신: 윤승혁 — Reliability·Harness·HITL·Handoff  
> 시작 기준: `dongyoon@7cbc9bf0c062a36901903e1feee7f10fd2f4d4d2`

> 바로 전달할 작업 요청은
> `docs/handoffs/20260826_이동윤_to_윤승혁_context-synthesis_자연어_작업요청.md`를
> 사용한다. 아래 내용은 구현 계약과 검증 근거를 설명하는 상세 자료다.

## 결론

상담사 전달용 맥락을 출처 보존형 브리프로 가공하는 독립 Agent와 Harness·
Consultation Handoff 내부 연결은 구현됐다. `context_synthesis`는 AI 내부 Handoff
결과에만 포함되고 Backend Client의 기존 계약 Allowlist에서 제외되므로, 현재
상태는 `PARTIAL / AI_INTERNAL_CONNECTED / BACKEND_NOT_CONNECTED`다.

## 구현된 경계

- `ConsultationContextSynthesisAgent`는 상담 분기가 최종 확정된 뒤에만 호출할 수
  있는 독립 후보로 구현했다. 기존 3-Agent `AgentRole`, Shared State, Pipeline
  Router에는 추가하지 않았다.
- 입력은 공개 UUID 추적 정보, exact `model_code`, 명시적
  `runtime_product_approved`, 구조화 증상·문진·실제 수행 조치, 호출자가 선별한
  Evidence, Safety 결과와 상담 우선 확인 항목만 허용한다.
- Evidence의 `chunk_id + summary_sha256`가 입력 Binding과 정확히 일치하지 않으면
  입력을 거부해 전달 후 본문 변조를 탐지한다. 다만 이 Binding은 자기일관성
  검증이며, Runtime 연결에서는 같은 실행의 Harness
  `accepted_evidence_chunk_ids`와 일치하는 Evidence만 합성 입력에 전달한다. 검색
  점수·Vector·Prompt·고객 원문·내부 오류는 입력과 Provider 요청에서 제외한다.
- LLM은 새 문장을 작성하지 않고 비식별 Source ID의 선택·정렬·그룹화만 한다.
  최종 문장은 로컬에서 원 출처를 그대로 조립하므로 진단·자가조치·상태 전환을
  새로 만들 수 없다.
- Provider에는 허용된 증상·물 종류·오류 코드와 최소 Safety Category만 전달한다.
  문진 자유문·실제 수행 조치·Evidence 본문·상담 우선순위는 Provider에 보내지
  않는다.
- Danger, Safety 미확인, 미승인 Runtime 제품, 입력 과대, Provider 미설정·Timeout·
  거부·오류·Schema/출처 검증 실패는 재시도 없이 결정론적 브리프로 종료한다.
  특히 미승인 제품과 Danger는 Provider 호출이 0회다.
- 전화번호·이메일·주민번호형 값·주소·URL·DSN·Secret·내부 식별자를 마스킹한다.
  이름 휴리스틱은 의미 훼손을 막기 위해 고객 자유입력에만 적용하고, Safety·공식
  Evidence에서는 명시 이름 라벨·고객 호칭·연락처 인접처럼 비모호한 신호만
  마스킹한다.

주요 산출물:

- `ai/app/orchestration/agents/consultation_context_synthesis_agent.py`
- `ai/app/orchestration/agents/context_synthesis_contracts.py`
- `ai/app/generation/consultation_summary/context_models.py`
- `ai/app/generation/consultation_summary/context_synthesizer.py`
- `ai/app/integrations/llm/consultation_summary_client.py`
- `ai/app/validation/consultation_context/brief_validator.py`
- `ai/prompts/consultation_summary/v2/**`
- `ai/tests/unit/test_consultation_context_synthesis_agent.py`

## 요청하는 Runtime 연결 순서

| 최종 분기 | 합성 Agent | Provider | 다음 동작 |
| --- | --- | --- | --- |
| `AUTO_GUIDANCE` | 호출 0회 | 호출 0회 | 기존 자동 안내 유지 |
| `CUSTOMER_INPUT_PENDING` | 호출 0회 | 호출 0회 | 기존 추가 입력 대기 유지 |
| `DANGER_HANDOFF` | 호출 | 호출 0회 | 결정론적 Safety-first 브리프 후 기존 Handoff 즉시 실행 |
| `PRE_SEND_HUMAN_REVIEW` | 호출 0회 | 호출 0회 | 기존 HITL만 시작하며 실제 Handoff 확정 전 합성하지 않음 |
| `FAIL_CLOSED_CONSULTATION` | 호출 | 승인 제품·검증된 Safety일 때만 최대 1회 | 성공·Fallback 모두 기존 Handoff 유지 |
| `HARNESS_ESCALATE` | 호출 | 승인 제품·검증된 Safety일 때만 최대 1회 | 성공·Fallback 모두 기존 Escalate/Handoff 유지 |

`runtime_product_approved`는 모델 코드에서 추정하지 말고 Harness가 사용한 승인된
Product Context에서 명시적으로 전달해야 한다. Agent 실패가 기존 상담 이관을
막거나 고객 자동 안내로 되돌아가면 안 된다.

`safety_requires_consultation`은 Safety Agent의 실제 판정으로 유지한다. Danger는
`true`와 승인된 Safety Rule ID를 요구하지만, Timeout·MCP·Harness 실패에 의한
`HARNESS_ESCALATE`와 `FAIL_CLOSED_CONSULTATION`은 Safety가 `false/unknown`이어도
허용한다. 상담 이관 여부와 Safety 상담 필요 여부를 같은 값으로 강제하지 않는다.

## 현재 결합 Gap

AI 내부 Runtime 연결 이후에도 다음 의미 차이와 외부 계약 Gap이 남아 있다.

1. 기존 Handoff 입력은 문진에서 `answer/value/selected_option`만 읽으므로 현재
   Pipeline의 `answer_text`가 누락될 수 있다.
2. 기존 Handoff 입력은 고객이 실제 수행한 `StructuredSymptom.actions_taken`이
   아니라 향후 안내 후보인 `UsageGuidance.next_actions`를 self-help action으로
   사용한다.
3. 현재 연결 코드는 실제 Safety 판정과 별도로 모든 Handoff 입력의
   `safety_requires_consultation`을 `true`로 강제한다. 이동윤 소유 입력 계약은
   실제 Safety 값을 허용하도록 정정했으며, 윤승혁 소유 Runtime Adapter도 강제
   변환을 제거해야 한다.
4. Backend `ConsultationHandoffRequestSerializer`는 알 수 없는 필드를 거부한다.
   새 구조화 브리프를 전송하려면 윤승혁·최지용이 AI Handoff DTO와 Backend
   Serializer/저장 계약을 함께 확정해야 한다. 승인 없이 임의 필드를 추가하거나
   기존 문자열에 JSON을 숨겨 넣지 않는다.
5. 현재 AI Handoff Input/Result와 Backend Handoff Serializer에는
   `state_version`이 없다. 합성 결과에 보존된 값을 동일 Inquiry의 stale 요청
   차단에 사용할지 윤승혁·최지용이 계약으로 확정해야 한다.

## 소유자와 Acceptance Criteria

### 윤승혁 — Harness·HITL·Handoff

- 최종 Routing 이후 합성 Agent 호출 위치와 공유 파일의 단일 편집자를 확정한다.
- `AUTO_GUIDANCE`, `CUSTOMER_INPUT_PENDING`에서 합성 호출 0회를 검증한다.
- Danger·미승인 제품의 Provider 호출 0회를 검증한다.
- 합성 성공·Timeout·거부·Schema·출처 검증 실패 모두에서 논리 Handoff 1건이
  유지되는지 검증한다. Background Delivery의 bounded retry는 허용하되 Backend
  멱등성으로 중복 영속은 0건이어야 한다.
- `inquiry_id`, `correlation_id`, `ai_request_id`, `state_version`, exact
  `model_code`가 끝까지 보존되는지 검증한다.
- 위 Handoff 입력의 `answer_text`와 실제 수행 조치 의미 차이를 수정하고 담당
  표적 테스트를 추가한다.
- 같은 실행의 Harness `accepted_evidence_chunk_ids`와 일치하는 Evidence만 합성
  입력으로 전달하고, 임의·미승인 Evidence는 합성 호출 전에 거부하는 테스트를
  추가한다.

### 최지용 — Backend·Database

- 구조화 브리프의 승인된 Request DTO·저장 필드·Schema Version을 확정한다.
- 같은 Inquiry에서 멱등성, stale `state_version` 차단, 저장·Replay와 Payload Hash
  일치를 PostgreSQL에서 검증한다.
- 알 수 없는 필드 거부와 PII 차단을 유지한다.

### 한예나 — Web 소비

- 상담사 화면에서 AI 브리프를 확정 진단이 아닌 검토용 초안으로 표시한다.
- 출처·불확실성·실제 수행 조치와 제안 행동을 서로 다른 의미로 노출한다.

### 김은진 — 독립 QA

- 같은 Inquiry에서 정상·Danger·미승인 제품·No-Evidence·Provider Timeout·거부·
  Schema 오류를 재현한다.
- 고객 PII, Prompt·검색 점수·Vector·Trace·내부 오류 원문이 Provider 요청,
  Backend 저장 Payload, Web Projection에 노출되지 않는지 확인한다.
- Agent Unit 결과를 실제 Provider·Backend·Web 공동 E2E `PASS`로 승격하지 않고
  Fault Injection과 저장·Replay 증거를 독립 검토한다.

## 실행 증거와 상태 경계

```powershell
.\ai\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider ai\tests\unit\test_consultation_context_synthesis_agent.py -q
.\ai\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider ai\tests\unit\test_consultation_context_synthesis_agent.py ai\tests\unit\test_multi_agent_pipeline.py ai\tests\unit\test_llm_guidance.py ai\tests\unit\test_consultation_summary.py -q
.\ai\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider ai\tests\unit -q
```

| 범위 | 결과 |
| --- | --- |
| 신규 Agent Unit | `42 passed` — `PASS` |
| Multi-Agent·Guidance·기존 상담 요약 관련 회귀 | `104 passed` — `PASS` |
| AI 전체 Unit | `657 passed, 4 warnings, 41 subtests passed` — `PASS` |
| Harness/Handoff Runtime 연결 | `NOT_RUN / NOT_CONNECTED` |
| 실제 OpenAI Provider 실행 | `NOT_RUN` |
| Backend 동일 Inquiry 저장·Replay | `NOT_RUN` |
| Web 상담사 소비 E2E | `NOT_RUN` |

### 2026-08-27 이동윤 계약 정정 검증

- 기준 Branch·HEAD: `dongyoon@6427755ac13d9e0e41a046f83f399e0e80928d59`
- `ConsultationContextSynthesisInput`은 Danger에만
  `safety_requires_consultation=true`와 Safety Rule ID를 강제한다.
  `HARNESS_ESCALATE`와 `FAIL_CLOSED_CONSULTATION`은 실제 Safety 판정이
  `false/unknown`이어도 허용한다.
- Agent 표적: `43 passed` — `PASS`
- Harness/Handoff 연결 표적: `18 passed` — `PASS`
- AI 전체 Unit: `1 failed, 662 passed, 4 warnings, 41 subtests passed` —
  `PARTIAL`
- 단독 재현:
  `ai/tests/unit/harness/test_otel_tracing.py::test_span_attributes_are_metadata_only`
  — `FAIL`
- 실패 원인: Production Handoff Span에 추가된
  `waterbridge.handoff.context_synthesis.present`와
  `waterbridge.handoff.context_synthesis.status`가 윤승혁 소유 OTel 메타데이터
  Allowlist 테스트 기대값에 반영되지 않았다. Production 속성의 허용 여부를
  윤승혁이 검수하고 테스트를 갱신한 뒤 전체 Unit을 재실행해야 한다.
- 실제 Provider·Backend 저장/Replay·Web 소비: `NOT_RUN`

회신 형식:

```text
owner=윤승혁
reviewed_commit=<40자리 SHA>
shared_file_editor=<이름>
routing_trigger_contract=APPROVED | CHANGES_REQUIRED
handoff_dto_contract=APPROVED | BLOCKED_BY_BACKEND
harness_handoff_target_tests=PASS | FAIL | NOT_RUN
runtime_status=CONNECTED | PARTIAL | HOLD
remaining_blocker=<없음 또는 담당자·해제 조건>
```
