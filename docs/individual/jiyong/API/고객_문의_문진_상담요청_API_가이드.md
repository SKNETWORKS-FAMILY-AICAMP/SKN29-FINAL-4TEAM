# 고객 문의·문진·상담 요청 API 구현 가이드

> 관련 업무: 고객 문의 생성·증상 제출·추가답변·상담 요청

## 1. Runtime 흐름

```text
문의 생성
→ 최초 증상 제출
→ 필요한 경우 추가 질문 조회·답변
→ AI 결과 또는 Fail-closed 상태 반영
→ 고객이 상담 요청
```

## 2. 주요 경로

- `backend/apps/inquiries/api/**`
- `backend/apps/inquiries/services/**`
- `backend/apps/inquiries/repositories/**`
- `contracts/api/paths/inquiries.yaml`
- `backend/tests/api/test_t022_*`

## 3. 저장 원칙

- 고객 본인과 활성 구독·지원 제품을 확인한다.
- 상태 전이·증상·History·멱등 원장을 한 Transaction으로 저장한다.
- 신규 제출 Commit 이후에만 AI를 호출한다.
- Replay는 최초 저장 응답을 유지하고 AI를 다시 호출하지 않는다.
- 같은 Key의 다른 Payload는 409로 거부한다.
- AI 실패·Timeout에도 이미 Commit된 고객 입력과 상태는 보존한다.

## 4. 추가문진

답변은 `ANSWERED`, `REFUSED`, `UNKNOWN`을 명시적으로 구분하고 질문 ID와
현재 `state_version`을 검증한다. 중복 답변·stale 요청·타 고객 접근을
차단하며 최신 Snapshot을 반환한다.

## 5. 상담 요청

상담 필요 상태에서 고객 Action으로 요청한다. Timeout이나 AI 결과만으로
Consultation 행을 자동 생성하지 않는다. Consultation 생성 책임은 승인된
`REQUEST_CONSULTATION` 흐름에 둔다.

## 6. 검증 Matrix

| Case | 기대 결과 |
| --- | --- |
| 정상 신규 제출 | 저장·상태·이력 1회 |
| Replay | 추가 저장·AI 호출 0 |
| Payload 충돌 | 409 |
| 타 고객 | 404 또는 계약상 거부 |
| 잘못된 제품 | AI 호출 0, Fail-closed 전이 |
| AI 오류·Timeout | 입력·상태 보존 |
| 저장 실패 | 업무·이력·멱등 전체 Rollback |

## 7. 판정

고객 입력 보존, 권한, 상태·멱등·동시성, AI 호출 경계와 상담 요청 Runtime이
통과하면 Backend 구현 완료다. 실제 AI Provider E2E는 별도 통합 Gate다.
