# Consultation Context Provider Canary 실행 전 보강 회신

수신: 최지용

발신: 이동윤

작성일: 2026-08-28

공식 caution 계약 정정일: 2026-08-30

## 결론

요청한 세 항목을 기준으로 Runner 입력 연결 기준, `official_verified` 전용 제한,
실행·승인·재실행 기준을 아래와 같이 확정한다.

이번 시험은 Provider 컴포넌트 Canary다. Backend 공식 가이드 거절이 AI를 자동
재개하는 전체 서비스 E2E 또는 운영 활성화 시험이 아니다. 실제 Provider와
Backend HTTP 호출은 최종 main SHA와 두 Hash를 승인하기 전까지 실행하지 않는다.

## 1. Runner 전체 입력 항목의 연결 기준

### 1.1 최상위 식별자와 실행 조건

| Runner 입력 | 기준 원천 | 이동·고정 기준 | Inspect 전 검증 | 상태 |
| --- | --- | --- | --- | --- |
| `schema_version` | Canary Runner 계약 | `1.1.0` 고정 | 다른 값 거절 | AI 확정 |
| `environment_id` | Canary 실행 담당자 | 실제 보호형 실행 환경을 나타내는 비밀이 아닌 식별자 사용 | `^[A-Z0-9][A-Z0-9_.-]{2,99}$` | AI 확정 |
| `backend_release_sha` | AWS Backend 원장 Release | 원장을 생성한 Release의 40자리 Commit SHA를 그대로 사용 | 소문자 16진수 40자리, Runner `git_sha`와 별도 기록 | Backend 확정 |
| `data_classification` | Canary 정책 + Backend 합성 고객 기록 | `synthetic` 고정 | Backend 고객과 연결 User 모두 `is_synthetic=true`인지 확인 | Backend 확인 필요 |
| `inquiry_id` | `Inquiry.public_id` | 내부 정수 PK 금지 | `AIRun.inquiry`, `HumanReview.inquiry`와 동일 UUID | Backend 확정 |
| `correlation_id` | 원본 `AIRun.correlation_id` | HumanReview 결정 Correlation을 사용하지 않음 | 원본 AIRun과 Handoff 대상 Correlation 일치 | Backend 확정 |
| `ai_request_id` | 원본 `AIRun.idempotency_key` | `AIRun.public_id`를 사용하지 않음 | `HumanReview.source_ai_request_id`와 일치 | Backend 확정 |
| `state_version` | `AIRun.input_payload.state_version` | 현재 Inquiry Version으로 교체하지 않음 | `HumanReview.source_inquiry_state_version`과 일치 | Backend 확정 |
| `backend_review_id` | `HumanReview.public_id` | 공개 UUID 그대로 사용 | 동일 Inquiry·Guidance의 Review인지 확인 | Backend 확정 |
| `backend_review_state_version_after_reject` | 거절 완료 후 `HumanReview.review_state_version` | 거절 API 요청 Version이 아니라 응답의 증가된 Version 사용 | `status=REJECTED`, `decision=REJECT`, 값 `>=2` | Backend 확정 |
| `checkpoint_thread_id` | `HumanReview.checkpoint_thread_id` | 문자열을 재작성하지 않음 | Inquiry ID·AI Request ID·State Version으로 AI가 다시 계산한 값과 일치 | Backend 내부 조회 방식 확인 필요 |
| `model_code` | Inquiry 구독 제품 + AIRun 입출력 | `WPUJAC104DWH` 고정 Canary | Inquiry 제품, `AIRun.input_payload.model_code`, `validated_output_payload.model_code`, 모든 Evidence 제품과 일치 | 공동 확인 |
| `product_family` | AI Harness Product Registry | `DIRECT_WATER_PURIFIER` 고정 | Exact Model Registry 결과와 일치 | AI 확정 |
| `runtime_product_approved` | AI Runtime Profile·Product Registry | `true` 고정 | 실행 Commit의 승인 모델 목록에 Exact Model 존재 | AI 확정 |

`HumanReview` 공개 응답에는 현재 `checkpoint_thread_id`와
`source_ai_request_id`가 모두 포함되지 않는다. 최지용님이 보호된 DB 조회 또는
Canary 전용 Export 중 어떤 방식으로 제공할지 확인한다. 공개 API 계약을 임의로
변경하지 않는다.

