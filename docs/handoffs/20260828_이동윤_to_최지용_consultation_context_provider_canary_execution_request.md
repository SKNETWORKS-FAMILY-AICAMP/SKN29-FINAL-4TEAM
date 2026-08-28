# Consultation Context Provider Canary 실행 인계

수신: 최지용

발신: 이동윤

작성일: 2026-08-28

## 결론

이번 실행은 **Provider 컴포넌트 Canary**다. 운영 API를 변경하지 않으며,
Backend의 가이드 거절 요청이 AI를 자동 재개하는 전체 서비스 E2E가 아니다.

전용 Runner는 같은 AI Process 안에서 다음만 검증한다.

1. Harness가 입력 Evidence를 전부 승인한다.
2. 최초 가이드 결과가 `PRE_SEND_HUMAN_REVIEW`로 분기된다.
3. 최초 검토 대기 단계에서는 맥락정리 Agent와 Provider가 호출되지 않는다.
4. 동일 Checkpoint에 `REJECT`를 적용한 뒤에만 맥락정리 Agent와 Provider가
   각각 정확히 한 번 호출된다.
5. Provider 합성이 성공한 경우에만 Handoff `2.0.0`을 만들고, 명시적 실행
   옵션이 있을 때만 Backend로 전송한다.
6. 같은 Handoff 객체를 한 번 더 보내 Backend Replay 중복 방지를 확인한다.

Provider Fallback이 발생하면 기존 운영 Handoff 동작과 달리 이 Canary는
Backend 전송 전에 중단한다. 이번 시험의 목적이 결정론적 Fallback 확인이 아니라
실제 Provider 성공 경로 확인이기 때문이다.

## 기준 코드와 파일

- Runner 도입 Commit:
  `141829c438f5133a30538ef0ac91a1081b1cd2a2`
- `official_verified` 보강 최신 main 동기화 기준:
  `4f71692a754836757b7d6437916c7c0a33a09623`
- Runner:
  `ai/scripts/run_consultation_context_provider_canary.py`
- 단위 테스트:
  `ai/tests/unit/test_consultation_context_provider_canary.py`
- 실제 실행 기준 Commit: **보강본 main 병합 후 새 40자리 SHA로 별도 회신 예정**

`execute` 모드는 전달받은 실행 기준 Commit과 현재 `HEAD`가 다르거나 작업 트리가
Dirty이면 실패한다. 따라서 위 도입·보강 기준 Commit을 실제 실행 SHA로 사용하면
안 된다.

## 최지용님이 제공할 식별자

공식 검토 API에서 신규 합성 문의의 가이드를 `REJECT` 처리한 뒤 아래 값을
전달해 주면 된다.

- `inquiry_id`: 공개 Inquiry UUID
- `correlation_id`: 해당 AI 실행의 Correlation UUID
- `ai_request_id`: 해당 AI 실행의 멱등 식별자
- `source_inquiry_state_version`: 거절 대상 가이드가 생성된 Inquiry Version
- `review_id`: Backend HumanReview 공개 UUID
- `review_state_version_after_reject`: 공식 거절 처리 후 Review Version
- `checkpoint_thread_id`: Backend HumanReview에 저장된 `hitl-` 형식 식별자

Runner 입력에서는 `source_inquiry_state_version`을 `state_version` 필드에 넣는다.
Runner는 `inquiry_id + ai_request_id + state_version`으로 Checkpoint ID를 다시
계산해 Backend가 제공한 값과 다르면 Provider 호출 전에 중단한다.

`review_id`와 거절 후 Review Version은 Backend 기록과 AI 실행 보고서를 같은
건으로 결속하기 위한 참조값이다. 현재 Handoff 공개 계약 필드에는 추가하지 않는다.

## 보호 입력 준비 원칙

- 신규 합성 문의만 사용하고 완료된 기존 문의는 재사용하지 않는다.
- 입력은 `data_classification=synthetic`, 모델은 `WPUJAC104DWH`, 위험도는
  `caution`, 사용 안내는 `PARTIAL_STOP`으로 제한한다.
- Evidence는 해당 모델과 정확히 일치하며 `official_verified`,
  `allowed_use=true`, `runtime_eligible=true`인 항목만 넣는다.
