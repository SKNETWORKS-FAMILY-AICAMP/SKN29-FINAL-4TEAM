# 고객·방문기사 Reference Dashboard Android 적용

## 구현 방식

- Android 실행 UI: Kotlin + Jetpack Compose
- 공용 디자인 계약: TypeScript
- 이미지 자산: 로컬 PNG
- 외부 UI 라이브러리: 추가하지 않음

TypeScript는 Android 화면을 직접 렌더링하지 않는다. 고객용·방문기사용
색상과 섹션 구조를 기록하는 디자인 계약이며, 실제 Android 화면은 동일한
값을 Kotlin Compose 컴포넌트로 구현한다.

## 고객용

- 블루·라벤더 포인트
- 고객 역할 Chip
- 사용량 Hero 카드
- 홈 상태 4열
- 빠른 실행 4열
- 사용 중인 제품 카드
- 서비스 & 지원
- 하단 메뉴

계측 API가 아직 없으므로 사용량 12.5L는 `계측 API 연결 전 UI 예시`로
명확히 표시한다. 실제 Backend 성공이나 제품 계측값으로 오인시키지 않는다.

## 방문기사용

- 민트·아쿠아 포인트
- 방문기사 역할 Chip
- 오늘 방문 Hero 카드
- 방문 상태 4열
- 빠른 실행 4열
- 주요 방문 카드
- 지원 & 도구
- 하단 메뉴

방문 목록은 기존 합성 Fixture를 그대로 사용하며 실제 방문 API로
표현하지 않는다.

## 기존 기능 유지

- 고객 문진 시작
- 고객 안전 안내 열기
- 고객 개발 검증 Scenario
- 방문기사 방문 상세 열기
- 로그인·세션 복원
- 실제 Backend/Fixture 구분
- 위험 카드 불투명 처리

## 검증

```text
:core:test
:customer-app:testDebugUnitTest
:customer-app:assembleDebug
:technician-app:testDebugUnitTest
:technician-app:assembleDebug
```
