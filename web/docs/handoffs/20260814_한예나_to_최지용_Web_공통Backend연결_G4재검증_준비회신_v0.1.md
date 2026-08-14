# 한예나 → 최지용: Web 공통 Backend 연결 및 G4 재검증 준비 회신 v0.1

## 1. 문서 정보

| 항목 | 내용 |
|---|---|
| 작성일 | 2026-08-14 KST |
| 발신 | 한예나 — Web Frontend |
| 수신 | 최지용 — Backend·DB |
| 요청 문서 | `20260814_최지용_to_한예나_Web_공통Backend연결_G4재검증_작업요청_v0.1.md` |
| 판정 범위 | 최신 main 동기화, Mock OFF 준비, Web 회귀 Gate, Backend 인계 전 사전 Smoke |
| 현재 상태 | `WEB_LATEST_MAIN_READY / G4_WAIT_INQUIRY_HANDOFF` |

## 2. 결론

- `yena`를 최신 `origin/main@ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7`로 충돌 없이 fast-forward했습니다.
- 동기화된 4개 Commit에는 Web 파일 변경이 없었습니다.
- Mock OFF Remote 설정을 확인했습니다.
- 현재 main에서 Web Unit Test·Lint·TypeCheck·Production Build를 모두 통과했습니다.
- 실제 Browser에서 Backend 실패가 Mock/Fake 성공으로 전환되지 않고 오류 UI로 표시되는 것을 확인했습니다.
- 공통 PostgreSQL Backend 및 신규 Inquiry 인계값이 없어 실제 로그인·목록·상세·G4 Action은 아직 실행하지 않았습니다.
- 기존 SQLite·과거 Runtime 결과를 현재 G4 PASS로 사용하지 않았습니다.
- 현재 판정은 `WEB_LATEST_MAIN_READY`, `G4_WAIT_INQUIRY_HANDOFF`, `FULL_E2E_NOT_CLAIMED`입니다.

## 3. 최신 기준선 동기화

| 항목 | 결과 |
|---|---|
| 작업 전 `yena` | `9a855f264b0978ec36ae145af58a449b3640d2b1` |
| 최신 `origin/main` | `ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7` |
| 관계 | 작업 전 `yena`가 `origin/main`보다 4 Commit 뒤인 직접 조상 |
| 동기화 방식 | `git fetch origin --prune` 후 `git merge --ff-only origin/main` |
| 충돌 | 없음 |
| 실행 기준 `main_sha` | `ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7` |
| 실행 기준 `web_sha` | `ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7` |
| 작업 트리 | 회신 문서 외 제품 소스 변경 없음 |

## 4. Mock OFF Remote 설정

현재 로컬 Web 설정을 확인했습니다.

```ini
VITE_USE_MOCK_API=false
VITE_API_BASE_URL=/api/v1
VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8000
```

- `127.0.0.1:8000`은 같은 PC에서 Backend를 실행할 때 사용하는 로컬 기본값입니다.
- 최지용이 LAN 또는 공통 Backend URL을 전달하면 실행 직전에 해당 값으로 교체해야 합니다.
- Web은 PostgreSQL `5432`에 직접 연결하지 않습니다.
- Remote 실패 시 Mock/Fake 데이터로 성공 처리하지 않습니다.

## 5. Web 회귀 Gate 결과

### 5.1 최종 순차 실행 결과

| Gate | 명령 | 결과 |
|---|---|---:|
| Unit Test | `npm.cmd test -- --maxWorkers=1` | PASS — 34 files, 155 tests |
| Lint | `npm.cmd run lint` | PASS |
| TypeCheck | `npm.cmd run typecheck` | PASS |
| Production Build | `npm.cmd run build` | PASS — 143 modules transformed |

### 5.2 최초 병렬 실행 참고

최초에는 Test·Lint·TypeCheck·Build를 동시에 실행했습니다. 이때 Vitest가 `ConsultantDashboardPage.test.tsx`의 Worker 시작을 기다리다 Timeout되어 다음 결과로 종료됐습니다.

```text
33 files passed
136 tests passed
1 unhandled worker startup error
error=Timeout waiting for worker to respond
```

제품 Assertion 실패는 없었습니다. 원인 분리를 위해 다음과 같이 재실행했습니다.

1. `ConsultantDashboardPage.test.tsx` 단독 실행: 1 file / 19 tests PASS
2. 전체 Test 순차 실행: 34 files / 155 tests PASS
3. Lint·TypeCheck·Build 순차 실행: 모두 PASS

따라서 최종 Unit Test Gate는 PASS이며, 최초 오류는 병렬 실행 자원 경합으로 기록합니다.

## 6. Browser 사전 Smoke

### 확인된 항목

- 최신 main의 상담사 문의 화면 진입
- 문의 검색 입력 표시
- 새 문의·처리 중·처리 완료·전화 문의 등록 Tab 표시
- 전체 업무·상담 연결·장기 대기·AI 검수 Filter 표시
- Backend 미기동 상태에서 목록 오류 UI 표시
- 가짜 문의 0건, Mock/Fake 성공 Fallback 없음

