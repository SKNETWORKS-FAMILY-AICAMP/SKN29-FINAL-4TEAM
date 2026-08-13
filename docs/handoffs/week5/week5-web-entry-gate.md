# Week 5 Web Entry Gate — Backend Runtime 대응표

> 점검일: 2026-08-11
> 담당: 한예나 — Web Frontend
> 현재 Branch: `yena`
> 현재 작업 시작 Commit: `11f0950ec6cd14c8b03a438ddfb75bc2edec6514`
> 최신 `origin/main`: `541b2fa85bab6885689c083bcc4d9912cbf4de5b` (`2026-08-11 | 은진 브랜치 병합`)
> 기준선 포함 여부: 현재 Branch에 위 `origin/main` Commit이 포함되어 있음

## 1. 실행환경과 Gate 결과

| 항목 | 결과 |
|---|---|
| Node | `v26.4.0` |
| npm | `11.17.0` |
| 의존성 | `npm ls --depth=0` 성공, 설치 Package 확인 완료 |
| Web Test | `32 files / 139 tests PASS` |
| ESLint | `PASS` |
| TypeScript | `npm run typecheck` 추가 후 `PASS` |
| Production Build | `PASS` |
| Diff whitespace | `git diff --check PASS` |

`package.json`에 별도 `typecheck` Script가 없어서 현재 TypeScript 설정에 맞는 `tsc -b` Script를 추가했다. Build도 `tsc -b && vite build`로 동일 TypeScript Gate를 다시 확인한다.

### Backend Test 실행 상태

Backend Route·OpenAPI·기존 API Test 코드는 최신 기준으로 대조했다. 다만 이 작업환경의 기본 Python과 Codex Bundle Python에는 `pytest`가 없고, `backend/.venv`는 Interpreter Process를 생성하지 못해 Backend Test를 이번 Gate에서 새로 실행하지 못했다.

- 시스템 Python: `No module named pytest`
- Bundle Python: `No module named pytest`
- `backend/.venv`: `Unable to create process`

따라서 아래 `RUNTIME_DONE`은 최신 Backend Route 존재, OpenAPI `x-runtime-status: IMPLEMENTED`, 대응 API Test 존재를 뜻한다. 공용 실행환경의 Live Smoke 완료를 뜻하지 않는다.

## 2. 상담사 P0 Endpoint Runtime 대응표

| Method | Endpoint | Backend Route | OpenAPI | 기존 Runtime Test | Web Adapter | 판정 |
|---|---|---:|---:|---:|---:|---|
| `GET` | `/api/v1/inquiries` | 있음 | `IMPLEMENTED` | `test_consultant_inquiry_runtime.py` | 연결됨 | `RUNTIME_DONE` |
| `GET` | `/api/v1/inquiries/{id}` | 있음 | `IMPLEMENTED` | `test_consultant_inquiry_runtime.py` | 연결됨 | `RUNTIME_DONE` |
| `POST` | `/api/v1/inquiries/{id}/start-consultation` | 있음 | `IMPLEMENTED` | `test_consultation_visit_runtime.py` | 연결됨 | `RUNTIME_DONE` |
| `PATCH` | `/api/v1/inquiries/{id}/consultation-summary` | 있음 | `IMPLEMENTED` | `test_consultation_visit_runtime.py` | 연결됨 | `RUNTIME_DONE` |
| `POST` | `/api/v1/inquiries/{id}/consultation-summary/confirm` | 있음 | `IMPLEMENTED` | `test_consultation_visit_runtime.py` | 연결됨 | `RUNTIME_DONE` |
| `POST` | `/api/v1/inquiries/{id}/complete-consultation` | 있음 | `IMPLEMENTED` | `test_consultation_visit_runtime.py` | 연결됨 | `RUNTIME_DONE` |
| `POST` | `/api/v1/inquiries/{id}/visit-review` | 있음 | `IMPLEMENTED` | `test_consultation_visit_runtime.py` | 연결됨 | `RUNTIME_DONE` |
| `POST` | `/api/v1/inquiries/{id}/visits` | 있음 | `IMPLEMENTED` | `test_consultation_visit_runtime.py` | 연결됨 | `RUNTIME_DONE` |
| `POST` | `/api/v1/inquiries/{id}/visit-not-needed` | 있음 | `IMPLEMENTED` | `test_consultation_visit_runtime.py` | 연결됨 | `RUNTIME_DONE` |
| `PATCH` | `/api/v1/visits/{visit_id}/schedule` | 있음 | `IMPLEMENTED` | `test_consultation_visit_runtime.py` | Adapter 연결됨, 신규 기사 Source 대기 | `RUNTIME_DONE` + `BLOCKED_BY_BACKEND` |
| `POST` | `/api/v1/visits/{visit_id}/confirm` | 있음 | `IMPLEMENTED` | `test_consultation_visit_runtime.py` | 연결됨 | `RUNTIME_DONE` |

