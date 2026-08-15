# 김은진 → 이동윤·최지용: AI RAG Customer Guidance G1-B 공동실행 재검증 회신 v0.1

> 발신: 김은진 — Data·QA·DevOps
>
> 수신: 이동윤 — AI·RAG, 최지용 — Backend·Database
>
> 참조: 윤승혁 — PM·기술 통합
>
> 작성·검증일: 2026-08-14 KST
>
> 상태: `DB_READY / PGVECTOR_PASS / MOBILE_LOCAL_PASS / ACTUAL_OPENAI_FAIL / G1B_HOLD`

## 1. 회신 결론

TEAM_INTEGRATION DB, 승인 7개 Evidence, Crosswalk, Readonly View와 AI 최소권한
Role은 `READY`다. 현재 `origin/main`과 일치하는
`004688132b623f5d2f8f24add558f6c3d5ce24d6`에서 AI 표적 회귀와 실제 pgvector
검색도 다시 통과했다.

그러나 사용자 승인 범위의 합성 입력을 `store=false`로 실제
`gpt-4.1-mini` Responses API에 전송한 Local Runtime Gate가 다시 실패했다.
정상 Guidance 선행 Gate가 통과하지 않아 Backend·AI Runtime을 새 SHA로 함께
기동하지 않았고, 정상 Guidance 저장·고객 GET 200·NO_EVIDENCE·DANGER는
실행하지 않았다.

따라서 현재 판정은 `G1B_BLOCKED_AI_PROVIDER_REQUEST`이며 다음 실행 주체는
이동윤이다. AI Provider 경계 교정과 새 40자리 SHA 회신 전까지 전체 G1-B와
후속 시나리오를 `PASS`로 확대하지 않는다.

최지용 Author Host의 `SM_X610(R54WC016MWV)` 연결과
`adb reverse tcp:8000 tcp:8000` 준비는 `AUTHOR_REPORTED`로 접수했다. 김은진
QA Host에서는 로컬 Emulator Gate만 별도로 통과했으며, 이를 Galaxy 실기기 또는
실제 Backend Remote Smoke PASS로 확대하지 않는다.

## 2. 구조화 회신

```ini
sender=김은진
receiver=이동윤,최지용
scope=AI_RAG_CUSTOMER_GUIDANCE_G1B_JOINT_RETRY
qa_head_sha=004688132b623f5d2f8f24add558f6c3d5ce24d6
origin_main_sha=004688132b623f5d2f8f24add558f6c3d5ce24d6
local_main_ref=ed4afa79c4f24393ec03740e4a2da10e0073288a
same_final_main_three_party_ack=NO
head_unchanged_during_retry=PASS
ai_targeted_regression=43 passed,3 warnings
g1b_readiness=READY
g1b_readiness_exit=0
team_database_identity=waterbridge_team_integration
actual_pgvector=PASS
actual_openai=FAIL
openai_model=gpt-4.1-mini
openai_store=false
latest_openai_failure=LOCAL_RUNTIME_GENERALIZED_FAILURE
confirmed_previous_failure=GuidanceGenerationExecutionError_to_LLMOutputValidationError_HTTP_400
joint_happy_path=BLOCKED_BEFORE_NEW_BACKEND_AI_RUNTIME
guidance_persistence=NOT_RUN
customer_guidance_get_200=NOT_RUN
replay_duplicate_zero=NOT_RUN_ON_LATEST_SHA
correlation_end_to_end=NOT_RUN_ON_LATEST_SHA
no_evidence=NOT_RUN_WAIT_HAPPY_PATH
danger_total_stop=NOT_RUN_WAIT_HAPPY_PATH
ai_health=NOT_RUNNING_AFTER_GATE
backend_health=NOT_STARTED_AI_GATE_BLOCKED
ai_service_base_url=NOT_CONFIGURED_FOR_LATEST_RETRY
environment_ready=DB_AND_PGVECTOR_READY_AI_RUNTIME_FAIL
qa_decision=BLOCKED_AI_PROVIDER_REQUEST
joint_execution_time=2026-08-14 KST
secret_values_printed=NO
next_owner=이동윤
qa_host_mobile_local_gate=PASS
qa_host_mobile_local_tests=11
qa_host_mobile_local_passed=7
qa_host_mobile_remote_expected_skips=4
qa_host_mobile_failures=0
author_host_sm_x610=AUTHOR_REPORTED_READY
author_host_adb_reverse_8000=AUTHOR_REPORTED_READY
```

