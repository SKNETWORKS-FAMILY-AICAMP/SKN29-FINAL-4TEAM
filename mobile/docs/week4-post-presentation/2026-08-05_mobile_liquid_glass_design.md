# 고객·방문기사 Mobile Liquid Glass 디자인 통일

## 기준

`WaterCare 공용 디자인 토큰 v0.1 — Liquid Glass`를 Mobile Compose
구현의 단일 기준으로 사용한다.

## 적용 범위

- Core Material Theme
- 공통 Loading·Error·Pending 카드
- 고객용 공통 Screen·Section·Product·Evidence·Status 컴포넌트
- 고객 로그인·홈·문진·안전 안내 화면 표면
- 방문기사 로그인·방문 목록·사전 점검 화면 표면
- 버튼·카드·텍스트·위험도 색상
- 고객·기사 앱 배경 그라디언트

## 토큰

| 구분 | 값 |
| --- | --- |
| 배경 상단 | `#F2F9FB` |
| 배경 하단 | `#DCEEF3` |
| 주 강조 | `#2E8BA3` |
| 강조 텍스트 | `#1B5A6B` |
| 본문 | `#12262B` |
| 보조 텍스트 | `#4A6169` |
| 카드 | White 55% |
| 중요 카드 | White 72% |
| 카드 테두리 | White 65% |
| 카드 반경 | 24dp |
| 컨트롤 반경 | 16dp |
| 일반 | `#2E8BA3` |
| 주의 | `#C08A2E` |
| 위험 | `#C0392B` |

## 안전 원칙

- 위험 안내 카드는 흰색 불투명 배경을 사용한다.
- 위험 테두리와 텍스트는 `#C0392B`를 사용한다.
- 위험 카드에는 반투명 유리 표면을 사용하지 않는다.
- 일반·주의·위험 Badge는 기존 식별 목적을 유지한다.

## 성능 원칙

- 새 UI 라이브러리를 추가하지 않는다.
- `Modifier.blur`를 사용하지 않는다.
- Android 버전과 단말 성능에 관계없이 동작하도록 반투명 표면과
  그라디언트만 사용한다.
- 레이아웃 구조, Navigation, ViewModel, Repository는 변경하지 않는다.

## 검증

```powershell
cd C:\skn29\WaterCare\mobile

.\gradlew.bat `
  :core:test `
  :customer-app:testDebugUnitTest `
  :customer-app:assembleDebug `
  :technician-app:testDebugUnitTest `
  :technician-app:assembleDebug `
  --no-daemon
```

실물 단말에서는 고객 로그인 화면과 방문기사 로그인 화면을 각각 캡처해
배경·카드·강조색을 나란히 비교한다.