### P0 밖의 확인 결과

- `POST /api/v1/visits/{visit_id}/start`: OpenAPI 계약은 있으나 `x-runtime-status: NOT_IMPLEMENTED`, 기사 역할 Endpoint이므로 상담사 Web P0에서는 `NOT_P0`로 분류한다.
- `POST /api/v1/visits/{visit_id}/complete`: OpenAPI 계약은 있으나 `x-runtime-status: NOT_IMPLEMENTED`, 기사 역할 Endpoint이므로 상담사 Web P0에서는 `NOT_P0`로 분류한다.
- AI·Evidence는 문의 상세 OpenAPI에서 `DEC-008` 제외로 명시되어 있어 현재 `CONTRACT_ONLY`이다.

## 3. Mock → Remote 전환 목록

| 위치 | 현재 의미 | Remote 자동 Mock 대체 | 조치/판정 |
|---|---|---:|---|
| `app/config/env.ts`의 `VITE_USE_MOCK_API` | App 시작 시 Mock/Remote를 명시적으로 선택 | 요청 실패 시 대체 없음 | Production 환경변수 누락은 Remote로 해석하도록 수정 |
| `.env.example` | 실행 예시 | 해당 없음 | `VITE_USE_MOCK_API=false`, `VITE_MOCK_AUTHENTICATED=false`로 변경 |
| `consultantWorkspaceDataRepository` | 목록·상세 비동기 Data Source | 없음 | Remote는 `requestApi`만 사용, 실패를 그대로 전달 |
| `consultantWorkspaceRepository` | Mock 화면용 동기 Repository | Remote에서 빈 값 반환 | `BACKEND_BLOCKED` 문구를 `READY_FOR_WEB_INTEGRATION`으로 갱신; Mock 제거 시 Repository 자체 삭제 후보 |
| `useSaveConsultation` | Mock/Remote 상담 저장 분기 | 없음 | Remote는 실제 4개 상담 API만 호출 |
| `consultationMockApi.getNextStatus()` | Mock Scenario 전용 상태 계산 | Remote에서는 호출되지 않음 | `MOCK_ONLY`; Mock 종료 시 삭제 |
| `ConsultantDashboardPage`의 `inquiryStateUpdates`·`CompactConsultationDesk` | Mock 인라인 상담 상태 Snapshot | Remote 상세에서는 사용되지 않음 | `MOCK_ONLY`; Mock 종료 시 삭제 |
| `VisitTransitionPage`의 `availableMockActions`·`lastAction` | Mock 방문 흐름 계산 | Remote에서는 사용되지 않음 | `MOCK_ONLY`; Mock 종료 시 삭제 |
| `RemoteVisitTransitionPanel` | 실제 방문 API 처리 | 없음 | Mock 기사 목록과 Mock 기본 문구 재사용 제거 완료 |
| `ApiRuntimeStatus`·상담사 Layout | 현재 Data Source 표시 | 해당 없음 | Remote에서도 Mock이라고 표시하던 문구 수정 완료 |
| `runtime-status/apiIntegrationReadiness.ts` | 화면용 Runtime 대응표 | 해당 없음 | 4주차 `BACKEND_BLOCKED` 고정표를 현재 11개 P0 Runtime 표로 교체 |

