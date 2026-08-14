# 한예나 → 최지용: Web·Backend 연결 테스트 상세 회신 v0.2

> 작성일: 2026-08-13 KST  
> 발신: 한예나 / Web Frontend  
> 수신: 최지용 / Backend·Database  
> 현재 Web·Main SHA: `6ae659f12c02c4abc72cb6b2645e1669c76d571d`  
> 실제 E2E 실행 내용 보존 SHA: `1cd190559dcc6271799620ef6eea50de6a733388`

## 1. 요약 판정

| 구분 | 결과 |
|---|---:|
| 현재 SHA Web 자동 테스트 | PASS |
| 현재 SHA Web lint·typecheck·build | PASS |
| Web↔Backend 상담 Action 경로 정적 대조 | PASS |
| Backend 미기동 시 Browser Fail-closed | PASS — 오류 표시, Mock/Fake 전환 없음 |
| 과거 격리 Runtime 실제 Remote 상담 흐름 | PASS |
| 현재 SHA Backend 기동 | FAIL — 실행환경 차단 |
| 현재 SHA 실제 Remote 공동 Smoke | NOT RUN |
| 팀 PostgreSQL 공동 Smoke | NOT RUN |

Web 코드에서 발견된 실패 테스트는 없습니다. 현재 실패는 Backend 서버를 실행하는 환경 단계에서 발생했습니다. 또한 최신 Backend 코드를 정적으로 대조한 결과, Web 새로고침 지속성과 AI 제한 기능 표시에 영향을 주는 Projection 차이가 확인됐습니다.

## 2. 현재 SHA에서 통과한 테스트

### Web 전체 검증

| 명령 | 결과 | 상세 |
|---|---:|---|
| `npm.cmd test -- --maxWorkers=1` | PASS | 34 files, 155 tests |
| `npm.cmd run lint` | PASS | ESLint 오류 0 |
| `npm.cmd run typecheck` | PASS | TypeScript 오류 0 |
| `npm.cmd run build` | PASS | Vite production build 성공 |

Remote 상담 관련 테스트에서 확인한 내용:

- 상담 시작 → 저장 → 확정 → 완료 시 서버의 최신 `state_version`을 이어서 사용
- 저장 요청에 공개 DTO 필드만 전송
- 네트워크 재시도 시 같은 Idempotency Key 사용
- 각 재시도에 새 Correlation ID 사용
- 409 응답을 성공으로 오인하지 않고 최신 Snapshot 반영
- 409 재조회 중 작성 중인 입력 보존
- 처리 중 중복 클릭 차단
- 브라우저 재진입 시 서버 상담 기록으로 Form 복구
- 저장되지 않는 로컬 전용 상담 결과 Textarea 제거
- Public Evidence 미제공 시 안전 Fallback 사용

## 3. Web↔Backend API 경로 대조

현재 Web Repository, OpenAPI, Backend URL 정의의 Method·Path가 일치합니다.

| 기능 | Method·Path | 정적 대조 |
|---|---|---:|
| 상담 시작 | `POST /api/v1/inquiries/{id}/start-consultation` | PASS |
| 상담 기록 저장 | `PATCH /api/v1/inquiries/{id}/consultation-summary` | PASS |
| 상담 요약 확정 | `POST /api/v1/inquiries/{id}/consultation-summary/confirm` | PASS |
| 상담 완료 | `POST /api/v1/inquiries/{id}/complete-consultation` | PASS |

Web 실행 설정도 실제 Backend Remote 기준입니다.

```ini
VITE_API_BASE_URL=/api/v1
VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8000
VITE_USE_MOCK_API=false
```

## 4. 실제 Remote에서 이미 통과한 증거

격리 SQLite Runtime과 실제 Browser에서 동일 Inquiry를 처리했습니다.

```text
inquiry_id=96d76459-cffe-43f9-b927-67a8aedf1fc7
inquiry_code=INQ-254C17960A8943BB855DE6E8FB0F883B
before=CONSULTATION_REQUIRED,v4
after=COMPLETION_PENDING,v8
```

