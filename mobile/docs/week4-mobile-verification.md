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
| `:customer-app:connectedDebugAndroidTest` | 보류 |

## Compose UI Test 보류 사유

실기기에서 Instrumentation Test는 실행되지만 Compose Semantics Tree가 생성되지 않아
`No compose hierarchies found in the app` 오류가 발생한다.

Core 테스트, 단위 테스트, Lint, APK 빌드 및 실제 앱 설치에는 영향을 주지 않는다.
발표 기능 확대보다 실제 Backend 연동을 우선하기 위해 별도 테스트 인프라 결함으로 기록한다.

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