## 4. 실제 계약 불일치·잔여 내부 판단 목록

| 항목 | 위치 | 판정 | 처리 |
|---|---|---|---|
| `assignee` Filter | `useCounselorQueueFilters.ts`, `CounselorFilters` | Backend Query 계약에 없음 | 현재 화면에서 사용하지 않는 Mock legacy. Mock 제거 단계에서 타입·URL Parser와 함께 삭제 |
| `consultation` Filter | 같은 위치 | Backend Query 계약에 없음 | 현재 화면에서 사용하지 않는 Mock legacy. 삭제 대상 |
| URL `status` Filter | 같은 위치 | URL에는 남지만 실제 Remote Query는 업무함 `BUCKET_STATUSES`가 우선 | 이중 상태 Source. 업무함 단일 Source로 정리할 삭제 대상 |
| 검색 `q` | 목록 화면·Repository | Backend 계약과 일치 | 문의번호·증상 원문·고객명·제품 모델 검색 Runtime 확인 |
| 위험도·우선순위·기간·정렬·Page | 목록 화면·Repository | Backend 계약과 일치 | 유지 |
| Web `nextStatus` | `consultationMockApi.ts` | Remote 계약과 불일치하지만 Mock 분기 안에 격리됨 | Mock 제거 때 삭제, Remote로 이동 금지 |
| Web 로컬 `allowed_actions` 계산 | Mock Projection·Mock 방문 화면 | Remote 계약과 불일치하지만 Mock 분기 안에 격리됨 | Remote는 Backend 응답만 사용; Mock 제거 때 삭제 |
| 신규 방문 기사 선택 | 기존 Remote 방문 화면이 `MOCK_TECHNICIANS`를 사용 | 실제 기사 Source 계약 불일치 | Mock 목록 제거. Backend 상세에 이미 배정된 기사만 재사용 가능, 신규 일정 저장 버튼 비활성화 |
| 방문 날짜·시간 | Remote 방문 화면 | 계약 일치 | `type=date`, `YYYY-MM-DD`만 전송; `datetime-local` 없음 |
| 상담 완료 Body | 상담 Write Repository | 기존 Web 타입이 저장 DTO를 재사용 | `state_version`만 허용하도록 수정 완료 |

## 5. 주소·PII 노출 점검

| 화면/데이터 | 결과 | 조치 |
|---|---|---|
| 상담사 목록 고객명 | Backend `customer_display_name_masked` 사용 | 유지 |
| Remote 상세 고객 전화 | Backend 합성 전화 원문을 그대로 표시하고 있었음 | Web에서 `maskCustomerPhone()` 적용 완료 |
| Remote 상세 주소 | DTO와 화면에 없음 | 유지; 임의 추가 금지 |
| Mock 상담 상세 주소 | `serviceAddress` 표시 | `MOCK_ONLY`; 실제 고객 주소로 오인하지 않도록 Mock 제거 시 함께 삭제 |
| 기사 전화 | Remote 방문 화면에서 표시하지 않음 | 유지 |
| Correlation ID | 오류 추적용 식별자만 표시 | 개인정보가 아니며 유지 |

## 6. AI Evidence 공개·비공개 필드 점검

Web Public Evidence allowlist는 다음 7개 필드만 정의한다.

- `dataClassification`
- `documentTitle`
- `documentVersion`
- `page`
- `sourceLandingUrl`
- `summary`
- `verificationLabel`

`sourceLandingUrl`은 HTTPS만 화면에 전달한다. `chunk_id`, 검색 점수, 내부 파일 경로, Prompt, Token, Chain-of-Thought는 Web 공개 타입에 없다.

현재 Remote 문의 상세 계약은 DEC-008을 제외하고 AI·Evidence DTO를 제공하지 않으므로 화면 연결 상태는 `CONTRACT_ONLY`이다. Web이 Mock Evidence를 Remote 응답처럼 보완하지 않는다.

