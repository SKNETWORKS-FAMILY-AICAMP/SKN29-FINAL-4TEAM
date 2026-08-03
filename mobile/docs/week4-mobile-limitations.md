# 4주차 모바일 제한사항

## 문서 기준

- 기준 브랜치: `personal/mobile-extension`
- 기능 기준 커밋: `e14893e`
- 작성일: 2026-08-03

## 실제 Backend 연동 범위

| 기능 | 상태 | Endpoint |
| --- | --- | --- |
| Backend 상태 확인 | 실제 연동 | `GET /health` |
| Demo 고객 로그인 | 실제 연동 | `POST /api/v1/auth/demo-login` |
| 저장 세션 확인 | 실제 연동 | `GET /api/v1/me` |
| 고객 문의 생성 | 실제 연동 | `POST /api/v1/inquiries` |
| 고객 문의 취소 | 실제 연동 | `POST /api/v1/inquiries/{id}/cancel` |

## Mock 또는 Blocked 범위

| 기능 | 현재 상태 | 제한 이유 |
| --- | --- | --- |
| 고객 제품·구독 홈 데이터 | Mock | 구독 조회 Runtime API 미제공 |
| 문의 상세·타임라인 | Mock 또는 Blocked | Runtime API 미제공 |
| AI Guidance 조회 | Mock 또는 Blocked | Runtime API 미제공 |
| 상담 요청 | Blocked | 상담 요청 Runtime API 미제공 |
| 방문 일정 조회 | Blocked | 상담사·방문 일정 Runtime API 미제공 |
| 방문기사 방문 목록 | 화면 골격 수준 | 기사 방문 Runtime API 미제공 |
| QR 제품 조회 | Blocked | 제품 조회 Runtime API 미제공 |

## 안전 처리 원칙

- Backend의 `allowed_actions`에 포함된 지원 동작만 화면에 표시한다.
- 알 수 없는 Action은 임의 해석하거나 버튼으로 표시하지 않는다.
- 상담 API가 없는 상태에서는 실제 요청 버튼을 노출하지 않는다.
- 위험·근거 없음 상태에서는 해결·종료 동작을 노출하지 않는다.
- 미연동 기능은 Mock 또는 Blocked임을 화면과 발표에서 명시한다.

## 로컬 설정과 보안

- Demo 구독 식별자는 `mobile/local.properties`에서만 관리한다.
- `mobile/local.properties`는 Git에 포함하지 않는다.
- UUID, Token, 사용자 내부 ID, correlation ID가 보이는 로그와 캡처는 저장소에 포함하지 않는다.
- 발표 화면에는 합성 Demo 고객 데이터만 사용한다.

## 알려진 비차단 사항

- Cold Start 시 `/health`와 `/api/v1/me`가 각각 두 번 호출될 수 있다.
- 현재 호출은 모두 200 OK이며 발표 흐름을 차단하지 않는다.
- Compose UI Test에서 기존 `createAndroidComposeRule` API 사용 중단 예정 경고가 발생한다.
- 발표 APK는 Debug 빌드이며 운영 배포용 서명 APK가 아니다.

## 발표 시 설명 문구

> 현재 고객 인증과 문의 생성·취소는 실제 Backend에 연결되어 있습니다. 구독 조회, AI 안내 조회, 상담 요청과 방문 일정은 Runtime API가 아직 제공되지 않아 Mock 또는 Blocked 상태로 명확히 구분했습니다.
