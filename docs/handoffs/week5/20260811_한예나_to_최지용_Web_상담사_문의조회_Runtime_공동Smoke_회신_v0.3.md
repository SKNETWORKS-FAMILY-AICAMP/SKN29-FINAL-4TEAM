# 한예나 → 최지용: Web 상담사 문의 조회 Runtime 공동 Smoke 회신 v0.3

## 1. 판정

- 원격 `main`의 최신 기준선은 `92b0674`이며 QA Seed 커밋 `5a6f13d`가 포함된 것을 확인했다.
- 현재 `yena` 작업선은 `origin/main`보다 24커밋 뒤이고 미커밋 Web 작업이 있어, 작업 손실 방지를 위해 이번 점검에서 Pull·Merge는 수행하지 않았다.
- Web 로컬 실행은 `VITE_USE_MOCK_API=false`로 전환했다.
- Backend `127.0.0.1:8000`이 실행 중이지 않고 저장소 가상환경이 존재하지 않는 Python 3.13 경로를 참조해 실제 HTTP 공동 Smoke는 차단됐다.
- 최종 판정은 `WEB_SHARED_SMOKE_WAITING / shared_smoke=BLOCKED`다.

## 2. Web 준비 및 검증 결과

| 항목 | 결과 | 근거 |
|---|---|---|
| QA Seed `main` 반영 | PASS | `origin/main`에 `5a6f13d` 포함 |
| Remote 로컬 설정 | PASS | Git 제외된 `web/.env.local`에 `/api/v1`, `127.0.0.1:8000`, Mock Off 적용 |
| Remote 전용 Unit | PASS | 4 files, 23 tests passed |
| Web 전체 회귀 | PASS | 테스트 프로세스에서만 Mock fixture 활성화, 33 files, 142 tests passed |
| Web Lint | PASS | ESLint exit 0 |
| Web TypeScript | PASS | `tsc -b` exit 0 |
| Web Production Build | PASS | Mock Off 설정, 142 modules transformed |
| Remote → Mock 자동 fallback | DISABLED | Remote Repository 실패를 그대로 throw하는 Unit 통과 |
| 브라우저 Remote 경계 | PASS | 실제 API 로그인 화면 표시, Backend 단절 시 실패 안내, Mock 세션 미생성 |

전체 회귀는 Mock 시나리오를 검증하는 기존 테스트가 포함되어 있으므로 테스트 프로세스에서만 `VITE_USE_MOCK_API=true`를 주입했다. Remote 전용 23개 테스트와 프로덕션 빌드는 `VITE_USE_MOCK_API=false` 상태에서 검증했다.

## 3. 공동 Smoke 미실행 항목

다음 항목은 Backend Runtime과 PostgreSQL Seed Replay가 준비된 뒤 실제 신규 요청으로 검증해야 한다.

- 상담사 로그인 `200`, 역할 `CONSULTANT`
- 문의 목록 `200`과 Scenario `DEMO-CONSULTANT-READ-001` 포함 여부
- 문의 상세 `200`과 공개 UUID `4f829120-ecbb-5b30-9365-bf02f9044c3b` 일치 여부
- 다른 역할 `403`
- 미존재·타 상담사 문의의 동일 `404 RESOURCE_NOT_FOUND`
- 허용하지 않은 Query의 `422 VALIDATION_ERROR`
- 응답의 계약 밖 주소·이메일·내부 ID 비노출
- 성공·오류 응답과 `backend/.runtime/logs/backend.jsonl`의 Correlation ID 일치

Correlation ID는 공동 Smoke에서 브라우저 DevTools Network의 요청·응답과 Backend JSON 로그를 대조한다.

## 4. 담당자 협의사항

### 최지용 — Backend·DB

1. 정상 Python 3.13 가상환경에서 PostgreSQL Seed를 재적용한다.
2. `127.0.0.1:8000` Backend Runtime을 실행하고 Web 측에 시작 완료를 알린다.
3. 공동 Smoke 중 생성된 신규 Correlation ID를 `backend/.runtime/logs/backend.jsonl`에서 함께 대조한다.

### 한예나 — Web

1. 현재 미커밋 작업을 안전하게 보존한 뒤 최신 `origin/main` 24커밋을 통합한다.
2. Backend 시작 확인 후 Mock Off 개발 서버를 재시작한다.
3. 목록·상세 Network 호출과 200·403·404·422 및 Retry 화면을 검증한다.
4. 결과를 같은 문서에 갱신하고 최종 `CONSULTANT_INQUIRY_READ_REMOTE_SMOKE=PASS` 여부를 양측과 맞춘다.

## 5. 요청 형식 회신

```text
sender=한예나
receiver=최지용
scope=CONSULTANT_INQUIRY_READ_SHARED_SMOKE
main_pull=WAITING
vite_use_mock_api=false
vite_api_base_url=/api/v1
vite_backend_proxy_target=http://127.0.0.1:8000
web_test=PASS
web_lint=PASS
web_build=PASS
login_200=NOT_TESTED
list_200=NOT_TESTED
detail_200=NOT_TESTED
role_403=NOT_TESTED
same_404=NOT_TESTED
query_422=NOT_TESTED
correlation_observation=DEVTOOLS
correlation_match=NOT_TESTED
remote_mock_fallback=DISABLED
shared_smoke=BLOCKED
blocker=origin/main의 QA Seed 병합은 확인했으나 현재 yena 작업선이 24커밋 뒤이고 미커밋 작업이 있어 Pull 대기 중이다. 또한 127.0.0.1:8000 Backend가 실행 중이지 않고 backend/.venv가 존재하지 않는 Python 3.13 경로를 참조해 실제 HTTP 공동 Smoke를 시작할 수 없다.
```
