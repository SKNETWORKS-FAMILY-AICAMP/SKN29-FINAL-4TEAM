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

## 환경변수와 Mock 인증

`web/.env.example`을 기준으로 로컬 설정을 구성합니다.

| 환경변수 | 기본값 | 용도 |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `/api/v1` | Backend API 기준 경로 |
| `VITE_USE_MOCK_API` | `true` | 합성 Mock 사용 여부 |
| `VITE_MOCK_AUTHENTICATED` | `true` | 시작 시 Mock 인증 여부 |
| `VITE_MOCK_ROLE` | `CONSULTANT` | `CUSTOMER`, `CONSULTANT`, `TECHNICIAN`, `OPERATOR` 중 역할 |

기본 설정에서는 기존처럼 상담사 문의 화면이 바로 열립니다. 미인증·역할별 Guard를 수동 확인하려면 `.env.local`에서 Mock 인증과 역할을 변경한 뒤 개발 서버를 다시 시작합니다. 실제 JWT나 비밀값은 `.env` 파일에 하드코딩하지 않습니다.

## 검증 명령

```powershell
npm.cmd run lint
npm.cmd run test
npm.cmd run build
```

- `lint`: TypeScript·React 정적 검사
- `test`: Vitest 단위·컴포넌트·통합 테스트 1회 실행
- `test:watch`: 파일 변경을 감지하는 테스트 개발 모드
- `build`: TypeScript 검사 후 Production 번들 생성

## 상담 처리 Mock 확인

상담 큐에서 `DEMO-INQ-003 · 냉수 온도 이상`을 선택하면 상담 기록 Form을 확인할 수 있습니다. 우측 `Mock 응답 테스트`에서 성공, 403, 409, 422, 네트워크 오류를 선택할 수 있습니다.

409에서는 사용자가 작성한 내용을 버리지 않고 최신 `stateVersion`과 `allowed_actions`를 반영하며 자동 재전송하지 않습니다. 이 선택 항목과 `consultationMockApi.ts`는 실제 상담 API가 확정되면 교체해야 합니다.

## 방문 전환 Mock 확인

브라우저에서 `http://localhost:5173/consultant/inquiries/DEMO-INQ-004/visit-transition`를 열면 `CONS-03` 방문 전환 화면을 바로 확인할 수 있습니다.

고객 희망일과 가상 방문기사를 선택해 `일정 조율 저장`을 누르거나, 가상 방문 확정일까지 입력해 `방문 확정`을 누릅니다. 두 동작은 화면 안의 상태와 `stateVersion`만 변경하며 실제 API 요청, 기사 배정, 알림, 일정 저장은 수행하지 않습니다.

## 현재 연동 상태

- 문의 목록·상세·상담 처리: 합성 Mock
- 인증·역할: `AuthProvider` 합성 사용자 Mock, `AuthGuard`·`RoleGuard` 실제 Route 제어
- 상담 쓰기 API: 계약 미확정으로 Provisional Mock DTO 사용
- 방문 전환 저장·확정: 프론트 화면 전용 Mock, 실제 API 호출 없음
- `allowed_actions`, `state_version`, `Idempotency-Key`, `X-Correlation-ID`: 상태 머신 계약의 연결 위치 반영
- 실제 고객 개인정보: 사용하지 않음

필드별 확정·미확정 상태는 [week3-screen-api-db-map.md](./docs/week3-screen-api-db-map.md)를 확인합니다.
기술 선택과 미연동 범위는 [week3-web-decisions.md](./docs/week3-web-decisions.md), [week3-open-issues.md](./docs/week3-open-issues.md)를 확인합니다.
