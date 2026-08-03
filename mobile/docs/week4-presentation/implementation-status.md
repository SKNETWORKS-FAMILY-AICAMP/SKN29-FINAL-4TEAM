# 모바일 구현 상태표

## 1. 문서 기준

- 기준 브랜치: `personal/mobile-extension`
- 기준 커밋: `a9c286d`
- 대상: 4주차 중간 발표 고객용 Android 앱
- 실제 연동 판정 기준: 실기기에서 실제 Backend 요청과 응답을 확인한 기능

## 2. 구현 상태 분류

| 구분 | 의미 |
| --- | --- |
| 실제 연동 | 실기기에서 실제 Backend 요청·응답을 검증한 기능 |
| Mock·Fallback | 명시적인 합성 데이터 또는 실패 재현 Scenario |
| Blocked | Runtime API가 없어 실제 동작 버튼을 노출하지 않는 기능 |
| 화면 골격 | 화면 구조만 존재하고 실제 업무 API에는 연결되지 않은 기능 |
| 미구현 | 현재 발표 범위에 포함하지 않은 기능 |

## 3. 고객 앱 구현 상태

| 기능 | 발표 분류 | Backend 또는 처리 방식 | 검증 결과 | 발표 시연 |
| --- | --- | --- | --- | --- |
| Backend 상태 확인 | 실제 연동 | `GET /health` | 실기기 200 OK | 시연 가능 |
| Demo 고객 로그인 | 실제 연동 | `POST /api/v1/auth/demo-login` | 실기기 200 OK | 초기 세션이 없을 때 가능 |
| 저장 Token 재사용 | 실제 연동 | `GET /api/v1/me` | Cold Start 200 OK | 시연 가능 |
| 고객 홈 제품·구독 정보 | Mock·Fallback | 합성 고객·제품·구독 데이터 | 화면 확인 | Mock임을 명시 |
| 증상 입력 | 실제 화면 | Compose 입력 및 ViewModel 상태 보존 | 단위·UI Test 통과 | 시연 가능 |
| 고객 문의 생성 | 실제 연동 | `POST /api/v1/inquiries` | 실기기 201 Created | 데이터 초기화 확인 시만 시연 |
| 고객 문의 취소 | 실제 연동 | `POST /api/v1/inquiries/{id}/cancel` | 실기기 200 OK | 발표용 문의가 있을 때만 시연 |
| 문의 상태 표시 | 실제 응답 기반 | Backend `status`, `state_version` 사용 | DRAFT·version 1 확인 | 문의 생성 시 확인 |
| 허용 행동 표시 | 실제 응답 기반 | Backend `allowed_actions` 사용 | 지원 Action만 표시 | 설명 가능 |
| 일반 Guidance | Mock·Fallback | 명시적 Mock Scenario | Compose UI Test 통과 | 시연 가능 |
| 위험 Guidance | Mock·Fallback | 명시적 위험 Scenario | 해결·종료 Action 미노출 확인 | 시연 가능 |
| 근거 없음 | Mock·Fallback | 명시적 무근거 Scenario | 안전 Fallback 화면 확인 | 시연 가능 |
| AI 실패 | Mock·Fallback | 명시적 AI 실패 Scenario | 실패 화면 확인 | 시연 가능 |
| 네트워크 실패 | Mock·Fallback | 명시적 네트워크 실패 Scenario | 재시도·입력 보존 테스트 통과 | 시연 가능 |
| 상담 요청 | Blocked | 상담 요청 Runtime API 미제공 | 실제 버튼 제거 | 준비 중 안내만 시연 |
| 방문 일정 | Blocked | 일정 Runtime API 미제공 | 비활성 안내 | 설명만 가능 |
| QR 제품 조회 | Blocked | 제품 조회 Runtime API 미제공 | 비활성 안내 | 설명만 가능 |
| 오프라인 미리보기 | Mock·Fallback | 명시적 Preview Mode | 화면 진입 가능 | 장애 시 사용 |

## 4. 오류·상태 처리

| 항목 | 구현 상태 | 검증 |
| --- | --- | --- |
| 400 잘못된 요청 | 구현 완료 | 입력 보존·안전 메시지 테스트 통과 |
| 401 인증 만료 | 구현 완료 | 인증 만료 이벤트 소비·입력 보존 테스트 통과 |
| 403 접근 거부 | 구현 완료 | 안전 메시지·입력 보존 테스트 통과 |
| 404 리소스 없음 | 구현 완료 | 안전 메시지·입력 보존 테스트 통과 |
| 409 상태 충돌 | 구현 완료 | 최신 상태·버전·Action 반영 테스트 통과 |
| 422 검증 실패 | 구현 완료 | 오류 메시지 Mapper 테스트 통과 |
| 500 서버 오류 | 구현 완료 | 공통 오류 메시지 테스트 통과 |
| 503·504 일시 오류 | 구현 완료 | 재시도 가능·입력 보존 테스트 통과 |
| 일반 네트워크 실패 | 구현 완료 | 입력·Idempotency Key 보존 테스트 통과 |
| 알 수 없는 Action | 구현 완료 | 버튼 미노출·원본 값 보존 |

## 5. 방문기사 앱

| 기능 | 발표 분류 | 현재 상태 | 발표 처리 |
| --- | --- | --- | --- |
| 기사 앱 APK 빌드 | 화면 골격 | Debug APK 빌드 성공 | 고객 앱 발표에서는 제외 |
| 기사 Demo 로그인 | 화면 골격 | 정적 Demo 수준 | 실제 인증으로 설명하지 않음 |
| 방문 목록 | 화면 골격 | Runtime API 미연동 | 발표 후 작업 범위 |
| 사전 점검 리포트 | 화면 골격 | 실제 AI·방문 API 미연동 | 발표 후 작업 범위 |
| 방문 수락·출발·도착·완료 | 미구현 | 4주차 필수 범위 제외 | 완료 기능으로 표현 금지 |
| 기사 위치 추적 | 미구현 | 범위 제외 | 시연하지 않음 |

## 6. 발표자료용 수치

- 실제 검증된 `/api/v1` Endpoint: 4개
  - Demo 로그인
  - 현재 사용자 조회
  - 문의 생성
  - 문의 취소
- 운영 상태 확인 Endpoint: 1개
  - Backend Health
- 고객 Compose UI Test: 2개 통과
- 고객 단위 테스트·Lint·Debug APK 빌드: 통과
- 기사 Debug APK 빌드: 통과
- 실기기: Samsung SM-F721N / Android 16

## 7. 발표 설명 요약

> 고객 인증, 저장 세션 복원, 문의 생성과 취소는 실제 Backend에 연결했습니다. 제품·구독 홈과 AI 안내는 Runtime API 미제공으로 Mock 또는 Fallback임을 명확히 표시했고, 상담·방문 일정·QR 기능은 동작하는 것처럼 보이지 않도록 차단했습니다.
