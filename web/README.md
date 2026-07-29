# Watercare Web

상담사·운영 담당자가 사용하는 React 19, Vite, TypeScript 기반 웹입니다. 현재 상담사 `CONS-01 → CONS-02 → CONS-03` 흐름은 합성 Mock 데이터로 실행됩니다.

## 실행 환경

- Node.js 20.19 이상 또는 22.12 이상
- npm

## 설치와 실행

```powershell
cd C:\Users\Playdata\Desktop\skn29\final\SKN29-FINAL-4TEAM\web
npm.cmd install
npm.cmd run dev
```

브라우저에서 `http://localhost:5173/consultant/inquiries`를 엽니다.

상담 큐의 검색·상태·위험도·우선순위·담당자·접수 기간·정렬·페이지 조건은 URL Query에 유지됩니다. 문의를 선택하면 UUID `inquiry_id`를 사용하는 `CONS-02` 상세 경로로 이동하고, 화면에는 표시용 `inquiry_code`가 노출됩니다. 상단의 상담 큐 복귀 버튼을 누르면 기존 조건으로 돌아갑니다.

## 환경변수와 Mock 인증

`web/.env.example`을 기준으로 로컬 설정을 구성합니다.

| 환경변수 | 기본값 | 용도 |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `/api/v1` | Backend API 기준 경로 |
| `VITE_USE_MOCK_API` | `true` | 합성 Mock 사용 여부 |
| `VITE_MOCK_AUTHENTICATED` | `true` | 시작 시 Mock 인증 여부 |
| `VITE_MOCK_ROLE` | `CONSULTANT` | `CUSTOMER`, `CONSULTANT`, `TECHNICIAN`, `OPERATOR` 중 역할 |

기본 설정에서는 기존처럼 상담사 문의 화면이 바로 열립니다. 미인증·역할별 Guard를 수동 확인하려면 `.env.local`에서 Mock 인증과 역할을 변경한 뒤 개발 서버를 다시 시작합니다. Access·Refresh Token은 Web Storage에 저장하지 않고 실행 중인 메모리 세션에만 보관하며, 실제 JWT나 비밀값은 `.env` 파일에 하드코딩하지 않습니다.

## 검증 명령

```powershell
npm.cmd run lint
npm.cmd run test
npm.cmd run build
npm.cmd run fixtures:generate
```

- `lint`: TypeScript·React 정적 검사
- `test`: Vitest 단위·컴포넌트·통합 테스트 1회 실행
- `test:watch`: 파일 변경을 감지하는 테스트 개발 모드
- `build`: TypeScript 검사 후 Production 번들 생성
- `fixtures:generate`: 공식 `data/synthetic/fixtures/inquiries.json`에서 Web 계약 테스트 Fixture 재생성

## 상담 처리 Mock 확인

상담 큐에서 `INQ-20260704-0013 · 제품 누수`를 선택하면 상담 기록 Form을 확인할 수 있습니다. 우측 `Mock 응답 테스트`에서 성공, 403, 409, 422, 네트워크 오류를 선택할 수 있습니다. 목록은 `data/synthetic/fixtures/inquiries.json`의 공식 합성 문의 24건을, 근거 카드는 검증된 `data/processed/structured/evidence/jac104_evidence_registry.jsonl`의 공개 필드만 View Model로 변환해 사용합니다.

`STATE-CONFLICT-01`에서는 사용자가 작성한 내용을 버리지 않고 최신 `stateVersion`과 Action code 배열을 화면 행동 객체로 복구하며 자동 재전송하지 않습니다. `DUPLICATE-EVENT-01`의 빈 `details`는 최신 상태 Snapshot으로 적용하지 않고 새 멱등 키가 필요한 오류로 안내합니다. 성공 응답의 `allowed_actions`는 label·operation 정보가 포함된 객체 배열로 별도 처리합니다. 이 선택 항목과 `consultationMockApi.ts`는 실제 상담 API가 확정되면 교체해야 합니다.

목록 상태는 `?mockState=loading|empty|error|forbidden`, 상세 상태는 `?mockState=loading|error|forbidden|unsupported`, 상세 부분 실패는 `?mockFailure=ai|evidence|timeline`으로 확인할 수 있습니다. 이 Query는 개발용 Mock 검증 경로입니다.

## 방문 전환 Mock 확인

브라우저에서 `http://localhost:5173/consultant/inquiries/a6bdf6b7-b9ba-553a-8447-f928384c1ad1/visit-transition`를 열면 `CONS-03` 방문 전환 화면을 바로 확인할 수 있습니다. 이 UUID의 화면 표시용 문의 번호는 `INQ-20260703-0008`입니다.

고객 희망일과 가상 방문기사를 선택해 `일정 조율 저장`을 누르거나, 가상 방문 확정일까지 입력해 `방문 확정`을 누릅니다. 두 동작은 화면 안의 상태와 `stateVersion`만 변경하며 실제 API 요청, 기사 배정, 알림, 일정 저장은 수행하지 않습니다.

## 운영 대시보드 P1 Mock

`VITE_MOCK_ROLE=OPERATOR`로 설정한 뒤 `/admin`에서 확인합니다. 기간·제품·관리유형·담당자·증상·위험도·상태·처리 결과 필터, 핵심 지표, 증상·상태 분포, 운영 예외 목록과 반응형 화면을 구현했습니다. 현재 공식 합성 문의 24건을 사용하며 실제 운영 집계 API만 미연동 상태입니다.

개발 상태는 `/admin?mockState=loading|empty|error`로 확인할 수 있습니다.

## 현재 연동 상태

- 문의 목록·상세·상담 처리: 합성 Mock
- 운영 대시보드: T-101~T-104 프론트 P1 Mock 완료, 실제 집계 API 미연동
- 공통 API Wrapper·오류·페이지네이션: 계약 타입과 테스트 구현 완료, Authorization·Correlation 공통 적용
- 인증·역할: Demo Login·Refresh·Logout·`/me` 계약 Client, 메모리 세션, 401 Refresh single-flight·원요청 1회 재시도, `AuthGuard`·`RoleGuard` 구현. 기본 실행은 합성 Mock이며 실제 Backend E2E는 보류
- 상담 쓰기 API: 계약 미확정으로 Provisional Mock DTO 사용
- 방문 전환 저장·확정: 프론트 화면 전용 Mock, 실제 API 호출 없음
- `allowed_actions`, `state_version`: 상태 머신 계약의 연결 위치 반영
- `Idempotency-Key`: 논리 쓰기 시작 시 생성하고 동일한 네트워크 재시도에만 보존
- `X-Correlation-ID`: 전송 시도마다 새 UUID를 생성
- 실제 고객 개인정보: 사용하지 않음

필드별 확정·미확정 상태는 [week3-screen-api-db-map.md](./docs/week3-screen-api-db-map.md)를 확인합니다.
기술 선택과 미연동 범위는 [week3-web-decisions.md](./docs/week3-web-decisions.md), [week3-open-issues.md](./docs/week3-open-issues.md)를 확인합니다.
3주차 완료 기준 대조표는 [week3-completion-checklist.md](./docs/week3-completion-checklist.md)를 확인합니다.