표시된 오류:

```text
상담 문의 목록을 불러오지 못했습니다.
잠시 후 다시 시도해 주세요.
```

### 실행하지 못한 항목

- 실제 Backend 상담사 로그인
- PostgreSQL 문의 목록·검색·Filter·Pagination 응답 확인
- 실제 Inquiry 상세 확인
- 실제 401·403·404·409 응답 UI 확인
- 새로고침 후 실제 서버 Snapshot 재조회
- START→기록 저장→요약 확정→완료
- 다른 상담사 목록 제외·상세 및 Action 404

사유는 Backend Runtime·Base URL·환경 ID·신규 Inquiry가 아직 인계되지 않았기 때문입니다. 따라서 사전 Smoke 결과는 `PARTIAL`이며 G4는 `WAIT_HANDOFF`입니다.

## 7. Blocker 전달 양식

```ini
phase=PRE_SMOKE
main_sha=ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7
web_sha=ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7
backend_runtime_sha=PENDING_HANDOFF
environment_id=PENDING_HANDOFF
backend_base_url=PENDING_HANDOFF(local_placeholder=http://127.0.0.1:8000)
method_path=GET /api/v1/inquiries
http_status=N/A_CONNECTION_REFUSED
inquiry_id=PENDING_HANDOFF
state_version=PENDING_HANDOFF
allowed_actions=PENDING_HANDOFF
correlation_id=N/A_REQUEST_NOT_REACHED_BACKEND
expected=공통 PostgreSQL Backend에서 상담사 문의 목록 응답
actual=Backend Listener가 없어 Web 목록 요청 실패, 오류 UI 표시, Mock/Fake Fallback 없음
reproduction=VITE_USE_MOCK_API=false 상태에서 Web 실행 후 /consultant/inquiries 진입
blocker_owner=최지용
result=BLOCKED
```

이 Blocker는 Web 제품 코드 결함 판정이 아니라 Backend 인계 전 대기 상태입니다.

## 8. 현재 알고 있는 Backend Projection 제한

요청 문서에서 현재 main의 제한으로 아래 내용을 전달받았습니다.

```text
consultation=null
restricted_functions=[]
```

Web은 이 값을 가짜 데이터로 채우지 않습니다. 실제 PostgreSQL G4에서 다음 현상이 발생하면 Backend Projection Blocker로 별도 전달하겠습니다.

- 상담 기록 저장 성공 후 상세 재조회에서 `consultation=null`이어서 기록 복구 불가
- 실제 AI 제한 기능이 존재하지만 `restricted_functions=[]`로 반환되어 화면 표시 불가

현재 Backend가 실행되지 않아 위 Projection 제한을 최신 Runtime에서 직접 재현하지는 못했습니다.

## 9. G4 시작을 위해 필요한 Backend 인계값

```ini
backend_runtime_sha=
environment_id=
backend_base_url=
db_backend=POSTGRESQL
migration_status=
demo_consultant_001_usage=
inquiry_id=
inquiry_code=
status=
state_version=
allowed_actions=
request_consultation_correlation_id=
assigned_consultant=DEMO-CONSULTANT-001
consultation_status=WAITING
consultation_consultant=null
known_blocker=
```

Secret·Token·Authorization 원문·고객 개인정보는 전달하지 않아도 됩니다.

## 10. 최종 회신 양식

```ini
sender=한예나
receiver=최지용
main_sha=ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7
web_sha=ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7
sync_result=PASS
remote_mode=true
mock_fallback=DISABLED
unit_test=PASS(34_FILES_155_TESTS)
lint=PASS
typecheck=PASS
build=PASS
pre_smoke=PARTIAL
g4_same_inquiry=WAIT_HANDOFF
same_inquiry_id=PENDING_HANDOFF
final_status=N/A
final_state_version=N/A
correlation_ids=N/A
blocker=BACKEND_RUNTIME_BASE_URL_ENVIRONMENT_AND_NEW_INQUIRY_NOT_HANDED_OFF
needed_from_backend=backend_runtime_sha,environment_id,backend_base_url,POSTGRESQL migration status,DEMO-CONSULTANT-001 procedure,inquiry_id,inquiry_code,status,state_version,allowed_actions,REQUEST_CONSULTATION correlation_id,assignment and consultation snapshot,known_blocker
completion_code=WEB_LATEST_MAIN_READY
e2e_claim=FULL_E2E_NOT_CLAIMED
```

## 11. 변경 범위 확인

- 수정한 Web 제품 소스: 없음
- 수정한 Web 설정: 없음
- 생성한 파일: 이 Web 전용 회신 문서 1개
- Backend·Mobile·AI·DB·Migration·공용 계약 수정: 없음
- 기존 SQLite·과거 Runtime 결과를 최신 G4 PASS로 승격하지 않음