## 3. 검증 기준과 SHA 경계

| 항목 | 값 | 판정 |
| --- | --- | --- |
| QA Checkout | `004688132b623f5d2f8f24add558f6c3d5ce24d6` | `origin/main` 일치 |
| 로컬 `main` Ref | `ed4afa79c4f24393ec03740e4a2da10e0073288a` | 최신 원격과 불일치 |
| 재시도 중 HEAD | 시작·종료 동일 | PASS |
| 이전 실제 공동실행 SHA | `ed4afa79c4f24393ec03740e4a2da10e0073288a` | 최신 재시도와 미합산 |
| 최신 Commit의 AI 변경 | 없음 | Provider 교정 증거 없음 |
| 최신 Commit의 관련 변경 | Backend 합성 E2E Readonly 감사도구 추가 | AI 실패 원인과 무관 |

최지용·이동윤 Host의 동일 SHA ACK는 이번 단독 재시도에서 확인하지 못했다.
따라서 `same_final_main_three_party_ack=NO`로 유지한다.

## 4. 최신 SHA 재검증 결과

| 검증 | 결과 | Exit |
| --- | --- | ---: |
| AI Guidance·Smoke·Local Runtime 표적 | `43 passed, 3 warnings` | 0 |
| G1-B Readiness Audit | `READY`, blocker 0 | 0 |
| PostgreSQL·pgvector | `16.14 / 0.8.6` | 0 |
| Evidence Migration | `0009`, `0010`, `0011` 적용 | 0 |
| Crosswalk·Page Link·Readonly View | `7/7`, `8/8`, 7행·고유 7 | 0 |
| AI Role 권한 | View SELECT만 허용, Base Table·DML·Schema CREATE 거부 | 0 |
| 실제 pgvector Query·Exact Search | `1 passed` | 0 |
| 실제 OpenAI Local Runtime Gate | 일반화된 Runtime 실패 | 1 |
| 시작·종료 HEAD | `004688132b623f5d2f8f24add558f6c3d5ce24d6` 동일 | 0 |

경고 3건은 Starlette TestClient 1건과 `jsonschema.RefResolver` 폐기 예정 API
2건이며 이번 실패 원인이 아니다.

## 5. 실제 Provider 실패 증거

이전 `ed4afa79c4f24393ec03740e4a2da10e0073288a` 실제 공동실행에서는 AI와
Backend Health 200을 확인한 뒤 신규 합성 Inquiry를 제출했다.

| 항목 | 확인값 |
| --- | --- |
| Inquiry | `2d095b44-4969-40ed-bd2f-e8707ea73feb` |
| Submit Correlation | `d292a085-312a-48b4-8e1c-6085ebd88cdb` |
| Submit·Replay | HTTP 200, 최초 Replay false, 재요청 Replay true |
| Correlation | 응답 Header·metadata·AIRun·History·Backend/AI 로그 일치 |
| AI 로그 | `analysis_started → analysis_failed` |
| 실패 Stage | `GENERATING` |
| AIRun | 1건, `FAILED / PASSED / AI-FAILED-01` |
| Assessment·Guidance·EvidenceLink | 모두 0건 |
| 고객 Guidance GET | 409 |
| Provider 분류 | `GuidanceGenerationExecutionError → LLMOutputValidationError` |
| Provider HTTP | 400 |

