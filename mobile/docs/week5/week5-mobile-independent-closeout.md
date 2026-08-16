# 5주차 모바일 독립 수행 범위 마감

양정현 5주차 업무 지침서 중 **백엔드 신규 Runtime 없이 모바일 담당자가 독자적으로 완료할 수 있는 범위**를 닫는다.

## 완료 범위

- 모바일 기준선 / Runtime 분류 / Remote-Fake 경계 문서화
- 실제 구독 목록/상세 및 실제 `subscription_id` 문의 진입
- 실제 문의 생성 / 증상 제출
- 실제 고객 문의 Snapshot / 미답변 Questions / 추가 문진 Answers
- 고객 추가 문진 3개 API 실단말 Remote Smoke PASS (skipped=0)
- 생성/제출 Idempotency 및 409 허용 재시도 단위 회귀
- Remote 구독 실패 → Fixture 성공 자동 대체 제거
- Guidance Runtime 없음 → fail-closed
- 방문기사 Remote Visit Runtime 없음 → fail-closed
- 오프라인 미리보기 Fixture 명시 분리
- WAITING_COMPLETION 오매핑 및 알 수 없는 레거시 상태 fail-closed 테스트
- 고객 / 방문기사 연결 테스트
- 단위 테스트 / Debug APK / AndroidTest APK / 실단말 검증
- README 현행화
- Runtime 대응표 현행화
- 6주차 모바일 인계 문서
- 추적 중인 local.properties / 흔한 secret / 개인 IP 정적 검사

## 2026-08-15 Mobile 고객 최신 진행 문의 복구 조회 연동

- `GET /api/v1/me/inquiries/active` Remote 연동 완료
- `active_inquiry` null/non-null 응답을 서버 Snapshot 그대로 매핑
- 동일 `inquiry_id` 복구 및 `COMPLETION_PENDING`, `state_version` 보존
- Remote 조회 실패 시 Fake/Fixture 성공 자동 대체 없음
- Core / Customer Unit Test 및 Customer Debug Build PASS
- 전체 실제 기기 E2E Smoke는 Backend 테스트 계정·신규 Inquiry 인계 후 수행
## 백엔드 없이는 완료할 수 없는 항목

- CUSTOMER_GUIDANCE_EVIDENCE_RUNTIME
- CUSTOMER_REQUEST_CONSULTATION_RUNTIME
- TECHNICIAN_ASSIGNED_VISIT_LIST_DETAIL_RUNTIME
- TECHNICIAN_VISIT_START_COMPLETE_RUNTIME
- FULL_CUSTOMER_AI_CONSULTATION_VISIT_TECHNICIAN_E2E

## 조건 미충족으로 착수하지 않는 후행 업무

- 전체 대표 E2E
- E2E 이후 공통 상태 UI 대규모 공통화
- 전체 실제 API 흐름 이후 Token/Refresh 추가 고도화
- E2E 이후 접근성/사용성 최종 마감

```text
MOBILE_INDEPENDENT_ACTIONABLE_ITEMS = COMPLETE
INDEPENDENT_MOBILE_WEEK5 = PASS
FULL_P0_FEATURE_COMPLETE = BLOCKED_BY_BACKEND
```