### 1.2 구조화 증상

아래 값은 모두 같은 `AIRun.validated_output_payload.structured_symptom`에서
그대로 가져온다. 현재 Inquiry나 화면 표시값으로 다시 만들지 않는다.

| Runner 입력 | 변환 기준 | 검증 기준 |
| --- | --- | --- |
| `structured_symptom.symptom_type` | 변환·번역·동의어 치환 없음 | Provider 허용 증상 유형이며 원본 AIRun 값과 동일 |
| `structured_symptom.occurrence_time` | `null` 포함 그대로 유지 | 원본 AIRun 값과 동일 |
| `structured_symptom.target_water_type` | `null` 포함 그대로 유지 | 값이 있으면 Provider 허용 출수 종류인지 확인 |
| `structured_symptom.occurrence_condition` | `null` 포함 그대로 유지 | 원본 AIRun 값과 동일 |
| `structured_symptom.error_code` | 대소문자 변경 없음 | 값이 있으면 허용 형식이며 원본과 동일 |
| `structured_symptom.accompanying_symptoms` | 원래 순서 보존 | 배열 전체가 원본과 동일 |
| `structured_symptom.actions_taken` | 원래 순서 보존 | 배열 전체가 원본과 동일 |

### 1.3 이전 답변

같은 `AIRun.input_payload.previous_answers`를 사용한다.

| Runner 입력 | Backend 입력 | 변환·검증 기준 |
| --- | --- | --- |
| `previous_answers[].field_name` | `previous_answers[].question_id` | Key 이름만 변경하고 값은 변경하지 않음 |
| `previous_answers[].answer_text` | `previous_answers[].answer_text` | 원문 그대로 사용하고 순서 보존 |

Runner는 답변 길이를 500자로 제한한다. Backend 입력이 500자를 초과하면 자르거나
요약하지 않고 해당 Canary Case를 거절한다.

### 1.4 Safety 판정

아래 값은 모두 같은 `AIRun.validated_output_payload.safety_assessment`에서
가져온다.

| Runner 입력 | 변환 기준 | 이번 Canary 고정 조건 |
| --- | --- | --- |
| `safety_assessment.risk_level` | 원본 값 그대로 | `caution` |
| `safety_assessment.priority` | 원본 값 그대로 | `consultation_recommended` |
| `safety_assessment.requires_consultation` | 원본 Boolean 그대로 | `false` |
| `safety_assessment.matched_safety_rule_ids` | 순서 보존 | 정확히 `["SAFETY-TEMP-ABNORMAL-001"]` |
| `safety_assessment.detected_risks` | 순서 보존 | 원본 AIRun과 동일 |
| `safety_assessment.safety_reason` | 변환·요약 없음 | 원본 AIRun과 동일 |

조건이 다르면 값을 고치지 않고 신규 합성 문의를 다시 선정한다.
다른 caution Rule, 임의 Rule, danger Rule 또는 기존 테스트 전용 조합인
`requires_consultation=true + 빈 Rule 목록`은 Provider 호출 전에 거절한다.

### 1.5 사용 안내

아래 값은 같은 `AIRun.validated_output_payload.usage_guidance`에서 가져온다.
Backend `HumanReview.proposed_guidance`는 화면·업무용 Guidance 형태로 변환된
결과이므로 Runner 입력을 역산하는 기준으로 사용하지 않는다.

| Runner 입력 | 변환 기준 | 이번 Canary 고정 조건 |
| --- | --- | --- |
| `guidance.guidance_status` | 원본 값 그대로 | `PARTIAL_STOP` |
| `guidance.message` | 변환·요약 없음 | 원본 AIRun과 동일 |
| `guidance.restricted_functions` | 순서 보존 | 원본 AIRun과 동일 |
| `guidance.next_actions` | 순서 보존 | 원본 AIRun과 동일 |

### 1.6 Evidence

Evidence 목록과 순서는 같은 `AIRun.validated_output_payload.evidence_references`를
기준으로 한다. 본문·Source Hash·제품 Metadata는 동일 `chunk_id`를
`backend_ai_rag_chunks_v1` Readonly View에서 조회해 결합한다.