## 7. 5주차 Web Blocker 목록

| Blocker | 상태 | 담당/협업 | 해제 조건 | 목표일 |
|---|---|---|---|---|
| 신규 방문 기사 선택 Source 없음 | `BLOCKED_BY_BACKEND` | 최지용 / 양정현·김은진·한예나 | 기사 목록 Endpoint 또는 승인된 공용 합성 기사 Fixture·UUID Crosswalk 제공 | 2026-08-13 |
| AI·Evidence Public DTO 없음 | `CONTRACT_ONLY` | 이동윤·최지용 / 윤승혁·한예나 | DEC-008 Public allowlist, Evidence Crosswalk, Backend 조립 Endpoint와 오류 Wrapper 확정 | 2026-08-12 |
| 공용 Remote Live Smoke 미실행 | `BLOCKED_BY_BACKEND` | 최지용·김은진 / 한예나 | Base URL, 상담사 계정, 배정 Inquiry UUID, Log 확인 권한 제공 | 2026-08-13 |
| Backend Test 환경 실행 불가 | `BLOCKED_BY_BACKEND` | 최지용·김은진 | 재현 가능한 Python/의존성 설치 절차 또는 CI Test 결과 공유 | 2026-08-12 |
| 대표 전체 Web E2E | `READY_FOR_WEB_INTEGRATION` | 김은진 / 전 담당자 | 위 Runtime·AI·Fixture 해제 후 같은 Commit과 Scenario로 실행 | 2026-08-14 |
| 운영 대시보드 집계 | `MOCK_ONLY`·`NOT_P0` | 윤승혁·최지용 | 상담사 P0 이후 별도 Runtime 범위와 일정 승인 | 6주차 WBS에서 결정 |

## 8. Backend가 열리면 즉시 실행할 순서

1. `VITE_USE_MOCK_API=false`, `VITE_MOCK_AUTHENTICATED=false`, 공용 `VITE_API_BASE_URL`로 Production Build를 만든다.
2. 상담사 로그인 후 `GET /inquiries`의 검색·Filter·Sort·Pagination과 403·422를 확인한다.
3. 배정 Inquiry UUID로 `GET /inquiries/{id}`의 200·404·Nullable Section·PII 마스킹을 확인한다.
4. 상담 시작→기록 저장→요약 확정→상담 완료를 실행하고 `state_version`, `allowed_actions`, Idempotency, 409 Draft 유지를 확인한다.
5. 방문 검토→방문 필요/불필요 분기→Visit 생성까지 실행한다.
6. 승인된 기사 Source로 기사·date-only 일정을 저장한 뒤 방문을 확정한다.
7. 각 요청의 `X-Correlation-ID`로 Backend Log와 DB 상태 이력을 대조한다.
8. Public AI·Evidence DTO가 열리면 내부 필드 비노출과 정상·근거 없음·Fallback Scenario를 확인한다.
9. 김은진의 대표 Fixture·Scenario ID로 전체 E2E를 실행하고 윤승혁에게 P0 판정을 요청한다.

## 9. Entry Gate 결론

- 상담사 P0 11개 Endpoint는 최신 Backend Route와 OpenAPI에서 `IMPLEMENTED` 상태이며 Web Adapter가 존재한다.
- Remote 요청 실패를 Mock 성공으로 바꾸는 자동 Fallback은 없다.
- Production 환경변수 누락 시 Mock으로 시작하던 위험과 Remote 화면의 고정 Mock 표시를 제거했다.
- Remote 방문 화면에서 오래된 Mock 기사·기본 인계 문구를 제거했다.
- 계약에 없는 Filter와 Web 상태 계산은 Mock 분기에만 남아 있으며 5주차 Mock 종료 시 삭제할 위치가 식별되었다.
- 실제 Live 완료 판정은 기사 Source, 공용 Runtime·계정·Fixture, AI Public DTO와 E2E가 제공된 뒤 수행한다.