| 시각(KST) | 요청 | HTTP | Correlation ID |
|---|---|---:|---|
| 14:53:10 | 상담 시작 | 200 | `5a9085e0-3246-41fc-a73f-7b869c461170` |
| 14:53:25 | 상담 기록 저장 | 200 | `039415b0-06be-4405-a8e5-855a58416861` |
| 14:53:39 | 상담 요약 확정 | 200 | `6fdc622f-db7e-43cf-acb0-04e6f6e88e87` |
| 14:55:26 | 상담 완료 | 200 | `8a11fe96-3c90-411d-83c0-6f4e6766295b` |
| 14:55:26 | 상담사 상세 재조회 | 200 | `d3c7e3ee-008b-4713-8f18-584726bcd0b1` |
| 15:00:06 | 고객 최종 상태 재조회 | 200 | `5e36e34b-e742-4a0d-b306-896cd2ac8c50` |

주의: 위 실제 Remote 증거는 실행 내용이 `1cd1905`로 보존된 시점의 결과입니다. 현재 `6ae659f`는 이후 Backend·AI·Mobile·계약 변경을 포함하므로 최신 Runtime 재검증이 필요합니다.

## 5. 오늘 실패한 항목

### 5.1 Backend 가상환경 실행 실패

```text
command=backend/.venv/Scripts/python.exe --version
result=FAIL
exit_code=101
error=가상환경이 참조하는 Python 3.13 Base Interpreter 경로가 존재하지 않아 프로세스를 만들 수 없음
```

`backend/.venv/pyvenv.cfg`의 참조값:

```text
home=C:\Users\Playdata\AppData\Local\Programs\Python\Python313
version=3.13.13
```

### 5.2 대체 Python으로 Backend Check 실패

기존 Site Packages를 다른 Python Runtime에 연결해 `manage.py check`를 시도했지만 실패했습니다.

```text
result=FAIL
error=no pq wrapper available
details=psycopg_c 없음, psycopg_binary 호환 실패, libpq 없음, psycopg2 없음
```

Binary 패키지 호환 문제이므로 Web 담당 범위에서 임의로 Backend 환경을 수정하지 않았습니다.

### 5.3 Backend 연결 실패

```text
target=http://127.0.0.1:8000
listener=NONE
result=FAIL
error=원격 서버에 연결할 수 없음
```

이는 API 응답 실패가 아니라 서버가 기동되지 않은 환경 실패입니다.

### 5.4 Browser Fail-closed 확인

현재 SHA의 Web을 실제 Browser로 실행한 결과, 기존 상담사 Session으로 문의 화면까지 진입했지만 실제 목록 요청이 실패해 다음 오류가 표시됐습니다.

```text
상담 문의 목록을 불러오지 못했습니다.
잠시 후 다시 시도해 주세요.
```

목록 수는 0건으로 표시됐고 가짜 문의나 Mock 성공 데이터는 생성되지 않았습니다. 따라서 `VITE_USE_MOCK_API=false`와 Remote 실패 Fail-closed 동작은 실제 화면에서도 PASS입니다.

## 6. 현재 최신 Backend와 Web 사이에서 확인된 차이

### 6.1 상담 기록 재조회 Projection

현재 `ConsultantInquiryService.get_detail()`은 상담 기록이 저장돼 있어도 아래 값을 고정 반환합니다.

```text
consultation=null
```

Web은 새로고침·재진입 시 `consultation` DTO로 상담 기록을 복구합니다. 따라서 현재 Backend 응답 그대로라면 Action 요청은 성공해도 새로고침 후 저장 기록을 화면에서 복구할 수 없습니다.

요청 사항:

- 해당 Inquiry의 실제 ConsultationRecord를 상세 DTO에 Projection
- `consultation_id`, `summary`, `consultation_note`, `additional_check`, `customer_guidance`, `usage_guidance_status`, `result_code` 반환
- 상담 미생성 상태에서만 `null` 반환

### 6.2 제한 기능 Projection

현재 Backend 상세는 다음 값을 고정 반환합니다.

```text
restricted_functions=[]
```

Web은 실제 AI Guidance의 제한 기능을 표시할 준비가 되어 있습니다. 위험 문의에서도 빈 배열만 반환하면 실제 AI 안내가 화면에서 누락됩니다.

요청 사항:

- 최신 유효 Guidance의 `restricted_functions` Projection 여부 확정
- 미제공이 계약 의도라면 Web 표시 요구사항을 PM과 재합의

### 6.3 고객 실제 Guidance Route

현재 Backend URL·OpenAPI에서 다음 고객 소유 범위 Route를 찾을 수 없습니다.

```text
GET /api/v1/me/inquiries/{inquiry_id}/guidance
```

Mobile Remote Repository도 현재 `GUIDANCE_ROUTE_UNAVAILABLE`로 fail-closed합니다. PM P0의 첫 단계인 “Mobile 실제 AI 안내”를 최신 SHA에서 수행하려면 Route와 DTO 결정이 필요합니다.

