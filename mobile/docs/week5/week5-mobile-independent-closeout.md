# Week5 Mobile Independent Closeout

양정현 5주차 업무 지침서 중 **Backend 신규 Runtime 없이 Mobile 담당자가 독자적으로 완료할 수 있는 범위**를 닫는다.

## 완료 범위

- Mobile 기준선 / Runtime 분류 / Remote-Fake 경계 문서화
- 실제 Subscription list/detail 및 실제 `subscription_id` 문의 진입
- 실제 Inquiry create / symptom submit
- Create/Submit Idempotency 및 409 허용 재시도 단위 회귀
- Remote Subscription 실패 → Fixture 성공 자동 fallback 제거
- Guidance Runtime 없음 → fail-closed
- Technician Remote Visit Runtime 없음 → fail-closed
- Offline Preview Fixture 명시 분리
- WAITING_COMPLETION 오매핑 및 unknown legacy 상태 fail-closed 테스트
- Customer / Technician Connected Test
- Unit / Debug APK / AndroidTest APK / 실단말 Gate
- README 현행화
- Runtime Matrix 현행화
- 6주차 Mobile 인계 문서
- tracked local.properties / 흔한 secret / 개인 IP 정적 검사

## Backend 없이는 완료할 수 없는 항목

- CUSTOMER_FOLLOWUP_RUNTIME
- CUSTOMER_GUIDANCE_EVIDENCE_RUNTIME
- CUSTOMER_REQUEST_CONSULTATION_RUNTIME
- TECHNICIAN_ASSIGNED_VISIT_LIST_DETAIL_RUNTIME
- TECHNICIAN_VISIT_START_COMPLETE_RUNTIME
- FULL_CUSTOMER_AI_CONSULTATION_VISIT_TECHNICIAN_E2E

## 조건 미충족으로 착수하지 않는 후행 업무

- Full 대표 E2E
- E2E 이후 공통 상태 UI 대규모 공통화
- 전체 실제 API 흐름 이후 Token/Refresh 추가 고도화
- E2E 이후 접근성/사용성 최종 마감

```text
MOBILE_INDEPENDENT_ACTIONABLE_ITEMS = COMPLETE
INDEPENDENT_MOBILE_WEEK5 = PASS
FULL_P0_FEATURE_COMPLETE = BLOCKED_BY_BACKEND
```
