# 이동윤 → 최지용 Backend·AI P0-2 공동 Mock 착수 회신 v0.1

> 작성일: 2026-08-10 KST
> 발신자: 이동윤 / AI·RAG
> 수신자: 최지용 / Backend·Database

## 1. 착수 상태

```text
sender=이동윤
receiver=최지용
scope=BACKEND_AI_P0_2_JOINT_MOCK_START

integration_baseline=4d955116c00f715e1ba9e465104a381b858996b9
integration_baseline_type=SINGLE_MERGE_COMMIT
ai_working_tree_at_validation=CLEAN
python_version=3.13.13
pip_check=PASS
ai_unit_tests=127 passed, 0 failed, 0 skipped, 3 warnings
backend_fixture_tests=12 passed, 1 warning

ai_contract_version=3.0.0
contract_parity=PASS
mock_fixture_parity=PASS
uvicorn_mock_health=PASS
uvicorn_mock_analyze=HTTP 200 PASS
correlation_trace=PASS

mock_server_status=READY
mock_fixture_status=FROZEN
ready_for_joint_mock=CONDITIONAL_YES
joint_mock_available_time=후보 Commit 전달 즉시 가능

start_condition=Initial Symptom Wiring candidate_commit 및 Backend 재현 명령 전달
current_blocker=origin/jiyong에서 Initial Symptom Wiring 후보 미확인
joint_mock_excluded=팀 DB Migration, 최소 권한 DSN, Chunk Crosswalk, Local RAG
```

## 2. Backend 후보 검토 기준

1. 신규 `SUBMIT_SYMPTOM` 저장 Commit 이후 AI 호출을 정확히 1회 등록한다.
2. HTTP 호출은 DB Transaction과 Row Lock 밖에서 실행한다.
3. 동일 Idempotency-Key Replay에는 AI 호출을 추가 등록하지 않는다.
4. AI Timeout·4xx·5xx·Schema 오류가 이미 Commit된 증상과 State 전이를
   Rollback하지 않는다.
5. `correlation_id`, `ai_request_id`, `state_version`을 요청·응답·`AIRun`에
   보존한다.
6. Backend 자동 재시도는 0회다.

## 3. 공동 Mock 검증 범위

```text
SUBMIT_SYMPTOM 신규 요청
→ 증상·State Commit
→ Initial AI Dispatch 1회
→ POST /api/v1/ai/analyze?mode=mock
→ 계약 3.0.0 응답 검증
→ AIRun·구조화 결과 저장
→ Correlation 추적
```

판정값은 다음 형식으로 남긴다.

```text
backend_candidate_commit=
backend_author_tests=PASS|FAIL
initial_ai_dispatch_count=
idempotency_replay_additional_dispatch_count=
request_schema=PASS|FAIL
response_schema=PASS|FAIL
correlation_id_parity=PASS|FAIL
airun_saved=PASS|FAIL
timeout_boundary=PASS|FAIL
error_boundary=PASS|FAIL
joint_mock_result=PASS|FAIL
```

팀 DB와 Crosswalk는 이번 P0-2 Mock 판정에 포함하지 않는다.
