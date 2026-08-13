# 한예나 → 최지용: Web G4 동일 Inquiry 사전 Smoke 및 공동검증 회신 v0.1

## 1. 회신 요약

요청한 Web 상담 사전 Smoke와 Mobile에서 생성·상담 요청한 동일 Inquiry의 G4 Web 처리를 완료했습니다.

- Web 사전 Smoke: `WEB_PRE_SMOKE_PASS`
- 동일 Inquiry G4 Web 처리: `G4_WEB_PASS`
- 전체 Cross-client 결과: 동일 Inquiry의 Mobile 최종 재조회까지 별도 실행 결과에서 확인됨
- Web Remote 모드: 활성화
- Mock/Fake 자동 전환: 비활성화
- Public Evidence: 가짜 데이터를 만들지 않고 `공개 근거 미제공 / 상담 검토 필요` 안전 문구 사용
- 이번 회신을 위해 Backend·AI·Mobile 소스는 수정하지 않음

## 2. 검증 기준

| 항목 | 값 |
|---|---|
| 요청 문서 | `20260813_최지용_to_한예나_Web_G4_동일Inquiry_사전Smoke_및_공동검증_요청_v0.1.md` |
| 실제 G4 실행 코드 보존 SHA | `1cd190559dcc6271799620ef6eea50de6a733388` |
| 실제 G4 실행 시작 Base SHA | `2d8cff888b971af6cab27968eded9d25f7a20a74` |
| 현재 Web 통합 SHA | `6e786e4edafa90ca882260630119b9e613170d95` |
| 현재 `origin/main` | `e65de8876cd762afdc7da4ca3696e0a865ff6973` |
| Web 환경 | `VITE_USE_MOCK_API=false`, `/api/v1` → `http://127.0.0.1:8000` |
| 상담사 | `DEMO-CONSULTANT-001` |
| 실행 DB | 격리 SQLite E2E DB |
| 실행 Client | Android Emulator + Django Backend + FastAPI AI + Web Browser |

실제 G4는 작업 중 변경을 포함한 통합 워크트리에서 수행한 뒤 `1cd1905` 커밋으로 보존했습니다. 현재 `6e786e4`는 해당 커밋에 최신 `main`을 병합한 SHA입니다.

## 3. 동일 Inquiry 식별값

| 항목 | 값 |
|---|---|
| `inquiry_id` | `96d76459-cffe-43f9-b927-67a8aedf1fc7` |
| `inquiry_code` | `INQ-254C17960A8943BB855DE6E8FB0F883B` |
| 고객 | `SYN-CUSTOMER-001` |
| 제품 | ACTIVE `WPUJAC104DWH` |
| AI 위험도 | `danger` |
| AI Guidance | `TOTAL_STOP` |
| 상담 필요 | `true` |
| 공개 근거 | 0건, 가짜 근거 미생성 |
| Web 처리 전 | `CONSULTATION_REQUIRED`, v4 |
| Web 처리 후 | `COMPLETION_PENDING`, v8 |

`COMPLETION_PENDING`은 현재 계약에서 상담 완료 직후의 정상 상태입니다. `RESOLVED` 전이는 이번 G4 Web Runtime 범위가 아닙니다.

## 4. 사전 Smoke 결과

| 검증 항목 | 결과 | 확인 내용 |
|---|---:|---|
| 실제 Backend Remote | PASS | Web Proxy가 실제 `/api/v1` Backend를 사용 |
| Mock/Fake 자동 전환 | PASS | `VITE_USE_MOCK_API=false`; Remote 실패를 Mock 성공으로 바꾸지 않음 |
| 상담사 인증 | PASS | 만료된 인증 요청은 401 후 Refresh 200, 이후 실제 목록 200 |
| 목록·검색·상세 | PASS | 동일 Inquiry가 상담사 목록과 상세에 표시됨 |
| Filter·Pagination Query | PASS | Remote Repository 및 전체 Web 테스트에서 Query 전달 검증 |
| 고객 원문·추가 답변 | PASS | 실제 상세 DTO를 화면에 표시 |
| 현재 AI Guidance | PASS | `TOTAL_STOP`, `danger`, 제한 기능을 실제 상세 DTO에서 표시 |
| Public Evidence Fallback | PASS | Runtime 미제공 시 안전 문구만 표시 |
| `state_version`·`allowed_actions` | PASS | 각 Action 뒤 서버가 반환한 최신 Snapshot으로 다음 요청 수행 |
| 상담 시작 | PASS | v4 → v5 |
| 상담 기록 저장 | PASS | v5 → v6 |
| 상담 요약 확정 | PASS | v6 → v7 |
| 상담 완료 | PASS | v7 → `COMPLETION_PENDING` v8 |
| 새로고침 지속성 | PASS | 완료 후 상세 재조회 200, 서버 상담 기록과 v8 복구 |
| 비담당 상담사 경계 | PASS | 원자 Claim 후 다른 상담사 목록 제외 및 상세·Action 404 Runtime 회귀 검증 |

## 5. 실제 Remote 요청 및 Backend 로그 대조

