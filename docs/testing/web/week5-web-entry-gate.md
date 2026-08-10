# 5주차 Web Entry Gate 및 실제 API 전환 현황

> 담당: 한예나(Web)  
> 확인일: 2026-08-10 KST  
> 작업 브랜치: `yena`  
> 작업 시작 Commit: `c5d2f47`  
> 확인한 `origin/main`: `dd172c7`  
> 종합 판단: `ENTRY_GATE_DONE / REMOTE_READ_CONSUMER_READY / SHARED_RUNTIME_WAITING`

## 1. 금일 완료한 작업

- 최신 `main` 기준과 Backend 실제 연결 QA 결과를 다시 확인했다.
- Node `v26.4.0`, npm `11.17.0`을 기록했다.
- 상담사 목록·상세용 비동기 Repository를 추가했다.
- 실제 API DTO와 화면용 ViewModel을 분리하고 Mapper를 추가했다.
- `VITE_USE_MOCK_API=true`는 명시적 Mock, `false`는 Remote를 선택하도록 분리했다.
- Remote 실패 시 Mock 성공으로 자동 변경하지 않도록 수정했다.
- 공통 HTTP Client를 사용해 인증·재발급·Timeout·Correlation 처리를 재사용했다.
- 목록 Query는 계약에 있는 `q`, `status`, `risk_level`, `priority`, `from`, `to`, `sort`, `page`, `size`만 전송하도록 만들었다.
- 상세 조회는 공개 Inquiry ID만 URL에 사용하도록 만들었다.
- Mock 상세를 계약 형태로 바꿀 때 서비스 주소를 포함하지 않도록 했다.
- Repository 경계와 Mock 자동 대체 금지 테스트를 추가했다.
- 상담사 목록 화면을 비동기 목록 Query와 서버 `page_info`, `status_counts`에 연결했다.
- 상담사 상세 화면을 비동기 상세 Query의 Loading·Error·Forbidden·Retry 상태에 연결했다.
- Mock 모드에서는 기존 상세 Drawer와 시연 흐름을 유지하고, Remote 모드에서는 실제 API 상세 기본 정보를 표시하도록 분리했다.

## 2. Web 검증 결과

| 확인 항목 | 실행 명령 | 결과 |
| --- | --- | --- |
| 전체 테스트 | `npm test -- --pool=vmThreads --maxWorkers=1` | `31 files, 131 tests PASS` |
| Lint | `npm run lint` | `PASS` |
| TypeScript | `npm run build`의 `tsc -b` | `PASS` |
| Production Build | `npm run build` | `PASS`, 131 modules |
| 신규 Repository·Query·상세 계약 테스트 | 대상 테스트 3개 실행 | `14 tests PASS` |

`package.json`에 별도 `typecheck` 명령이 없어 Production Build에 포함된 `tsc -b` 결과를 TypeScript 검사 결과로 사용했다.

## 3. 실제 API Runtime 대응표

| 기능 | 계약 | Backend Runtime | Web 상태 | 판단 |
| --- | --- | --- | --- | --- |
| 문의 목록 `GET /api/v1/inquiries` | 확정 | Backend 담당자 로컬 구현·검증 완료, Commit·Push 전 | Remote Query·화면 상태 연결 완료 | `WAITING_FOR_SHARED_RUNTIME` |
| 문의 상세 `GET /api/v1/inquiries/{id}` | 확정 | Backend 담당자 로컬 구현·검증 완료, Commit·Push 전 | Remote Section·Null·오류 화면 연결 완료 | `WAITING_FOR_SHARED_RUNTIME` |
| 상담 시작 | 확정 | 미구현 | 연결 대기 | `BLOCKED_BY_BACKEND` |
| 상담 요약 저장 | 확정 | 미구현 | 연결 대기 | `BLOCKED_BY_BACKEND` |
| 상담 요약 확정 | 확정 | 미구현 | 연결 대기 | `BLOCKED_BY_BACKEND` |
| 상담 완료 | 확정 | 미구현 | 연결 대기 | `BLOCKED_BY_BACKEND` |
| 방문 필요 검토 | 확정 | 미구현 | 연결 대기 | `BLOCKED_BY_BACKEND` |
| 방문 생성 | 확정 | 미구현 | 연결 대기 | `BLOCKED_BY_BACKEND` |
| 방문 불필요 처리 | 확정 | 미구현 | 연결 대기 | `BLOCKED_BY_BACKEND` |
| 방문 일정 저장 | 확정 | 미구현 | 연결 대기 | `BLOCKED_BY_BACKEND` |
| 방문 확정 | 확정 | 미구현 | 연결 대기 | `BLOCKED_BY_BACKEND` |
| 공개 Evidence | 공개 Schema와 Route 미완성 | 미구현 | Mock 화면만 존재 | `CONTRACT_ONLY` |

현재 공유 Workspace의 Backend에는 상담사 읽기 Runtime 변경이 아직 반영되지 않았다. 최지용 님의 로컬 구현 Commit·Push와 공용 실행환경 전달 뒤 목록·상세 실제 연결 검증을 진행한다. consultations, visits, evidence 쓰기·공개 Runtime은 계속 대기 상태다.

