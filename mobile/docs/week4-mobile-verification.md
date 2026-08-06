# 4주차 모바일 문의 생성·증상 제출 연동 검증 결과

- 검증 일자: `2026-08-04`
- 작업 브랜치: `jeonghyun`
- 구현 기준 Commit: `5692124`
- Java: `openjdk version "17.0.19" 2026-04-21 LTS`
- Gradle: `Gradle 9.5.0`

## 적용 범위

- CUST-02 문의 생성을 실제 `POST /api/v1/inquiries`에 연결
- 문의 생성 성공 후 실제 `POST /api/v1/inquiries/{inquiry_id}/submit` 호출
- 생성 응답의 `inquiry_id`, `inquiry_code`, `state_version`을 증상 제출 단계에 사용
- 증상 제출 응답의 `state`, `state_version`, `allowed_actions`, `idempotent_replay`를 모바일 모델에 보관
- 문의 생성과 증상 제출에 서로 다른 Idempotency Key 사용
- 문의 생성 실패 재시도 시 동일 생성 Key 재사용
- 문의 생성 성공 후 증상 제출 실패 재시도 시 새 문의를 생성하지 않고 동일 문의·동일 제출 Key 재사용
- Remote 실패를 Mock 성공으로 자동 대체하지 않음
- 고객 홈·AI 안내는 확정 Runtime Endpoint 대기 상태이므로 명시적 Mock 유지
- 상담 요청은 `API 준비 중` 안내 유지

## 자동 검증 결과

- Core 단위 테스트: PASS
- Customer 단위 테스트: PASS
- Customer Debug APK: PASS
- Technician Debug APK: PASS
- Gradle 결과: `BUILD SUCCESSFUL in 37s`
- Gradle 작업: `106 actionable tasks: 15 executed, 91 up-to-date`
- `git diff --check`: 공백 오류 없음
- LF→CRLF 메시지는 Windows 작업 복사본 줄바꿈 안내이며 검증 실패가 아님

단위 테스트에서 확인한 항목:

- 문의 생성 실패 후 동일 Payload 재시도 시 동일 생성 Idempotency Key 사용
- 성공 완료 후 동일 Payload를 새 작업으로 제출하면 새로운 Key 사용
- 증상 제출 실패 후 재시도 시 문의 생성은 1회만 수행
- 증상 제출 재시도 시 동일 제출 Idempotency Key 사용
- 증상 제출에 문의 생성 응답의 `state_version` 전달
- 성공 결과에 `QUESTIONNAIRE_IN_PROGRESS`, 새 `state_version`, `allowed_actions` 보관

## 실단말 Runtime 검증

- 실단말 앱 프로세스 기준 검증 시각: `2026-08-04 12:12:38 ~ 12:13:18 +09:00`
- `GET /health`: PASS (`200 OK`, 10ms)
- `POST /api/v1/auth/demo-login`: PASS (`200 OK`, 50ms)
- `GET /api/v1/me`: PASS (`200 OK`, 20ms)
- `POST /api/v1/inquiries`: PASS (`201 Created`, 222ms)
- `POST /api/v1/inquiries/{inquiry_id}/submit`: PASS (`200 OK`, 308ms)
- 실제 문의 UUID는 검증 로그에서 마스킹함
- Demo 고객의 실제 활성 구독 UUID는 Runtime 검증에만 일시 적용함
- Runtime 검증 직후 `CustomerCareRepository.kt`를 Git 기준 상태로 복구함
- 복구 후 Runtime 전용 UUID 변경은 작업 트리에 남아 있지 않음

실제 요청 순서:

```text
POST /api/v1/inquiries
<-- 201 Created

POST /api/v1/inquiries/<UUID>/submit
<-- 200 OK
```

## 현재 확인된 완료 범위

- CUST-02 문의 생성 Runtime 호출
- 문의 생성 후 증상 제출 Runtime 호출
- 두 단계의 HTTP 성공 상태
- 문의 생성 실패와 증상 제출 실패를 구분한 재시도 구조
- 증상 제출 실패 시 중복 문의 생성을 막는 Repository 동작
- 실제 구독 UUID의 소스 미잔류 확인

## 남은 Runtime 검증

1. 증상 제출 응답 본문의 `state`, `state_version`, `allowed_actions`, `idempotent_replay` 실제 값 확인
2. 동일 Key·동일 Body를 다시 전송한 Idempotency Replay Runtime 검증
3. 동일 Key·다른 Body의 409 Conflict Runtime 검증
4. 실제 409 응답을 Mobile UiState와 최신 상태 이동 동작으로 검증
5. 앱 프로세스 종료 이후에도 진행 중 Idempotency 작업을 복원하는 영속화 검토

현재 OkHttp Logging은 `BASIC`이므로 HTTP 상태는 검증했지만 응답 본문 상세값은 Logcat에서 확인하지 못했다.

## 제한사항

- 고객 홈 제품·구독 조회 Runtime Endpoint 대기
- 운영용 활성 구독 ID 공급 경로 미확정
- AI 안내·Evidence Runtime Endpoint 대기
- 상담 요청 Runtime Endpoint 대기
- 위 기능은 실제 Endpoint가 제공되기 전까지 가짜 성공으로 처리하지 않음
- 운영용 활성 구독 ID 공급 경로는 Backend 계약 승인 전까지 `REVIEW_REQUEST / IMPLEMENTATION_HOLD`

## 기존 검증 이력

- Customer 실단말 Compose UI 테스트: PASS (`SM-F721N`, 2/2)
- 전용 Debug `ComposeTestActivity` Host 적용 후 실단말 2건 통과
- 최초 Compose 테스트의 잘못된 PASS 기록은 PowerShell 실패 코드 차단 누락 때문이었으며 이후 수정함
- CUST-02 최초 Runtime 검증에서 문의 생성 `201 Created` 확인
- 요청 계약 보정으로 `channel_code=MOBILE`, 필수 `raw_text` 검증 적용
