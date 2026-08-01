# Week 3 Mobile Decisions

- Final local verification: 2026-07-31 15:56:02 +09:00
- Local branch: jeonghyun
- GitHub connection/push: intentionally not performed

## Approved structure

- customer-app, 	echnician-app, and core three-module structure is retained.
- Customer and technician apps share common models, networking, repositories, and design components through core.
- The older single-app-module wording is treated as superseded by the current approved three-module structure.

## UI and UX

- Customer app: sky-blue primary visual language.
- Technician app: orange operational accent.
- Supplied customer and technician mascot assets are restored in the app and launcher icons.
- Material 3 rounded cards, large actions, plain-language labels, loading, error, and unavailable states are used.
- Risk states are communicated with labels and messages in addition to color.

## Data and API

- The mobile app uses the existing Backend contract and Demo login first.
- Missing production endpoints remain explicit Mock or unavailable states.
- The mobile app does not invent production endpoints or modify Backend source.
- Physical-device local development uses 127.0.0.1:8000 with db reverse tcp:8000 tcp:8000.

## Safety

- Unknown codes do not become confirmed failures.
- Danger, consultation-required, and no-evidence states hide resolved/close actions.
- Evidence UI excludes internal chunk_id, source paths, retrieval text, and internal storage URLs.

## 2026-07-31 재설계 결정 — 백엔드 계약 연동 중심 전환

### 배경

초기 모바일은 로컬 상태(`MutableStateFlow`) 기반 시연 데모로 구성되어 있었다.
카카오맵 실시간 추적, QR 스캔, 오류코드 OCR, 서비스콜 화면이 포함되어 있었으나,
모두 서버 계약과 무관하게 앱 내부에서만 동작하는 구조였다.

3주차 목표가 백엔드 계약(`contracts/state-machine/inquiry-states.yaml`) 기반 연동으로
확정되면서, 계약과 무관한 로컬 데모 기능은 유지 비용 대비 이점이 없다고 판단했다.

### 결정

계약 연동에 필요한 최소 흐름만 남기고 재작성한다.

**제거한 기능**

| 기능 | 제거 사유 |
| --- | --- |
| 카카오맵 실시간 기사 추적 | 계약에 추적 상태 축이 없고, 좌표 스크립트 재생 방식이라 서버 데이터와 무관 |
| QR 스캔 · 오류코드 OCR (ML Kit) | 계약의 `raw_text`·`representative_symptom_code` 입력으로 대체 가능 |
| 서비스콜 화면 | 계약에 대응 Endpoint 없음 |
| 방문 상태 하위 코드(`EN_ROUTE`·`NEARBY`·`ARRIVED`) | 계약 `visit_status_codes` 외 값이라 서버 전송 불가 |

**남긴 흐름**

로그인 → 고객 홈 → 증상 입력 → AI 안내 → 문의 상태 확인.
계약의 문의 13개 상태와 `allowed_actions` 기반 액션 표시까지 포함한다.

### 상태 표현 방식 변경

문의 상태를 `enum class` 에서 `String` + 라벨 매핑(`InquiryLabels.status`)으로 변경했다.

- enum 은 서버가 신규 상태를 추가하면 역직렬화 단계에서 예외가 발생한다.
- String 은 미지의 코드가 와도 `"확인 중 ($code)"` 로 표시되며 앱이 중단되지 않는다.
- 계약 13개 상태의 한국어 라벨은 `InquiryLabels` 한 곳에서만 관리한다.

### 저장소 정리

- 재작성 과정에서 생성한 백업 디렉터리 11개(`mobile_*_backup_*`)와 `.bak` 파일 11개를 삭제했다.
- 버전 관리는 git 이력으로 수행하며, 저장소에 백업 사본을 두지 않는다.
- `.gitignore` 에 `*.bak`, `*_backup_*/`, `mobile/**/build/` 규칙을 추가하고,
  구 경로(`WaterCareAndroid/`)를 `mobile/` 로 정정했으며 중복 규칙을 제거했다.