이 항목은 Web Action 4개와 직접 충돌하지 않지만, 동일 Inquiry Cross-client P0를 시작하는 선행 Gate입니다.

## 7. 현재 실행하지 못한 테스트

| 테스트 | 상태 | 필요한 선행조건 |
|---|---:|---|
| 최신 SHA 상담사 로그인 | NOT RUN | 실행 가능한 Backend Base URL |
| 최신 SHA 목록·검색·필터·Pagination | NOT RUN | Backend 기동·상담사 Seed |
| 최신 SHA 동일 Inquiry 상세 | NOT RUN | Mobile/Backend 합성 Inquiry Seed |
| 최신 SHA 시작→저장→확정→완료 | NOT RUN | 실제 Backend·DB |
| 최신 SHA 새로고침 기록 지속성 | NOT RUN | 실제 Consultation Projection |
| 다른 상담사 상세·Action 404 | NOT RUN | 두 상담사 계정·동일 Seed |
| 409 최신 Snapshot 복구 | NOT RUN | 상태 충돌을 만들 수 있는 Runtime |
| PostgreSQL 원자 Claim·row-lock | NOT RUN | 팀 PostgreSQL 환경 |
| Mobile 실제 Guidance→상담 요청 | NOT RUN | 고객 Guidance Route·Mobile Runtime |
| 물리 Android 최종 상태 확인 | NOT RUN | 물리기기·Backend 접근 주소 |

## 8. Backend 담당자에게 필요한 인계 정보

최신 공동 Smoke를 시작할 수 있도록 아래 정보를 부탁드립니다. Secret은 문서에 적지 않고 별도 안전 채널로 공유해 주세요.

```ini
backend_runtime_sha=
backend_base_url=
database=POSTGRESQL|SQLITE
migration_status=
seed_command_or_fixture=
consultant_login_code=DEMO-CONSULTANT-001
second_consultant_login_code=
inquiry_id=
inquiry_code=
initial_status=CONSULTATION_REQUIRED
initial_state_version=
initial_allowed_actions=START_CONSULTATION
customer_guidance_route=AVAILABLE|UNAVAILABLE
consultation_projection=IMPLEMENTED|NULL_ONLY
restricted_functions_projection=IMPLEMENTED|EMPTY_ONLY
backend_log_location_or_check_method=
```

## 9. 공동 Smoke 재실행 순서

1. 실행 직전 Backend·Web SHA를 기록합니다.
2. `DEMO-CONSULTANT-001`로 실제 로그인합니다.
3. 전달받은 동일 `inquiry_id`를 목록과 상세에서 확인합니다.
4. 고객 원문·추가 답변·AI Guidance·제한 기능을 확인합니다.
5. 서버 `state_version`, `allowed_actions`만 사용해 시작→저장→확정→완료를 실행합니다.
6. 각 요청의 Idempotency Key와 Correlation ID를 기록합니다.
7. 새로고침 후 상담 기록과 `COMPLETION_PENDING` 상태를 확인합니다.
8. 다른 상담사로 상세·Action 404를 확인합니다.
9. PostgreSQL DB 상태·이력과 화면 결과를 대조합니다.
10. Mobile에서 동일 문의의 최종 상태를 확인합니다.

## 10. 요청 및 Blocker 회신

```ini
sender=한예나
receiver=최지용
scope=WEB_BACKEND_LATEST_SHA_CONNECTION
web_sha=6ae659f12c02c4abc72cb6b2645e1669c76d571d
backend_runtime_sha=UNKNOWN
web_tests=PASS_34_FILES_155_TESTS
lint=PASS
typecheck=PASS
build=PASS
api_path_static_match=PASS
browser_remote_failure_fail_closed=PASS
historical_remote_smoke=PASS_AT_1cd1905
current_backend_boot=FAIL
current_remote_smoke=NOT_RUN
postgresql_smoke=NOT_RUN
blocker=BROKEN_BACKEND_VENV,NO_BACKEND_LISTENER,CUSTOMER_GUIDANCE_ROUTE_MISSING,CONSULTATION_NULL_PROJECTION,RESTRICTED_FUNCTIONS_EMPTY_PROJECTION
request=EXECUTABLE_BACKEND_ENV,FINAL_SHA,BASE_URL,POSTGRES_SEED,SECOND_CONSULTANT,PROJECTION_DECISION
```
