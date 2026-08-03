# 4주차 모바일 기준선 검증 결과

## 검증 환경

- Branch: personal/mobile-extension
- OS: Windows 11
- JDK: OpenJDK 17.0.19
- Gradle: 9.5.0
- Kotlin: 2.3.20
- Compile SDK: 37
- Target SDK: 37
- Min SDK: 26
- 실기기: SM-F721N / Android 16
- Backend: http://127.0.0.1:8000
- PostgreSQL: Docker localhost:5433

## 검증 결과

| 항목 | 결과 |
| --- | --- |
| `:core:test` | 성공 |
| `:customer-app:testDebugUnitTest` | 성공 |
| `:customer-app:lintDebug` | 성공 |
| `:customer-app:assembleDebug` | 성공 |
| `:technician-app:assembleDebug` | 성공 |
| Backend `/health` | HTTP 200 |
| 고객 앱 실기기 설치 | 성공 |
| `:customer-app:connectedDebugAndroidTest` | 성공 · 실기기 2개 테스트 통과 |

## Compose UI Test 실기기 검증

- 실행 기기: Samsung SM-F721N / Android 16
- 실행 Task: `:customer-app:connectedDebugAndroidTest`
- 실행 결과: 2개 테스트 실행, 2개 통과
- Gradle 결과: `BUILD SUCCESSFUL`
- `createAndroidComposeRule` 사용 중단 예정 경고는 후속 마이그레이션 대상으로 기록
- 판정: 고객 최소 Compose UI Test 통과

## 계약 정합성

- 운영 UI에서 계약 외 Action 버튼 제거
- 알 수 없거나 Mobile Route가 없는 Action은 표시하지 않음
- 문의 상태 `RESOLVED`는 정상 상태 코드이므로 유지
- `backend/**`, `contracts/**` 변경 없음
- 문의 생성·취소는 `RemoteInquiryRepository` 사용
- Home·Guidance는 Runtime API 부재로 Mock/Blocked 상태 유지

## 보안

- Demo 구독 UUID는 `mobile/local.properties`에만 저장
- `mobile/local.properties`는 Git 제외 확인
- UUID, Token, 비밀번호는 문서와 Git에 기록하지 않음
## 2026-08-03 실제 API Smoke Test

### 검증 환경

- 실제 Android 기기: Samsung SM-F721N
- Backend 연결: adb reverse tcp:8000 tcp:8000
- 고객 앱 패키지: com.skn29.watercare.customer
- 테스트 데이터 식별자는 로컬 환경변수에서만 관리

### 실제 API 검증 결과

| 흐름 | Endpoint | 결과 |
| --- | --- | --- |
| Demo 로그인 | POST /api/v1/auth/demo-login | 200 OK |
| 사용자 조회 | GET /api/v1/me | 200 OK |
| Backend 상태 | GET /health | 200 OK |
| 문의 생성 | POST /api/v1/inquiries | 201 Created |
| 문의 취소 | POST /api/v1/inquiries/{id}/cancel | 200 OK |

### 화면·계약 확인

- 문의 생성 직후 Backend 상태 DRAFT, state_version 1 확인
- Backend allowed_actions로 SUBMIT_SYMPTOM, CANCEL_INQUIRY 확인
- CANCEL_INQUIRY가 제공된 경우에만 실제 문의 취소 버튼 노출
- 취소 확인 팝업에서 사용자가 취소 진행을 선택한 뒤 실제 취소 Endpoint 호출
- 임의 상태명이나 지원되지 않는 동작을 Mobile에서 생성하지 않음

### 제한 사항

- /me/subscriptions Runtime API가 없어 Demo 구독 UUID는 mobile/local.properties에서만 임시 관리
- 문의 상세·타임라인·Guidance·상담 API는 Backend Runtime 제공 전까지 Mock 또는 Blocked 유지
- 문의 ID, correlation ID, 액세스 토큰이 포함될 수 있는 원본 캡처는 Git에 포함하지 않음

### Token 재사용 실기기 검증

- 검증일: 2026-08-03
- 기존 앱 데이터를 유지한 상태에서 APK를 덮어 설치함
- 앱 프로세스 종료 후 Cold Start로 재실행함
- Demo 로그인 API를 다시 호출하지 않고 저장된 Token을 사용함
- GET /api/v1/me 응답 200 OK 확인
- 판정: Demo 로그인 및 Token 재사용 통과
- 참고: /me 중복 호출은 후속 최적화 후보로 기록