- `team_verified`를 포함한 다른 검증 상태는 입력 검증에서 거절하고 Provider와
  Backend를 호출하지 않는다.
- 실제 고객 원문, 전화번호, 이메일, 계정 정보, Secret은 넣지 않는다.
- 입력 JSON과 실행 보고서는 저장소 밖 또는 Git에서 무시되는
  `.runtime/consultation-context-provider-canary/` 아래에만 둔다.
- 입력 본문과 Evidence 본문은 Git, 인계문서, 채팅, 테스트 로그에 복사하지 않는다.
- 입력 스키마는 아래 `schema` 명령으로 확인한다. 저장소에는 입력 예시를
  추가하지 않았다.

현재 맥락정리 Provider에는 Evidence 본문·문서명·Chunk ID를 보내지 않는다.
Provider에는 비식별·허용목록을 통과한 구조화 증상과 Safety Source만 전달하고,
Harness 승인 Evidence는 Provider 응답 검증 후 결정론적으로 상담사 Brief와
Handoff에 결합한다.

## 필요한 환경변수

값은 문서나 채팅에 남기지 않고 보호된 Process 환경으로만 주입한다.

| 환경변수 | 용도 | 필요 시점 |
| --- | --- | --- |
| `OPENAI_API_KEY` | 실제 맥락정리 Provider 인증 | `execute` 필수 |
| `OPENAI_BASE_URL` | 승인된 공식 HTTPS `/v1` Endpoint, 생략 시 코드 기본값 | Provider를 기본 Endpoint 외에서 사용할 때만 |
| `AI_HANDOFF_BACKEND_ENABLED` | Handoff HTTP 전송 명시 활성화 | `--send-handoff` 사용 시 `true` 필수 |
| `AI_BACKEND_BASE_URL` | 보호형 Local Backend 주소 | `--send-handoff` 필수 |
| `AI_HANDOFF_INTERNAL_TOKEN` | AI→Backend 내부 인증 Token | `--send-handoff` 필수 |
| `AI_HANDOFF_TIMEOUT_SECONDS` | Handoff 전송 Timeout | 선택, 코드 허용 범위 사용 |

`AI_PIPELINE_RUNTIME`이나 공개 FastAPI Route는 이 Runner가 사용하지 않는다.

## 정확한 실행 명령

저장소 Root에서 Python `3.13.13` 가상환경으로 실행한다.

### 1. 입력 스키마 확인

```powershell
.\ai\.venv\Scripts\python.exe -m ai.scripts.run_consultation_context_provider_canary --mode schema
```

### 2. Provider 미호출 사전 점검

```powershell
.\ai\.venv\Scripts\python.exe -m ai.scripts.run_consultation_context_provider_canary `
  --mode inspect `
  --input .runtime\consultation-context-provider-canary\input.json `
  --report .runtime\consultation-context-provider-canary\inspect-report.json
```

이 단계는 Provider와 Backend를 호출하지 않는다. 출력의 다음 조건을 확인한다.

- `overall_status=INSPECTED`
- `harness_decision=PASS`
- `routing_disposition=PRE_SEND_HUMAN_REVIEW`
- `initial_review_status=WAITING_FOR_REVIEW`
- `initial_context_agent_calls=0`
- `initial_provider_calls=0`
- `initial_handoff_present=false`

Inspect 보고서의 `input_sha256`과 `evidence_binding_sha256`을 양측이 확인한 뒤,
동일 Hash의 합성 입력을 외부 Provider에 보내는 것을 이동윤이 별도로 승인받는다.

### 3. Provider 실행과 Backend 전송·Replay

```powershell
.\ai\.venv\Scripts\python.exe -m ai.scripts.run_consultation_context_provider_canary `
  --mode execute `
  --input .runtime\consultation-context-provider-canary\input.json `
  --report .runtime\consultation-context-provider-canary\execute-report.json `
  --expected-git-sha <RUNNER_COMMIT_40_SHA> `
  --expected-input-sha256 <INSPECT_INPUT_SHA256> `
  --expected-evidence-sha256 <INSPECT_EVIDENCE_SHA256> `
  --allow-provider-input `
  --send-handoff `
  --verify-replay
```

