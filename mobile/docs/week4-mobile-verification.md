# 4주차 모바일 1차 연동 검증 결과

- 검증 시각: 2026-08-04 10:00:27 +09:00
- 작업 브랜치: `jeonghyun`
- 패치 기준 Commit: `12d79c341a6b942bcf7858a16ffb9ebc27f05872`
- Java: `openjdk version "17.0.19" 2026-04-21 LTS`
- Gradle: `Gradle 9.5.0`

## 적용 범위

- CUST-02 문의 생성 경로를 실제 `POST /api/v1/inquiries` Repository에 연결
- 동일 Payload 재시도 시 Idempotency Key 재사용
- 성공 응답의 `inquiry_id`, `inquiry_code`, `status_code`, `state_version`, `allowed_actions` 보관
- 계약에 없는 Fake Action 제거
- 상담 요청 빈 Callback 제거 및 `API 준비 중` 안내 유지
- 고객 홈·AI 안내는 Runtime Endpoint 미공개 상태이므로 명시적 Mock 유지
- Remote 실패를 Mock 성공으로 자동 대체하지 않음

## 검증 결과

- Core 단위 테스트: PASS
- Customer 단위 테스트: PASS
- Customer Debug APK: PASS
- Technician Debug APK: PASS
- Customer 실단말 Compose UI 테스트: PASS (`SM-F721N`, `R3CT8076D7B`, 2/2)
- 실제 재검증 시각: `2026-08-04 10:10:55 +09:00`
- 실제 재검증 기준 Commit: `1474a36a1b4bc218842ba675c5f4ce7c95c796a6`

## 다음 Runtime 검증

1. PostgreSQL과 Django 실행
2. `adb reverse tcp:8000 tcp:8000`
3. Demo 고객 로그인
4. CUST-02에서 증상 입력 후 실제 문의 생성
5. Backend 응답의 문의번호·상태·버전·허용 행동 확인
6. 네트워크 실패 후 같은 입력 재시도로 Idempotency Replay 확인

## 제한사항

- 제품·구독 조회 Runtime Endpoint 대기
- AI 안내·Evidence Runtime Endpoint 대기
- 상담 요청 Runtime Endpoint 대기
- 위 기능은 실제 Endpoint가 제공되기 전까지 가짜 성공으로 처리하지 않음
## 검증 보정 이력

- 최초 `runComposeUiTest` 실행은 Compose Host가 생성되지 않아 `No compose hierarchies found` 오류로 2건이 실패했다.
- 이후 테스트 소스를 JUnit `createComposeRule` 구조로 변경했지만, 첫 검증 Script가 저장소 루트에서 Gradle을 실행하여 실제 테스트를 수행하지 못한 채 결과 문서를 잘못 갱신했다.
- `2026-08-04 10:10:55 +09:00`에 Gradle Project Directory를 `mobile`로 명시하고 실단말 테스트를 강제 재실행했다.
- `SM-F721N` 실단말에서 Compose UI 테스트 2건이 모두 통과했으며 Core·Customer 단위 테스트와 Customer·Technician Debug APK 빌드도 통과했다.
