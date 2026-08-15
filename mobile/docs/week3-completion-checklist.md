# 3주차 모바일 완료 체크리스트

## 소스 구현

- [x] 3개 모듈 패키지 구조와 실행 가능한 Activity
- [x] CUST-01, CUST-02, CUST-04 화면 이동
- [x] CUST-02 검증, 입력 Snapshot, 중복 제출 차단, 실패 시 입력 유지
- [x] ViewModel 및 StateFlow 기반 화면 상태
- [x] Kotlinx Serialization 요청·응답 모델
- [x] Retrofit, OkHttp, Correlation ID, Bearer 인증 및 1회 Token 갱신
- [x] Repository 교체 지점과 명시적으로 구분된 Fake 구현
- [x] 일반·주의·위험·근거 없음·AI 실패·네트워크 실패 시나리오
- [x] 위험·근거 없음 상태에서 해결 완료 및 종료 동작 차단
- [x] 내부 RAG 필드를 노출하지 않는 근거 UI
- [x] 409 최신 상태 UiState를 포함한 400/401/403/404/409/5xx 안전 매핑
- [x] 시간대 중복 추가 없이 `+09:00` 표시 형식 적용
- [x] 단위 및 Compose 테스트 소스
- [x] README, 결정사항, 필드 대응표, 테스트 결과, 미해결 항목 문서
- [x] 통합 백엔드 데모 seed 명령
- [x] 한 번에 실행하는 백엔드 시작 및 최종 검증 스크립트

## 개발 PC 실행 근거

한 창에서 `START_WEEK3_BACKEND.cmd`를 실행하고 다른 창에서 `FINALIZE_WEEK3.cmd`를 실행합니다. 성공하면 `mobile/docs/week3-local-verification.txt`와 두 Debug APK가 생성됩니다. 이후 실제 기기에서는 `INSTALL_WEEK3_APPS.cmd`를 실행합니다.

이렇게 분리하면 실행하지 않은 결과를 성공으로 기록하는 일을 방지할 수 있습니다. 소스 구현 완료 여부는 이 문서에 기록하고, 개발 PC별 Android SDK, Gradle, Docker, 기기 실행 결과는 생성된 로컬 검증 로그에 기록합니다.