| Runner 입력 | 기준 원천 | 이동·검증 기준 |
| --- | --- | --- |
| `evidence[].chunk_id` | AIRun Evidence Reference + RAG View | 두 원천에 같은 ID가 존재하고 AIRun 순서 보존 |
| `evidence[].document_title` | AIRun Reference + View Metadata | 두 값이 완전히 동일 |
| `evidence[].page` | AIRun `page`, 필요 시 View 대표 Page | AIRun `page`가 있으면 그대로 사용. `null`이면 View Page가 AIRun `page_refs`에 포함될 때만 사용. 아니면 Case 거절 |
| `evidence[].model_code` | RAG View | Inquiry와 AIRun의 Exact Model과 일치 |
| `evidence[].content` | RAG View `content` | 수정·요약·공백 정리 없이 사용. 4,000자 초과 시 자르지 않고 Case 거절 |
| `evidence[].summary` | AIRun Evidence Reference | 원본 그대로 사용. 2,000자 초과 시 Case 거절 |
| `evidence[].source_hash` | RAG View Metadata | 소문자 64자리 SHA-256으로 정규화하고 View 원문 Hash와 일치 |
| `evidence[].similarity_score` | AIRun Evidence Reference | `null` 금지, `0.0..1.0` 범위 그대로 사용 |
| `evidence[].verification_status` | AIRun Reference + RAG View | 양쪽 모두 정확히 `official_verified`여야 함 |
| `evidence[].allowed_use` | RAG View | 정확히 `true` |
| `evidence[].runtime_eligible` | Readonly View 진입 조건 + AI DTO | 정확히 `true`; View 밖 행을 임의 승격하지 않음 |

Evidence 본문은 Provider에 전달하지 않는다. Provider에는 허용목록을 통과한
구조화 증상과 Safety Source만 전달하며, Evidence는 Provider 결과 검증 후
결정론적으로 Brief와 Handoff에 결합한다. 그러나 최종 Handoff가 같은 AIRun의
공식 Evidence와 일치해야 하므로 위 결속 검증은 Provider 호출 전에 완료한다.

### 1.7 최지용 확인이 필요한 Backend 항목

다음은 AI가 임의로 정하지 않는다.

1. `checkpoint_thread_id`, `source_ai_request_id`, 원본 AIRun 입출력 Payload를
   보호된 방식으로 Export하는 절차
2. 신규 합성 Customer와 연결 User의 `is_synthetic=true` 확인 방법
3. `AIRun.idempotency_key + correlation_id + inquiry_id`로 동일 실행을 조회하는
   Backend 기준
4. `backend_ai_rag_chunks_v1`의 동일 `chunk_id` 조회 결과를 이번 Canary 입력에
   제공하는 보호 절차
5. 공식 Review 거절 후 `review_state_version`, `status=REJECTED`,
   `decision=REJECT` 증거 형식

위 항목은 값 본문을 채팅에 붙이지 않고, 보호된 실행 Host의 입력 파일 또는
비식별 ID·Hash 증거로 전달한다.

## 2. `official_verified` Evidence 전용 제한

이번 Canary Runner는 `verification_status=official_verified`만 허용하도록
제한한다.

- `team_verified`와 그 외 값은 입력 Schema 검증에서 거절한다.
- 거절 결과는 `failure_stage=INPUT`,
  `failure_code=INPUT_VALIDATION_FAILED`다.
- 입력 검증 실패이므로 Context Agent·Provider·Backend Handoff 호출은 모두
  `0회`다.
- 공통 AI Evidence 계약과 Production Harness의 기존 허용 범위는 변경하지 않는다.
- 이번 제한은 Canary Runner와 해당 테스트·문서에만 적용한다.

Backend Handoff v2는 전송 Payload에서 검증 상태를 받지 않고, 연결된
`AIRun.validated_output_payload.evidence_references`를 다시 조회해 모든 항목이
`official_verified`인지 확인한다. 따라서 Runner 입력과 동일 AIRun 기록 양쪽이
모두 공식 검증 상태여야 한다.

## 3. 실제 실행·승인·재실행 기준

### 3.1 Commit 기준

- AWS Backend 원장 기준 Release (`v0.3.1`):
  `d1ffd2739883d8c8fedc934131335ed1b1a28dbc`
- Runner 정정 작업의 최신 main 기준:
  `d0a8c9848cf8613079a82fbfbad6781c1b890e95`
