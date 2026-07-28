# Mobile App Module

단일 `app` Gradle 모듈과 기능 중심 패키지 구조를 사용합니다.

각 기능은 초기에는 `Screen + ViewModel + UiState`로 시작하고,
복잡도가 증가한 기능만 `data/`, `domain/`, `presentation/` 계층으로 분리합니다.
