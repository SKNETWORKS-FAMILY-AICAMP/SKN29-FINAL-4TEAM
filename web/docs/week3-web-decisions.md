# 3주차 Web 기술 결정

- 기준일: 2026-07-28
- 범위: React 실행 기반, 상담사 P0 흐름, Mock 교체 구조, Router·권한, 테스트

## 결정 1. 팀 Vite 프로젝트 설정을 유지한다

- 개인 프로토타입의 `package.json`, Router, 직접 DOM 조작 코드는 복사하지 않는다.
- 프로토타입 v13의 상담사 화면 구조와 시각 자산은 React 컴포넌트로 이관한다.
- 팀 저장소의 React 19, Vite 8, TypeScript 구성을 기준으로 한다.

## 결정 2. 인증 상태와 Route 권한을 분리한다

- `AuthProvider`: 현재 사용자와 인증 여부를 제공한다.
- `AuthGuard`: 미인증 사용자를 `/login`으로 이동시키고 원래 요청 경로를 보존한다.
- `RoleGuard`: 인증된 사용자의 역할이 화면 역할과 다르면 `/forbidden`으로 이동시킨다.
- 역할 코드는 계약의 `CUSTOMER`, `CONSULTANT`, `TECHNICIAN`, `OPERATOR`만 허용한다.
- 역할 실패는 403, 리소스 접근 은닉은 실제 API에서 404 정책을 적용한다.

## 결정 3. 기본 로컬 경험은 기존 상담사 화면을 유지한다

- `VITE_USE_MOCK_API=true`, `VITE_MOCK_AUTHENTICATED=true`, `VITE_MOCK_ROLE=CONSULTANT`를 기본으로 한다.
- 따라서 환경변수를 만들지 않아도 `/`에서 상담 큐로 진입한다.
- 실제 JWT·Refresh Token을 Web 저장소에 임의 저장하지 않는다.
- Backend 인증 연동 시 Provider 내부 구현만 교체하고 Guard와 페이지 계약은 유지한다.

## 결정 4. 운영 화면은 계약 확정 전 Placeholder로 제한한다

- `/admin`은 `OPERATOR` 역할만 접근할 수 있다.
- 현재는 `ADMIN-01` Route·권한·정보 구조만 제공한다.
- 운영 집계·예외 API가 확정되기 전 차트와 수치를 임의 생성하지 않는다.

## 결정 5. 행동 버튼은 Backend `allowed_actions`만 따른다

- 상담 화면은 상태 코드를 보고 버튼을 재계산하지 않는다.
- 현재 고정 `allowedActions`는 Mock Backend 응답 Fixture로 취급한다.
- `code`, `label`, `operation_id`, `style`, 확인 메시지를 View Model로 변환한다.

## 결정 6. 상담 쓰기는 교체 가능한 Provisional Mock으로 둔다

- 상담 OpenAPI Schema가 비어 있으므로 Mock DTO를 확정 API 타입으로 부르지 않는다.
- `state_version`, `Idempotency-Key`, `X-Correlation-ID` 연결 위치만 계약대로 준비한다.
- 409에서는 입력 보존, 최신 상태·버전·허용 행동 반영, 사용자 재시도 원칙을 지킨다.

## 결정 7. 테스트는 사용자 행동 중심으로 작성한다

- Vitest, jsdom, React Testing Library를 사용한다.
- 내부 구현 함수보다 역할, 입력, 버튼, 오류 안내 등 사용자가 확인하는 결과를 검사한다.
- 단위·컴포넌트·통합 테스트를 `web/tests/**`로 분리한다.
- 브라우저 수동 검증은 레이아웃과 기존 URL 회귀를 보완한다.

## 결정 8. Backend 준비 전에는 CONS-03을 화면 전용 Mock으로 유지한다

- 개인 프로토타입의 방문 사유, 고객 희망일, 가상 방문기사, 점검 우선순위, 기사 전달사항, 안전 유의사항, 가상 방문 확정일 구성을 React로 이관한다.
- 일정 저장과 방문 확정은 브라우저 메모리에서만 상태를 바꾸며 API 요청, 기사 배정, 알림, 일정 생성을 수행하지 않는다.
- 희망일과 확정일을 구분하고, 확정일이 희망일보다 빠르지 않은지만 프론트에서 검증한다.
- 실제 Backend 계약이 준비되면 화면 구조를 유지한 채 Mock 저장 함수만 교체한다.
