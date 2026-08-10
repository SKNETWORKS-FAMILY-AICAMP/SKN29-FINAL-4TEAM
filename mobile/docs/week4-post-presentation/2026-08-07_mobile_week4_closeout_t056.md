# T-056 모바일 행동 구분 및 4주차 잔여업무 정리

기준일: 2026-08-07

## 1. 이번 패치에서 수행하는 항목

### UI·사용성

- 정보 박스는 물방울 Glass 카드 형태를 유지한다.
- 실제 실행 버튼은 Pill 형태 + Accent 색 + `›` 행동 표시를 사용한다.
- Action Tile에는 `›`를 표시하고 비활성 기능은 `준비 중`으로 표시한다.
- 실제 클릭 컨트롤에 Press Indication을 복구한다.
- Compact 버튼 최소 높이를 44dp, 일반 버튼을 56dp로 보강한다.
- 기사 방문 목록은 카드 전체 클릭을 제거하고 `방문 상세 보기` 버튼을 별도로 둔다.
- 홈 하단 Navigation의 미구현 메뉴는 비활성 처리한다.

### 미연동 기능의 안전 처리

다음 고객 홈 기능은 현재 Route/Endpoint가 없으므로 실행 가능한 버튼처럼
보이지 않게 비활성 처리한다.

- 제품 정보
- 제품 상세
- 관리 가이드
- 고객센터
- 자가 점검
- 보증/혜택
- 이벤트
- 방문 일정
- 제품/관리/알림/마이 하단 메뉴

Guidance의 `REQUEST_CONSULTATION`은 계약상 허용 Action이더라도 Mobile에서
실제 상담 Endpoint가 없으므로 `상담 요청 · API 준비 중`으로 비활성 표시한다.

### 안전 안내

근거 없음 Fixture에서 `임의 추정 안내`를 제거한다.

- `safeActions = emptyList()`
- `requiresConsultation = true`
- UI에서는 `근거가 없어 자가조치를 추정하지 않습니다.`를 표시한다.

### 빌드·검증

- `gradlew.bat`이 실제 Gradle/Java 종료 코드를 반환하도록 수정한다.
- `verify-build.bat`이 Core·Customer·Technician 테스트와 두 Debug APK를 확인한다.
- `week4-mobile-smoke-test.ps1`에 `ExpectedBranch`, `ExpectedCommit`을 추가한다.
- Smoke Test가 방문기사 단위 테스트·APK·SHA-256도 기록한다.

## 2. 현재 지침서 기준 완료로 볼 수 있는 항목

- 고객 문의 생성·증상 제출 Remote 경로
- 400/401/403/404/409/5xx/Network 오류 분리 기반
- `state_version`, `allowed_actions` 표시 기반
- 위험·근거 없음에서 해결/종료 버튼 비노출
- Evidence 내부 RAG 필드 비노출
- 고객/기사 Tone Provider
- `TechnicianViewModel`의 실제 `TechnicianApp` 연결
- 방문 목록·읽기 전용 사전 점검 리포트 Fixture 골격
- 고객/기사 Debug APK 빌드 검증 경로

## 3. Backend/AI 계약 때문에 현재 Mobile 단독으로 완료할 수 없는 항목

### 고객 홈 실연동

현재 Mobile `WaterCareApi`에는 다음 Runtime Endpoint가 선언되어 있지 않다.

- `GET /api/v1/me/subscriptions`
- `GET /api/v1/me/subscriptions/{subscription_id}`
- 케어 이력 조회

따라서 Remote 고객 홈이 실제 제품·구독 응답을 사용하도록 임의 Endpoint를
추가하지 않는다. Backend Runtime 제공 후 DTO/Repository를 연결해야 한다.

### 실제 Guidance/Evidence

현재 Mobile `WaterCareApi`에 고객 Guidance/Evidence 조회 Endpoint가 없다.
따라서 현재 안내는 명시적 Fixture/Fallback 경계를 유지한다.

### 실제 상담 요청

상담 요청 Endpoint가 Mobile 계약에 없으므로 활성 버튼을 제공하지 않는다.
Endpoint 제공 후 `REQUEST_CONSULTATION` 응답의 최신 상태,
`state_version`, `allowed_actions`를 반영해야 한다.

### 409 이후 서버 최신 상태 재조회

현재 문의 상세 GET Runtime 계약이 없으므로 409 후 서버 최신 문의를 다시
조회하는 전체 동선을 임의 구현하지 않는다.

## 4. 이번 패치 후 남는 수동 확인

1. `verify-t056-action-affordance-week4.ps1` 실행 결과 PASS
2. 고객·방문기사 APK 실단말 설치
3. 고객 홈에서 정보 카드와 실행 버튼 구분 확인
4. 비활성 기능이 눌리지 않는지 확인
5. 문진 선택 Chip 및 입력창 Focus 확인
6. 위험·근거 없음 안내에서 잘못된 완료 행동이 없는지 확인
7. 기사 방문 카드에서 `방문 상세 보기` 버튼으로만 진입되는지 확인
8. `week4-mobile-smoke-test.ps1` 결과 파일 저장
9. 최종 화면 캡처 및 필요 시 Fallback 영상 보관

## 5. 외부 계약 제공 후 다음 구현 순서

1. T-018/T-019 제품·구독 Runtime 연결
2. 실제 고객 Home Repository 연결 및 Fake 위임 제거
3. Guidance/Evidence Runtime 연결
4. Consultation Runtime 연결
5. 문의 상세/최신 상태 조회 계약이 제공되면 409 Refresh 동선 연결
6. 각 실제 응답에 대한 UI/통합 테스트 추가


---

## T-056 FIX1 복구 메모

초기 T-056 PowerShell 변환 스크립트는 고객 홈 소스를 담는 변수로
`$Home`을 사용했다. Windows PowerShell은 변수명을 대소문자 구분 없이
처리하므로 `$Home`은 자동 변수 `$HOME`과 충돌했고 다음 오류로 중단됐다.

```text
HOME 변수는 읽기 전용이거나 상수이므로 덮어쓸 수 없습니다.
```

FIX1에서는 해당 로컬 변수를 `$HomeContent`로 변경했다.

초기 T-056 실패 지점 이전에 공통 UI 파일이 일부 수정됐을 수 있으므로
FIX1 적용기는 T-056 허용 파일 외의 로컬 변경이 없는지 먼저 검사한 뒤,
T-056 대상 기존 파일만 기준 Commit `f193f923c7c71e999c95b51c8c1db9c762937eed`
상태로 복구하고 수정된 T-056을 처음부터 다시 적용한다.

다른 사용자 작업 파일은 복구하거나 삭제하지 않는다.
