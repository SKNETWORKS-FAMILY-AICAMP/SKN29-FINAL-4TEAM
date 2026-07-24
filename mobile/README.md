# Mobile

Kotlin + Jetpack Compose 기반 고객·방문기사 Android 애플리케이션입니다.

## 구조 원칙

- 단일 `app` Gradle 모듈
- 기능 중심 패키지
- 초기 기능은 `Screen + ViewModel + UiState`
- 상태 전환은 백엔드의 `allowed_actions`와 `state_version`을 기준으로 처리
- 공식 근거는 백엔드가 조립한 `EvidenceCardDTO`만 사용

> `gradlew`, `gradlew.bat`, `gradle/wrapper/`는 구조 확인용 골격입니다.
> 실제 Android Studio 프로젝트를 생성한 뒤 Wrapper 파일로 교체해야 합니다.
