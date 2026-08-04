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
- Customer 실단말 Compose UI 테스트: PASS

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