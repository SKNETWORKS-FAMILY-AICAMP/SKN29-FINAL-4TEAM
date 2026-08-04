# 3주차 모바일 테스트 결과

## 1. 검증 명령

```cmd
gradlew.bat :customer-app:clean :technician-app:clean :customer-app:testDebugUnitTest :customer-app:connectedDebugAndroidTest :customer-app:assembleDebug :technician-app:assembleDebug
```

## 2. 테스트 및 빌드 결과

- 고객 앱 단위 테스트: 통과
- 고객 앱 Compose UI 연결 테스트: 통과
- 고객 앱 Debug APK 빌드: 통과
- 기사 앱 Debug APK 빌드: 통과
- 백엔드 및 API 계약 보호 경로 변경 포함 여부: 없음

## 3. 테스트 기기

- 모델명: `SM_F721N`
- ADB 시리얼: `R3CT8076D7B`

## 4. 백엔드 연동 결과

- PostgreSQL 컨테이너 실행: 통과
- Django 시스템 검사: 통과
- Django 마이그레이션: 통과
- 데모 데이터 준비: 통과
- Health API 확인: 통과
- 고객 데모 로그인: 통과
- 기사 데모 로그인: 통과
- 실제 기기 포트 연결: `tcp:8000 -> tcp:8000`
- 모바일 백엔드 주소: `http://127.0.0.1:8000/`

## 5. 실행 환경

- Java: OpenJDK 17.0.19
- Gradle: 9.5.0
- Kotlin: 2.3.20
- 운영체제: Windows 11