| 시각(KST) | Method·Path | HTTP | 상태 전이 | `correlation_id` |
|---|---|---:|---|---|
| 14:53:10 | `POST /api/v1/inquiries/{id}/start-consultation` | 200 | v4 → v5 | `5a9085e0-3246-41fc-a73f-7b869c461170` |
| 14:53:25 | `PATCH /api/v1/inquiries/{id}/consultation-summary` | 200 | v5 → v6 | `039415b0-06be-4405-a8e5-855a58416861` |
| 14:53:39 | `POST /api/v1/inquiries/{id}/consultation-summary/confirm` | 200 | v6 → v7 | `6fdc622f-db7e-43cf-acb0-04e6f6e88e87` |
| 14:55:26 | `POST /api/v1/inquiries/{id}/complete-consultation` | 200 | v7 → v8 | `8a11fe96-3c90-411d-83c0-6f4e6766295b` |
| 14:55:26 | `GET /api/v1/inquiries/{id}` | 200 | `COMPLETION_PENDING`, v8 | `d3c7e3ee-008b-4713-8f18-584726bcd0b1` |

추가 Cross-client 추적값:

- 실제 AI 분석 완료: `c907c3ac-228a-4cca-9c19-e14cef948318`
- Mobile 상담 요청 완료: `c77b8b27-6823-498d-a633-74da92c16fa6`
- Mobile 최종 상태 재조회: `5e36e34b-e742-4a0d-b306-896cd2ac8c50`

Backend 구조화 로그의 `http_method`, `request_route`, `status_code`, `correlation_id`와 Django HTTP 로그의 시각·응답 코드를 함께 대조했습니다. 각 요청은 서로 다른 추적값을 사용하며, Cross-client 동일 업무 건은 `inquiry_id`로 연결했습니다.

## 6. 현재 Web 코드 재검증

2026-08-13 현재 통합 SHA `6e786e4`에서 다시 실행했습니다.

| 명령 | 결과 |
|---|---:|
| `npm.cmd test -- --maxWorkers=1` | PASS — 34 files, 155 tests |
| `npm.cmd run lint` | PASS |
| `npm.cmd run typecheck` | PASS |
| `npm.cmd run build` | PASS — Vite production build |

검증 범위에는 Remote DTO/Mapper, 목록·상세 Query, 상담 Action, 서버 Snapshot 동기화, 409 재조회, 입력 보존, 상담 기록 복구, Public Evidence 안전 Fallback이 포함됩니다.

## 7. 요청 형식 회신

### 7.1 Web 상담 사전 Smoke

```ini
sender=한예나
receiver=최지용
scope=WEB_CONSULTATION_PRE_SMOKE
web_sha=6e786e4edafa90ca882260630119b9e613170d95
backend_runtime_sha=1cd190559dcc6271799620ef6eea50de6a733388
remote_mode=true
mock_fallback=DISABLED
login_list_detail=PASS
start_consultation=PASS
save_summary=PASS
confirm_summary=PASS
complete_consultation=PASS
refresh_persistence=PASS
state_allowed_actions=PASS
role_403_404=PASS
lint=PASS
typecheck=PASS
build=PASS
pre_smoke=PASS
blocker=NONE
completion_code=WEB_PRE_SMOKE_PASS
```

### 7.2 동일 Inquiry G4 Web 공동 Smoke

```ini
sender=한예나
receiver=최지용
scope=G4_SAME_INQUIRY_WEB
backend_runtime_sha=1cd190559dcc6271799620ef6eea50de6a733388
web_sha=6e786e4edafa90ca882260630119b9e613170d95
inquiry_id=96d76459-cffe-43f9-b927-67a8aedf1fc7
correlation_id=start:5a9085e0-3246-41fc-a73f-7b869c461170,save:039415b0-06be-4405-a8e5-855a58416861,confirm:6fdc622f-db7e-43cf-acb0-04e6f6e88e87,complete:8a11fe96-3c90-411d-83c0-6f4e6766295b
same_inquiry_list_detail=PASS
other_consultant_404=PASS
start_save_confirm_complete=PASS
final_state_refresh=PASS
g4_result=PASS
blocker=NONE
completion_code=G4_WEB_PASS
```

## 8. 재현 및 환경 참고사항

오늘 최신 SHA에서 격리 DB를 다시 기동해 화면을 재조회하려 했으나, 로컬 `backend/.venv`가 참조하는 Python 3.13 Base Interpreter 경로가 삭제되어 Backend 재기동은 중단했습니다. 다른 Python Runtime에 기존 Site Packages를 연결하면 `psycopg` Binary 호환 오류가 발생합니다.

이 항목은 14:52~15:00 KST에 이미 완료한 실제 G4 결과를 무효화하지 않으며, 위 결과는 실제 Browser·Backend 로그·DB 상태와 현재 Web 자동 검증으로 판정했습니다. 다만 다른 PC에서 재실행하려면 다음이 선행되어야 합니다.

1. Backend Python 3.13 가상환경 복구 또는 재생성
2. 격리 Seed/DB 준비
3. 실제 실행 직전 Backend·Web SHA 재기록
4. 운영 PostgreSQL 환경의 row-lock 공동 Smoke는 별도 Gate로 수행

## 9. 범위 준수

- Queue·Claim UI, 자동 배정, 신규 상태를 Web에 추가하지 않았습니다.
- Dashboard·AI 검수 UI를 변경하지 않았습니다.
- Public Evidence 신규 화면·DTO를 만들지 않았습니다.
- 내부 Chunk ID, Vector Score, Prompt, AI Trace를 노출하지 않았습니다.
- Remote 실패를 Mock/Fake 성공으로 대체하지 않았습니다.
- 이번 회신은 `G4_WEB_PASS`를 기록하며, Web 단독 결과만으로 전체 E2E를 새로 선언하지 않습니다.