최신 SHA 재시도는 AI Provider Source 변경이 없는 상태에서 같은 Local Runtime
Gate가 다시 실패했다. 검증기는 예기치 않은 예외를 일반 메시지로 변환하므로 최신
호출의 Provider 세부 오류는 문서에 추측해 기록하지 않는다. 이전 HTTP 400 증거와
최신 일반 실패를 서로 다른 SHA의 사실로 분리한다.

공식 OpenAI 문서상 `gpt-4.1-mini`는 Responses API와 Structured Outputs를
지원한다. 현재 Runtime도 공식 Endpoint, `store=false`, 최상위 필드 required와
`additionalProperties=false` Schema를 사용하므로 모델 기능 미지원으로 실패를
확정하지 않는다. Provider 오류 본문의 안전한 `type/code/param` 보존이 필요하다.

- <https://developers.openai.com/api/docs/models/gpt-4.1-mini>
- <https://developers.openai.com/api/docs/guides/structured-outputs>

## 6. 실행하지 않은 항목과 이유

| 항목 | 상태 | 이유 |
| --- | --- | --- |
| 최신 SHA Backend·AI 공동 기동 | NOT_RUN | 단독 AI Gate 선행 실패 |
| 신규 Happy Path Inquiry | NOT_RUN | 실패 AIRun과 Key 추가 생성을 방지 |
| AIRun·Assessment·Guidance·Evidence 정상 저장 | NOT_RUN | AI 생성 성공 결과 없음 |
| 고객 Guidance GET 200 | NOT_RUN | 신뢰 가능한 Guidance 없음 |
| 동일 요청 Replay 중복 0건 | NOT_RUN | 최신 SHA 신규 Submit 미실행 |
| NO_EVIDENCE | NOT_RUN | Happy Path 결과 확인 후 실행 원칙 유지 |
| DANGER·TOTAL_STOP | NOT_RUN | Happy Path 결과 확인 후 실행 원칙 유지 |

NO_EVIDENCE·DANGER를 정상 Guidance 실패 상태에서 별도로 실행하면 Provider 결함과
결정적 Fallback 결과가 섞인다. 공동실행 준비 회신의 순서대로 정상 저장·Replay·
Correlation을 먼저 확인해야 한다.

## 7. 이동윤·최지용 요청사항

### 이동윤 — AI·RAG

1. `ai/app/**`에서 실제 Responses API HTTP 400 원인을 재현한다.
2. Raw Prompt·Evidence·Provider 응답 원문을 로그에 남기지 않으면서 안전한
   `type/code/param` 또는 내부 분류 코드를 보존한다.
3. `gpt-4.1-mini`, Structured Outputs, `store=false` 조건에서
   `verify_local_runtime`을 PASS한다.
4. `analysis_started → llm_guidance_completed → analysis_completed`, 실제 모델,
   Prompt Version과 Token 사용 증거를 Secret 제거 형식으로 회신한다.
5. 수정 Commit과 최종 40자리 SHA를 전달한다.

### 최지용 — Backend·Database

1. AI PASS SHA가 main에 반영된 뒤 Backend·AI·QA 동일 SHA를 ACK한다.
2. 기존 실패 Inquiry·Submit Key를 재사용하지 않는다.
3. 새 Inquiry에서 AIRun·Assessment·Guidance·EvidenceLink 저장과 고객 Guidance
   GET 200을 공동 실행한다.
4. Replay 추가 AI 호출 0회·중복 저장 0건과 Correlation 일치를 확인한다.

## 8. 재현 명령

