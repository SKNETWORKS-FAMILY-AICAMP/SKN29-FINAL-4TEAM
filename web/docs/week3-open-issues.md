# 3주차 Web 미해결 이슈

- 기준일: 2026-07-29
- 원칙: 아래 항목은 화면에서 임의 확정하지 않고 담당 계약·Backend 구현 확인 후 처리한다.

## P0 · 실제 연동 전 필수

### AUTH-01 실제 인증 Runtime E2E

- 현재: `/auth/demo-login`, `/auth/refresh`, `/auth/logout`, `/me` 계약 Client와 Mapper, 메모리 Token 세션, Authorization Header, 401 Refresh single-flight·원요청 1회 재시도 구현
- 남은 검증: 실제 Backend에서 로그인·Refresh rotation·만료·로그아웃·`/me` 응답과 브라우저 Redirect 확인
- 완료 조건: 실제 로그인·만료·로그아웃 후 동일한 Guard와 세션 제거 동작 확인

### CONS-API-01 상담 요청·응답 Schema 확정

- 현재: `SaveConsultationRequest`, `CompleteConsultationRequest`, `ConsultationRecord`, `ConsultationSummary`가 빈 객체
- 영향: 상담 Form 필드와 Endpoint별 Body를 확정 타입으로 만들 수 없음
- 완료 조건: 임시 저장·요약 수정·확정·완료·방문 검토 요청과 성공·오류 응답 확정

### CONS-API-02 실제 409·422 응답 연결

- 현재: Web 계약 Mock에서 `STATE-CONFLICT-01`과 `DUPLICATE-EVENT-01` DTO·Mapper, 입력 보존과 상태 Snapshot 적용 경계를 검증
- 남은 결정: `field_errors` 실제 Wrapper와 Backend Runtime 응답 연결
- 완료 조건: Backend 테스트 API의 409·422 Fixture와 Web 통합 테스트 통과

## P1 · 계약 정합성

### CONTRACT-01 Inquiry 상태 코드 불일치

- 상태 머신과 DB Draft의 일부 상태명이 다르다.
- Web은 상태 머신 계약을 우선하되 Runtime API 확정 전 Mapper에 별칭을 추가하지 않는다.

### CONTRACT-02 위험도 대소문자

- 공통 계약·DB: `general`, `caution`, `danger`
- 프로토타입 Workspace Mock: `GENERAL`, `CAUTION`, `DANGER`
- Web Mock Mapper는 대소문자를 정규화하고 알 수 없는 값은 `UNKNOWN`으로 안전하게 표시한다.
- 실제 API 연결 시 공통 소문자 계약을 최종 타입 원천으로 교체할 필요가 있다.

### CONTRACT-03 운영 대시보드 응답

- 현재: `/admin` P1 Mock 화면과 OPERATOR Guard 구현. 공식 합성 문의를 기준으로 필터·지표·분포·예외 목록 제공
- 남은 결정: 실제 집계 API의 기준 시각, SLA 지연 기준, 부분 실패 응답, 역할별 공개 필드
- 교체 지점: `features/operations-dashboard/model` 입력을 실제 API Adapter 응답으로 교체하며 화면·URL 필터 계약은 유지

## P2 · 품질·운영 준비

### WEB-01 Legacy CSS 범위 축소

- 상담 Workspace가 v13 시각 동일성을 위해 Legacy CSS를 사용한다.
- 다른 역할 화면과 클래스 충돌 여부를 확인하고 기능 단위 CSS로 점진 분리한다.

### WEB-02 E2E 확대

- 현재: jsdom 통합 테스트와 수동 브라우저 검증
- 남음: 로그인→목록→상세→상담 저장→방문 전환 실제 API E2E

### WEB-03 개발 의존성 보안 경고 검토

- 테스트 도구 설치 시 npm이 개발 의존성 트리의 high 경고 2건을 보고했다.
- `npm audit fix --force`는 실행하지 않는다.
- 팀 승인 하에 영향 패키지와 안전한 버전 범위를 확인한 뒤 잠금 파일을 갱신한다.

## 완료된 노출 보안 조치

- Evidence 화면에서 `chunk_id`, 내부 `document_id` 제거
- 내부 파일 경로, 검색 점수, 원문 전체, Prompt, Trace 미노출
- 실제 고객 개인정보 대신 합성 표시명 사용

