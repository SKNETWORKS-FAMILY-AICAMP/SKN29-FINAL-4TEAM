# 고객용 시연 앱 구조

```text
고객 Android 앱
├─ QR Scanner
│  └─ Google Code Scanner
├─ Questionnaire
├─ Error Detection
├─ Visit Request
└─ Technician Tracking
   ├─ Kakao Maps SDK v2
   └─ Demo Tracking Repository
```

## 고객 처리 흐름

```text
QR 촬영
├─ 오류 코드 있음 → 오류 결과
└─ 오류 코드 없음 → 문진

문진 제출
→ 오류 결과
→ 방문 요청
→ 기사 배정
→ 이동 추적
```

## 이동 상태

```text
CONFIRMED
→ EN_ROUTE / DRIVING
→ NEARBY / WALKING
→ ARRIVED
→ IN_PROGRESS
```

현재 `TrackingRepository`가 발표용 좌표를 시간 순서대로 전달합니다.
실제 서비스 전환 시 Repository 구현을 REST 또는 WebSocket 기반으로 교체합니다.
