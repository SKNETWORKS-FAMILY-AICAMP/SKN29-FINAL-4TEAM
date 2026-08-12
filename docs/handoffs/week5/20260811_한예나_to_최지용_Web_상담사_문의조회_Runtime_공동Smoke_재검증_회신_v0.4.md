# 한예나 → 최지용: Web 상담사 문의 조회 Runtime 공동 Smoke 재검증 회신 v0.4

## 1. 재검증 기준

| 항목 | 확인값 |
|---|---|
| 재검증일 | 2026-08-11 KST |
| Web Branch | `yena` |
| Web HEAD | `454339a` |
| 최신 `origin/main` | `92b0674` |
| `main` 반영 상태 | 현재 `yena`가 `origin/main`을 모두 포함, behind `0` |
| QA Seed Commit | `5a6f13d`가 `origin/main`과 현재 `yena`에 포함 |
| 우선 범위 | 상담사 문의 목록·상세 GET 2개 |

## 2. 이번에 수행한 작업

1. 최신 `origin/main`을 다시 Fetch하고 현재 `yena`의 포함 관계를 확인했다.
2. Git에서 제외되는 로컬 Web 환경을 아래 Remote 기준으로 유지했다.
   - `VITE_API_BASE_URL=/api/v1`
   - `VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8000`
   - `VITE_USE_MOCK_API=false`
3. 저장소의 `backend/.venv`가 삭제된 Python 3.13.13 경로를 참조해 실행되지 않아, 저장소 밖 임시 디렉터리에 Python 3.13.12와 고정 의존성 32개를 설치해 Backend 코드 검증을 재개했다.
4. Django System Check와 상담사 문의 조회 표적 테스트를 실행했다.
5. Web Remote 전용 테스트, 전체 회귀, Lint, TypeScript, Production Build를 다시 실행했다.
6. Mock Off 개발 서버에서 실제 API 로그인 경계와 Backend 단절 오류 처리를 브라우저로 확인했다.

저장소의 기존 `backend/.venv`는 삭제하거나 덮어쓰지 않았다. Token·비밀번호·DSN은 출력하거나 문서에 기록하지 않았다.

## 3. 자동 검증 결과

| 검증 | 결과 | 비고 |
|---|---|---|
| Django System Check | PASS | `0 silenced` |
| QA Seed·Runtime·Socket HTTP 표적 | PASS | 3 files, 11 tests passed |
| QA Seed Unit | PASS | 3 tests 포함 |
| 상담사 목록·상세 Runtime 계약 | PASS | 403·동일 404·422 경계 포함 |
| 실제 Socket HTTP — SQLite Test Runtime | PASS | 1 test 포함 |
| Web Remote 전용 Unit | PASS | 4 files, 23 tests passed |
| Web 전체 회귀 | PASS | 33 files, 142 tests passed |
| Web Lint | PASS | ESLint exit 0 |
| Web TypeScript | PASS | `tsc -b` exit 0 |
| Web Production Build | PASS | Mock Off, 142 modules transformed |
| Remote → Mock 자동 fallback | DISABLED | Remote Repository 실패 전파 및 브라우저 실패 상태 확인 |

전체 Web 회귀는 Mock fixture 자체를 검증하는 기존 테스트가 포함돼 있어 테스트 프로세스에서만 `VITE_USE_MOCK_API=true`를 주입했다. Remote 전용 23개 테스트와 Production Build는 `VITE_USE_MOCK_API=false` 상태에서 수행했다.

## 4. 실제 PostgreSQL 공동 Smoke 차단점

| 확인 | 결과 |
|---|---|
| Backend `127.0.0.1:8000` | 미실행, Port 8000 Closed |
| PostgreSQL Port 5432 | Closed |
| 로컬 PostgreSQL Service | 발견되지 않음 |
| Docker CLI | 설치되지 않음 |
| PostgreSQL 연결 검사 | `CONNECTION_FAILED / ConnectionTimeout` |
| PostgreSQL Seed Replay | 미실행 — 연결 선행 조건 미충족 |
| 실제 API 로그인·목록·상세 200 | 미실행 — Backend Runtime 미실행 |
| 실제 Correlation ID 로그 대조 | 미실행 — 신규 HTTP 성공·오류 응답 없음 |

Mock Off 브라우저에서 `/consultant/inquiries` 접근 시 실제 API 로그인 화면으로 이동했다. `API 데모 계정으로 로그인` 실행은 Backend 연결 실패 안내를 표시했고 Mock 계정이나 Mock 문의 목록으로 전환되지 않았다.

## 5. Backend·DB 담당자에게 요청하는 다음 조치

1. PostgreSQL `waterbridge.public` Runtime을 실행한다.
2. 현재 Migration 적용 상태를 확인하고 QA Seed를 Accounts → Consultant Inquiry 순서로 재적용한다.
3. Backend를 `127.0.0.1:8000`에서 실행하고 시작 완료 시점을 Web 담당자에게 전달한다.
4. Web과 같은 시간대에 로그인·목록·상세·403·동일 404·422 요청을 실행한다.
5. 이번 실행에서 새로 생성된 Correlation ID를 `backend/.runtime/logs/backend.jsonl`과 대조한다.

Backend Runtime 시작이 확인되면 Web에서는 별도 코드 변경 없이 Mock Off 서버를 재시작하고 실제 Network 요청과 화면 상태를 검증할 수 있다.

## 6. 공동 Smoke 회신 블록

```text
sender=한예나
receiver=최지용
scope=CONSULTANT_INQUIRY_READ_SHARED_SMOKE
main_pull=PASS
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
blocker=최신 main과 QA Seed 반영, Django Check, Backend 표적 11 tests, Web Remote 23 tests, Web 전체 142 tests, Lint·Build는 통과했다. 그러나 로컬 PostgreSQL 서비스와 Docker가 없고 5432 Port가 닫혀 PostgreSQL 연결이 ConnectionTimeout으로 실패했다. 따라서 Seed Replay와 Backend 8000 Runtime, 실제 로그인·목록·상세·403·404·422·Correlation 공동 Smoke를 실행할 수 없다.
```

## 7. 현재 판정

`BACKEND_CODE_GATE_PASS / WEB_REMOTE_GATE_PASS / POSTGRESQL_RUNTIME_BLOCKED / WEB_SHARED_SMOKE_WAITING`

PostgreSQL Runtime·Seed Replay·Backend 실행 후 실제 HTTP와 Correlation ID 대조가 완료되기 전에는 `CONSULTANT_INQUIRY_READ_REMOTE_SMOKE=PASS`로 종료하지 않는다.
