# 고객·방문기사 Iridescent Liquid Glass 디자인

## 목적

고객용과 방문기사용 Android 앱의 기능·데이터 흐름은 유지하면서,
투명 버튼과 진주빛 반사가 보이는 Liquid Glass 시각 체계로 통일한다.

## 적용 범위

- 공용 배경과 색상 토큰
- 공용 투명 패널
- 공용 투명 버튼
- 공용 액션 카드와 상태 타일
- 고객 로그인
- 고객 홈
- 고객 문진
- 고객 안전 안내
- 방문기사 로그인
- 방문 목록·요약
- 방문 사전 점검 리포트

## 시각 원칙

- 흰색 34~72% 투명도를 기본 Glass Fill로 사용한다.
- 파랑·보라·분홍 Pearl Tint를 약하게 겹친다.
- 버튼은 불투명 단색 대신 투명 Fill과 밝은 Border를 사용한다.
- 모서리는 공용 토큰 기준인 16dp Control, 24dp Card를 유지한다.
- 위험 안내는 투명도를 사용하지 않고 불투명 흰색과 위험색 Border를
  사용한다.
- 실제 Blur API와 신규 외부 라이브러리는 사용하지 않는다.
- 화면 기능, API 계약, 상태 전환, Fixture 구분은 변경하지 않는다.

## 공용 컴포넌트

`LiquidGlassComponents.kt`

- `LiquidGlassPanel`
- `LiquidGlassButton`
- `LiquidGlassActionCard`
- `LiquidGlassMetricTile`
- `LiquidGlassPill`

## 2026-08-05 컴파일 보정

초기 T-045 Commit `88f50c5`에서 현재 Compose 버전이 제공하지 않는
`Modifier.matchParentSize()` import를 사용해 `:core:compileDebugKotlin`이
실패했다.

배경 Layer는 부모 `Box`를 채우기만 하면 되므로 신규 의존성이나 레이아웃
변경 없이 `Modifier.fillMaxSize()`로 교체한다.

초기 적용 스크립트는 Gradle 실패 뒤에도 성공으로 판단했다. 보정 이후에는
`Start-Process -Wait -PassThru`가 반환하는 실제 Exit Code를 검사한다.
Exit Code가 0이 아니면 Stage, Commit, Push 이전에 즉시 중단한다.

## 엄격 검증

```text
:core:test
:customer-app:testDebugUnitTest
:customer-app:assembleDebug
:technician-app:testDebugUnitTest
:technician-app:assembleDebug
```

반복 검증 스크립트:

```text
mobile/scripts/verify-t045-iridescent-liquid-glass.ps1
```