`--allow-provider-input`은 사전 승인된 동일 Hash 입력에 한해서만 사용한다.
`--send-handoff`를 빼면 Provider 컴포넌트까지만 실행하고
`overall_status=AI_COMPONENT_PASS`로 끝난다. `--verify-replay`는
`--send-handoff`와 함께만 사용할 수 있다.

## Hash 산정 방식

- `input_sha256`: Pydantic 검증을 통과한 전체 입력을 JSON mode로 변환한 뒤
  Key 정렬, 공백 없는 구분자, ASCII Escape를 적용한 UTF-8 Byte의 SHA-256이다.
- `evidence_binding_sha256`: Evidence를 `chunk_id` 순으로 정렬하고 다음 값만
  정규화한 배열의 SHA-256이다.
  - `chunk_id`, `model_code`, `page`, `source_hash`
  - `verification_status`, `allowed_use`, `runtime_eligible`
  - 문서명·본문·요약 각각의 SHA-256

보고서에는 문서명·본문·요약 원문을 남기지 않는다. 어느 한 값이라도 바뀌면
`execute`가 Hash 불일치로 Provider 호출 전에 중단한다.

## AI 측 성공 증거

최종 AI 보고서는 원문·Prompt·생성 Brief·Secret 없이 다음만 남긴다.

- Git Branch, 40자리 SHA, `origin/main` SHA, Dirty 여부
- Inquiry·Correlation·AI Request·Review·Checkpoint 식별자와 Version
- 입력·Evidence 결속 Hash
- Harness 결정과 승인 Evidence Chunk ID
- 최초 단계 Agent·Provider 호출 횟수 `0/0`
- 거절 적용 후 Review 상태 `COMPLETED`, 결정 `reject`
- 전체 맥락정리 Agent·Provider 호출 횟수 `1/1`
- `provider_input_explicitly_allowed=true`
- `context_synthesis_status=SUCCEEDED`
- `context_synthesis_fallback_reason=null`
- `provider_called=true`, Provider Model·Prompt Version·Token 수
- `handoff_schema_version=2.0.0`
- Handoff와 맥락 Brief의 Evidence ID가 Harness 승인 집합의 부분집합인지 여부
- 최초 전송과 Replay의 상태·HTTP Status·내부 전송 시도 횟수

최종 완료 조건은 `overall_status=PASS`, 최초 전송 `DELIVERED`, Replay
`DELIVERED`, Backend Handoff 원장 1건, 상담 연결 1건, 상담사 상세 조회 반영이다.
AI 보고서만으로 Backend 저장이나 화면 반영을 PASS 처리하지 않는다.

## 실패와 재실행 기준

- Provider Fallback, 호출 횟수 불일치, 식별자·Git SHA·입력 Hash 불일치,
  Handoff 거절, 비밀정보 노출이 확인되면 즉시 중단한다.
- 보고서 파일은 덮어쓰지 않는다. 재실행 시 새 경로를 사용한다.
- Provider 호출 전에 실패했다면 원인을 수정하고 Inspect부터 다시 수행한다.
- Provider 호출 후 Handoff 전송 전 실패했다면 원인을 분리하고, 같은 Hash를 다시
  외부 Provider에 보내기 전에 재승인을 받는다.
- Backend 수신 성공 여부가 불명확하거나 한 번이라도 성공했다면 Provider를 다시
  호출하지 않는다. Backend 원장과 멱등 기록을 먼저 확인한다.
- Handoff Client 내부의 일시 오류 재시도는 최대 1회이며, 최초 전송과 명시적
  Replay는 서로 다른 Handoff 전송 호출이다. 두 호출은 같은 Runner 실행에서
  같은 Handoff 객체를 사용하며 Provider는 다시 호출하지 않는다.

## 현재 판정

- Runner와 Fake Provider 단위 경로: 구현 완료
- 실제 Provider 입력 승인: `HOLD`
- 최지용 신규 Backend 식별자 전달: `HOLD`
- 실제 Provider Canary: `NOT_RUN`
- Backend 저장·Replay·상담사 상세 조회: `NOT_RUN`
- Backend 가이드 거절→AI 자동 재개 전체 서비스 E2E: 이번 범위 밖
- 운영 활성화: `HOLD`
