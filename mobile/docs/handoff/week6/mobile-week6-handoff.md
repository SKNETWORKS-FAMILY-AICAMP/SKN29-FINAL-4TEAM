# Mobile Week6 Handoff

## 5주차 고정 기준

Customer:

```text
실제 인증
→ 실제 구독 목록/상세
→ 실제 subscription_id 선택
→ 실제 문의 생성
→ 실제 증상 제출
```

Technician:

```text
실제 인증
→ Visit Runtime 미제공 시 fail-closed
→ 명시적 Offline Preview에서만 synthetic Fixture
```

## Backend Runtime 개방 즉시 연결 순서

1. Customer Follow-up
2. Customer Guidance / Evidence
3. Customer Request Consultation
4. Technician assigned Visit list/detail
5. Technician Visit start/complete/result
6. Full Customer → AI → Consultation → Visit → Technician E2E

## 6주차 Mobile 허용 범위

- 잔여 UI/UX 버그
- 배포 Backend Base URL 반영
- 접근성 / 긴 문구 / Touch target 마감
- 성능·안정성
- Release APK 또는 시연 APK 검증
- 문서·스크린샷·발표 지원

## 금지

- Mobile 전용 가짜 Endpoint 생성
- Remote 실패 시 Fixture 자동 대체
- Visit 상태 임의 생성
- `WAITING_COMPLETION`을 `COMPLETED`로 처리
- AI FastAPI / LLM / Vector DB 직접 호출
- 실제 Token / Secret / 개인정보 로그 출력
- E2E 통과를 위한 DB 직접 수정

```text
MOBILE_INDEPENDENT_ACTIONABLE_ITEMS = COMPLETE
INDEPENDENT_MOBILE_WEEK5 = PASS
FULL_P0_FEATURE_COMPLETE = BLOCKED_BY_BACKEND
```
