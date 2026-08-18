# 고객 문의·문진·상담 요청 API 구현 가이드

> 관련 업무: T-022 고객 문의 생성·증상 제출·추가답변·자가조치 결과·상담 요청
>
> 최신 반영일: 2026-08-17

## 1. Runtime 흐름

```text
문의 생성
→ 최초 증상 제출
→ 필요한 경우 추가 질문 조회·답변
→ AI 결과 또는 Fail-closed 상태 반영
→ 고객 자가조치 결과 누적
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
- 자가조치 결과는 기존 GuidanceItem 아래에 Attempt 순서대로 누적한다.
- 의미가 확정되지 않은 `result_code`는 Backend가 임의로 해석하지 않는다.

## 4. 추가문진

답변은 `ANSWERED`, `REFUSED`, `UNKNOWN`을 명시적으로 구분하고 질문 ID와
현재 `state_version`을 검증한다. 중복 답변·stale 요청·타 고객 접근을
차단하며 최신 Snapshot을 반환한다.

## 5. 자가조치 결과

`POST /api/v1/inquiries/{id}/action-results`는 고객 본인의 `AI_GUIDANCE`
문의에만 결과를 추가한다. `Idempotency-Key`와 현재 `state_version`이
필수이며, GuidanceItem이 같은 문의에 속하는지 확인한다.

- 요청: `guidance_item_id`, `result_code`, `state_version`과 선택 원문 필드
- 성공: 201, ActionResult와 증가한 `state_version` 반환
- 동일 Key·동일 Payload: 최초 201 응답 Replay, 추가 저장 없음
- 동일 Key·다른 Payload: 409
- stale version·잘못된 상태: 409
- 타 고객·타 문의 GuidanceItem: 404
- 상태 코드는 유지하고 Aggregate version만 증가하며 전이 이력은 만들지 않는다.
- 응답 직렬화까지 한 Transaction으로 묶어 실패 시 전부 Rollback한다.

`NOT_PERFORMED` 외 코드의 공식 의미는 아직 확정하지 않았다. 따라서
Serializer는 비어 있지 않은 40자 이하 코드만 보존하고, 정책 판단이나
후속 상태 전이를 추가하지 않는다.

## 6. 상담 요청

상담 필요 상태에서 고객 Action으로 요청한다. Timeout이나 AI 결과만으로
Consultation 행을 자동 생성하지 않는다. Consultation 생성 책임은 승인된
`REQUEST_CONSULTATION` 흐름에 둔다.

## 7. 검증 Matrix

| Case | 기대 결과 |
| --- | --- |
| 정상 신규 제출 | 저장·상태·이력 1회 |
| Replay | 추가 저장·AI 호출 0 |
| Payload 충돌 | 409 |
| 타 고객 | 404 또는 계약상 거부 |
| 잘못된 제품 | AI 호출 0, Fail-closed 전이 |
| AI 오류·Timeout | 입력·상태 보존 |
| 저장 실패 | 업무·이력·멱등 전체 Rollback |
| 자가조치 정상 | 결과 1회 누적·version +1·상태 유지 |
| 자가조치 Replay | 결과·version·멱등 원장 추가 없음 |
| 타 문의 GuidanceItem | 404·부수효과 없음 |
| 응답 계약 실패 | 결과·version·멱등 원장 Rollback |

## 8. 2026-08-17 자체 검증

- T-022 전체 표적 회귀: `125 passed / 2 skipped / 0 failed`
- Skip 2건: PostgreSQL 전용 Row-lock 검증이며 기존 조건부 Skip 유지
- Action Result·Readiness 표적: `46 passed / 0 failed`
- Django system check: 문제 없음
- Migration drift: `No changes detected`
- OpenAPI: 126 YAML, 539 refs, 38 paths, 42 operations 통과
- Contract Crosswalk: Runtime 13건 포함 검증 통과

## 9. 판정

고객 입력 보존, 권한, 상태·멱등·동시성, AI 호출 경계와 상담 요청 Runtime이
통과하면 Backend 구현 완료다. 실제 AI Provider E2E는 별도 통합 Gate다.

T-022 Action Result Backend Runtime은 구현·자체 검증 완료다. 다만 공식
`result_code` 의미 승인, Mobile Adapter 연결, PostgreSQL 독립 QA는 외부
Gate이므로 이 문서만으로 T-022 전체 WBS 완료를 선언하지 않는다.