## 4. Mock → Remote 전환 현황

### 완료

- Mock과 Remote Repository 선택 경계를 분리했다.
- 목록·상세 비동기 메서드와 Remote HTTP 호출을 추가했다.
- DTO → Mapper → ViewModel 경계를 추가했다.
- Remote 모드에서 기존 동기 Repository가 Mock 데이터를 반환하지 않도록 막았다.
- Remote 오류를 Mock 성공으로 바꾸지 않는 테스트를 추가했다.
- Query 문자열과 `page_info`, `status_counts`, Correlation ID 변환 기반을 추가했다.
- 상담사 목록의 Loading·Empty·Error·Forbidden·Retry를 실제 Query 상태와 연결했다.
- 상담사 상세의 Loading·Error·Forbidden·Retry를 실제 Query 상태와 연결했다.
- 이전 요청 완료 후 최신 검색 결과를 덮어쓰지 않도록 요청별 결과 반영 경계를 추가했다.

### 남은 작업

- Backend 200 응답 제공 후 목록·상세 Remote Smoke를 실행한다.
- 상담·방문 Write Repository를 각 Runtime 제공 순서대로 추가한다.
- Backend가 준 `status`, `state_version`, `allowed_actions`만 사용하도록 기존 화면 내부 판단을 제거한다.

## 5. 확인된 계약 불일치

| 항목 | 현재 Web | 확정 기준 | 조치 |
| --- | --- | --- | --- |
| 담당자·상담구분 필터 | Web 전용 필터 존재 | 목록 API Query에 없음 | Remote 화면 연결 때 제거 또는 비활성화 |
| 방문 날짜 | `datetime-local`, `desiredAt`, `confirmedAt` | `preferred_date`, `confirmed_date`의 date-only | 방문 Runtime 연결 전에 수정 |
| 상담사 주소 | Mock 상세에서 서비스 주소 표시 | 상담사 P0 Projection은 주소 제외 | Remote ViewModel에는 주소를 넣지 않음, 기존 Mock 화면은 후속 정리 |
| 상태 판단 | `nextStatus`, 로컬 `allowed_actions` 계산 존재 | Backend 응답을 그대로 사용 | 상담 Write Runtime 연결 때 제거 |
| Evidence | Mock Registry 기반 표시 | Backend 공개 DTO만 사용 | 공개 Schema·Route 확정 후 교체 |

## 6. 남은 Blocker 및 요청 사항

| 제공 담당 | 필요한 내용 | 해제 조건 | 목표일 |
| --- | --- | --- | --- |
| 최지용(Backend) | 상담사 목록·상세 Route와 200 Example | 상담사 계정으로 목록·상세 200, 공통 Wrapper 확인 | 2026-08-11 |
| 최지용(Backend) | 상담 Start·Save·Confirm·Complete Runtime | 최신 `status`, `state_version`, `allowed_actions`, 409 응답 확인 | 2026-08-12 |
| 최지용(Backend) | Visit Review·Create·Not Needed·Schedule·Confirm Runtime | date-only 요청과 저장 결과 확인 | 2026-08-13 |
| 이동영(AI·RAG)·최지용(Backend) | 공개 Evidence 허용 필드와 전달 Route | `chunk_id`, 점수, 파일 경로, Prompt가 없는 응답 확인 | 2026-08-12 |
| 김은진(Data·QA) | Runtime 제공 뒤 Web↔Backend Smoke 지원 | Correlation ID로 HTTP·Log·DB 연결 확인 | Runtime 제공 즉시 |
| 윤승혁(PM) | 위 Runtime 제공 순서와 Evidence 계약 확정 | 5주차 P0 우선순위 고정 | 2026-08-10 |

## 7. 다음 작업 순서

1. Backend 목록 Route가 열리면 상담사 목록을 Remote Repository에 연결한다.
2. 상세 Route가 열리면 Section Mapper와 부분 오류 표시를 연결한다.
3. 상담 Runtime 제공 순서대로 Start → Save → Confirm → Complete를 연결한다.
4. 방문 입력을 date-only로 고친 뒤 Visit Runtime을 연결한다.
5. 공개 Evidence 계약 확정 후 Mock Evidence를 Backend 응답으로 교체한다.
6. 목록·상세·상담·방문 Remote Smoke와 Correlation 추적 결과를 이 문서에 갱신한다.

## 8. 금일 판단

8월 10일 Entry Gate, Remote 전환 기반, 상담사 목록·상세 화면의 비동기 연결과 읽기 계약 검토까지 완료했다. Backend 읽기 Runtime은 담당자 로컬에서 구현됐지만 아직 Commit·Push·공용 실행환경 반영 전이므로 실제 200 응답 검증은 대기한다. 현재 상태를 `REMOTE_READ_CONSUMER_READY / SHARED_RUNTIME_WAITING`으로 유지한다.