저장소 Root에서 보호 Loader와 검증기를 같은 PowerShell Process에 둔다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '& {
  . .\scripts\deployment\import_team_integration_env.ps1 `
    -Role AI -RequireOpenAIKey | Out-Null

  & .\ai\.venv\Scripts\python.exe -B `
    -m ai.scripts.verify_local_runtime
}'
```

Secret·DSN·Provider 원문을 출력하거나 회신에 포함하지 않는다.

## 9. 완료·재개 조건

현재 완료된 범위는 `DB_READY`, `PGVECTOR_PASS`, `ACTUAL_OPENAI_FAIL`의 재현과
인계다. `G1-B PASS`는 아니다.

다음 조건이 모두 충족되면 김은진 독립 QA를 재개한다.

1. 이동윤의 실제 OpenAI Local Runtime Gate PASS
2. Backend·AI·QA 동일 최종 40자리 SHA ACK
3. AI·Backend Health 200
4. 신규 Inquiry 정상 Guidance 저장과 고객 GET 200
5. Replay·Correlation·내부 정보 비노출 PASS
6. 위 결과 확인 후 NO_EVIDENCE·DANGER 실행 결정

Backend·AI 8000·8001 Process는 구 Runtime 혼동 방지를 위해 종료했고 PostgreSQL,
Volume과 합성 재현 데이터는 보존했다.

## 10. SHA별 사전 Gate 증거

이 절은 병합 전 `Backend·AI G1-B 독립 QA 사전 Gate 결과`의 고유 증거를
보존한다. 아래 결과는 최신 SHA 결과와 합산하지 않는다.

### 10.1 `720573906c5cba166a7f8fb35c9ff17f359350ab`

| 검증 | 결과 | Exit |
| --- | --- | ---: |
| Fresh Worktree 시작·종료 HEAD | 동일, 변경 0건 | 0 |
| Backend 공식 환경 Gate | Python 3.13.13, fingerprint 일치 | 0 |
| Backend·AI `pip check` | Broken requirement 0건 | 0 |
| Backend G1-B 표적 회귀 | `95 passed` | 0 |
| AI 전체 Unit | `229 passed, 5 warnings, 7 subtests passed` | 0 |
| 계약 Validator 5종 | 모두 PASS | 0 |
| 계약 pytest | `38 passed` | 0 |
| G1-B Readiness | `READY`, blocker 0 | 0 |
| 실제 pgvector Query·Exact Search | `1 passed` | 0 |
| 실제 Local Runtime Gate | `GuidanceGenerationExecutionError → LLMOutputValidationError` | 1 |

실패 Metadata는 `retry_count=0`, `retryable=false`, `timed_out=false`였다. 따라서
당시 실패는 DB Readiness, 환경변수 누락 또는 Network Timeout으로 분류하지
않았다. Provider 응답·Prompt·Evidence 원문과 Secret은 출력하지 않았다.

### 10.2 `ed4afa79c4f24393ec03740e4a2da10e0073288a`

이 SHA의 실제 공동실행 증거는 5절에 통합했다. AI·Backend Health 200, 신규 합성
Inquiry 제출, Idempotency Replay, Correlation 연결과 저장 Count 불변까지
확인했지만 Provider HTTP 400으로 `GENERATING` 단계에서 종료됐다. 실행 후 해당
Runtime과 일치하는 8000·8001 Process만 종료했고 PostgreSQL과 Volume은 보존했다.

## 11. 최신 SHA Mobile Local Gate 보조 증거

`004688132b623f5d2f8f24add558f6c3d5ce24d6`에서 Android Studio JBR과
`emulator-5554`를 사용해 Customer connected AndroidTest를 실행했다.

```ini
qa_host_device=Pixel_8(AVD)
qa_host_serial=emulator-5554
qa_host_model=sdk_gphone16k_x86_64
mobile_local_connected_tests=11
mobile_local_connected_passed=7
mobile_remote_expected_skips=4
mobile_local_connected_failures=0
mobile_local_gate=PASS
customer_apk_sha256=05C3F7DD935F40E2CA4137FCC61F6889316A195F5B5F12D2C80DA177E6E6CB6
android_test_apk_sha256=D56DEF65197CB09F2AF81DB67B2FA7B972456B215D55F19746DA2DFD7B744CB0
```

Gradle 콘솔의 중간 진행 수치는 `Finished 15 tests`로 잘못 표시됐지만 생성된
JUnit XML 정식 집계는 `tests=11`, `skipped=4`, `failures=0`, `errors=0`이다.
Remote 4건은 `runRemoteSmoke=true`를 사용하지 않은 예상 Skip이며 실제 G1~G3
PASS가 아니다.