- 위 두 값은 역할이 다르다. 입력·보고서의 `backend_release_sha`에는 AWS 원장
  Release를, 보고서의 `git_sha`에는 실제 Runner 실행 Commit을 기록한다.
- 정정 변경이 main에 병합된 뒤 `git fetch origin`을 실행하고 Runner 실행용
  `origin/main`의 40자리 SHA를 양측이 다시 고정한다.
- 실제 실행 보고서의 `git_sha`는 고정한 Runner SHA와 같고
  `git_dirty=false`여야 한다.

### 3.2 Clean Worktree 준비

로컬 변경이 있으면 `reset --hard`나 `clean -fd`로 지우지 않는다. 변경을 별도
커밋하거나 안전하게 보관한 뒤 최신 main 전용 Clean Checkout에서 실행한다.

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
git rev-parse HEAD
git status --porcelain
.\ai\.venv\Scripts\python.exe --version
```

완료 조건:

- `git rev-parse HEAD`가 합의한 40자리 main SHA와 일치
- `git status --porcelain` 출력이 비어 있음
- Python `3.13.13`
- 보호 입력과 보고서는 Git에서 무시되는 `.runtime/**` 또는 저장소 밖에 존재

### 3.3 Inspect 명령

```powershell
.\ai\.venv\Scripts\python.exe -m ai.scripts.run_consultation_context_provider_canary `
  --mode inspect `
  --input .runtime\consultation-context-provider-canary\input.json `
  --report .runtime\consultation-context-provider-canary\inspect-report.json
```

Inspect 완료 조건:

- `overall_status=INSPECTED`
- `harness_decision=PASS`
- `routing_disposition=PRE_SEND_HUMAN_REVIEW`
- 최초 Context Agent·Provider 호출 `0/0`
- 최초 Handoff 없음
- 모든 Evidence가 `official_verified`

### 3.4 Hash 확인과 승인 담당

1. 최지용: Backend 원본 기록과 Runner 입력의 식별자·AIRun 입출력·Review 상태
   연결을 확인한다.
2. 이동윤: AI Runtime 정책, RAG View Evidence, Runner Inspect 결과와
   `official_verified` 제한을 확인한다.
3. 최지용과 이동윤은 같은 보호 입력 파일에서 생성된 `input_sha256`과
   `evidence_binding_sha256`이 동일한지 확인한다.
4. 이동윤은 두 확인이 끝난 동일 Hash 입력에 대해서만 외부 Provider 호출을
   명시적으로 승인한다.
5. 윤승혁 PM은 실행 후 AI·Backend 결과를 합쳐 최종 Canary 판정을 검수한다.

채팅·회신문에 남기는 승인 증거는 다음 값으로 제한한다.

```text
git_sha
backend_release_sha
inquiry_id
correlation_id
ai_request_id
review_id
checkpoint_thread_id
input_sha256
evidence_binding_sha256
backend_binding_checked_by
ai_rag_binding_checked_by
approved_at
```

입력 본문, Evidence 본문, Provider Prompt, Token 값은 남기지 않는다.

### 3.5 Execute 명령

```powershell
.\ai\.venv\Scripts\python.exe -m ai.scripts.run_consultation_context_provider_canary `
  --mode execute `
  --input .runtime\consultation-context-provider-canary\input.json `
  --report .runtime\consultation-context-provider-canary\execute-report.json `
  --expected-git-sha <FINAL_MAIN_40_SHA> `
  --expected-input-sha256 <APPROVED_INPUT_SHA256> `
  --expected-evidence-sha256 <APPROVED_EVIDENCE_SHA256> `
  --allow-provider-input `
  --send-handoff `
  --verify-replay
```

Handoff는 기본적으로 자동 전송하지 않는다. `--send-handoff`와
`AI_HANDOFF_BACKEND_ENABLED=true`가 모두 있을 때, Provider 합성이
`SUCCEEDED`인 경우에만 전송한다. Replay는 같은 실행에서 같은 Handoff 객체를
다시 전송하며 Provider를 두 번째로 호출하지 않는다.

### 3.6 실패 상황별 재실행 기준

| 상황 | 즉시 조치 | Provider 재호출 | 재승인 |
| --- | --- | --- | --- |
| Provider 호출 전 입력·식별자·SHA·Hash·설정 실패 | 원인 수정 후 새 보고서 경로로 Inspect부터 재실행 | 호출 전이므로 없음 | 입력·Evidence·ID·Commit 중 하나라도 바뀌면 필요 |
| Provider 호출 후 Synthesis Fallback·출력 검증 실패 | Backend 전송 없이 중단하고 원인 분리 | 자동 재호출 금지 | 같은 Hash여도 두 번째 외부 호출 전 필요 |
| Handoff가 명확한 4xx·Evidence·Stale 오류로 거절 | Backend 기록과 입력 연결 오류를 먼저 수정 | 즉시 재호출 금지 | 수정된 입력으로 Inspect와 Hash 공동 승인 필요 |
| Handoff Timeout·Network로 저장 여부 불명확 | Backend 원장·멱등 기록을 먼저 조회 | 저장 여부 확인 전 금지 | Backend 저장 0건이 확인되고 새 Provider 실행이 필요할 때 필요 |
| 최초 Handoff `DELIVERED`, Replay 실패 또는 결과 불명확 | Handoff 1건과 상담 연결 상태를 Backend에서 확인 | 금지 | Provider 재실행 대신 Backend 결과 검수 |
| 최초·Replay 모두 `DELIVERED` | Handoff·상담 연결 각 1건과 상담사 상세 반영 확인 | 금지 | 불필요 |

다음 조건에서는 Provider를 다시 호출하면 안 된다.

- Backend에 Handoff가 1건이라도 저장된 경우
- Backend 수신 성공 여부가 아직 불명확한 경우
- 최초 전송은 성공하고 Replay 확인만 실패한 경우
- 같은 실행의 멱등 상태를 Backend에서 아직 확인하지 않은 경우

다음 조건에서는 재승인이 필요하다.

- Git Commit, Inquiry·AIRun·Review 식별자 중 하나가 변경됨
- 입력 또는 Evidence Hash가 변경됨
- Provider Endpoint·Model Profile이 변경됨
- Provider가 한 번이라도 호출된 뒤 다시 호출하려 함

보고서 파일은 덮어쓰지 않으며 재실행마다 새 경로를 사용한다. Handoff Client의
일시 오류 내부 재시도는 최대 1회이며, 이것을 새 Provider 호출로 계산하지 않는다.

## 4. 다음 협업 순서

1. 이동윤: Runner 제한·테스트·본 기준 문서를 main 병합 가능한 상태로 전달
2. 최지용: 1.7의 Backend 확인 항목 회신
3. 윤승혁 PM: 보강본 병합 확인
4. 최지용: 신규 합성 Backend 기록과 보호 입력 준비 후 Inspect 실행
5. 최지용·이동윤: 식별자·두 Hash 공동 확인
6. 이동윤: 동일 입력 Provider 실행과 Handoff·Replay 수행
7. 최지용: 저장 1건·중복 방지·상담 연결·상담사 상세 반영 확인
8. 윤승혁 PM: 양측 결과 최종 검수

## 5. 보강 검증 결과

검증 기준은 Branch `dongyoon`, 최신 main Commit
`d0a8c9848cf8613079a82fbfbad6781c1b890e95`에 이번 정정을 적용한 작업 트리다.
아직 커밋·main 병합 전이므로 이 Commit을 정정본의 실제 Runner 실행 SHA로
사용하지 않는다.

- Python: `3.13.13` — `PASS`
- Runner·Test Python Compile — `PASS`
- Runner 입력·보고서 Schema `1.1.0`, 공식 caution 조합 통과, 기존
  `true + 빈 Rule` 및 임의·danger Rule 거절 — `PASS`
- 비공식 Evidence Provider 호출 전 거절 — `PASS`
- Runner·맥락정리 Agent·HITL·Harness·Handoff·v2 Contract 표적:
  `141 passed in 1.18s` — `PASS`
- AI 전체 Unit:
  `703 passed, 4 warnings, 41 subtests passed in 25.52s` — `PASS`
- `git diff --check` — `PASS`
- 변경 파일 Secret·DSN Literal 확인: 검출 없음 — `PASS`
- 실제 Provider 호출: `NOT_RUN`
- 실제 Backend Handoff·Replay: `NOT_RUN`
- 최종 실행용 main 40자리 SHA 고정: 커밋·병합 후 수행 — `HOLD`
