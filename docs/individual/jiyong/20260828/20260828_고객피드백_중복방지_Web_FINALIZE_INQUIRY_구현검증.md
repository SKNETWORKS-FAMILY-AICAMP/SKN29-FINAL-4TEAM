# 고객 피드백 중복 방지·Web 문의 최종 완료 구현 검증

- 작성일: 2026-08-28
- 담당: 최지용(Backend·DB), Web 임시 승인 범위
- 기준 main: `ca1ec8f858590b776746d7dceeab4e90c9abbb50`
- Backend·계약 Commit: `9651a1db`
- Web Commit: `1f4c9e54`

## 1. 결론

고객이 `해결됐어요`를 정상 제출한 뒤 같은 문의에서 해결 응답과 상담 요청을
반복 저장할 수 있던 경계를 Backend에서 차단했다.

상담사 Web에는 Backend가 제공하는 `FINALIZE_INQUIRY`를 실제 최종 완료 API에
연결했다. 고객의 긍정 피드백 이후 문의는 바로 닫지 않고 기존
`COMPLETION_PENDING`을 유지하며, 마지막 처리 상담사·기사가 최종 완료한다.

이번 변경은 기존 테이블과 `FollowupConfirmation` 원장을 사용하므로 신규 Model,
Migration, Seed 또는 DB 수동 변경이 없다.

## 2. 확정 동작

| 상황 | 결과 |
|---|---|
| 첫 `resolved=true` 제출 | HTTP 200, 원장 1건 저장 |
| 같은 Idempotency Key·같은 Payload 재전송 | 기존 성공 응답 Replay |
| 새 Key로 긍정 피드백 재전송 | HTTP 409 `STATE-CONFLICT-01` |
| 긍정 피드백 뒤 상담 재요청 | HTTP 409 `STATE-CONFLICT-01` |
| 고객 Snapshot 재조회 | `CUSTOMER_REPORTED_UNRESOLVED`만 제공 |
| 고객이 미해결로 판단 | 기존 미해결·재상담 경로 유지 |
| 마지막 처리 상담사·기사의 최종 완료 | 기존 `FINALIZE_INQUIRY`로 `RESOLVED` 전이 |

중복 방지는 단순 화면 숨김이 아니다. Backend가 Inquiry 행을 잠근 상태에서 기존
해결 원장을 다시 확인하므로, 두 요청이 동시에 들어와도 한 건만 저장된다.

## 3. Backend·DB 구현

1. State Machine에 `G-NO-FRESH-RESOLVED-CUSTOMER-FEEDBACK` Guard를 추가했다.
2. `SUBMIT_RESOLUTION_FEEDBACK`과 `REQUEST_CONSULTATION`에 Guard를 적용했다.
3. 멱등 Replay를 Guard보다 먼저 판정해 정상 Replay 계약을 보존했다.
4. 새로운 Key의 중복 요청은 현재 상태·버전·허용 액션을 담은 409로 닫았다.
5. 고객 읽기 API는 완료 상담·방문·해결 피드백을 Subquery로 함께 읽어 기존
   쿼리 수를 늘리지 않고 최신 허용 액션을 계산한다.
6. PostgreSQL 동시 요청은 Inquiry 행 잠금으로 한 요청만 원장에 기록한다.

## 4. Web 구현

1. Remote 상담 액션 허용 목록에 `FINALIZE_INQUIRY`를 포함했다.
2. 아래 기존 Backend API를 Web Repository에 연결했다.

```http
POST /api/v1/inquiries/{inquiry_id}/finalize
Idempotency-Key: {request_key}
X-Correlation-ID: {correlation_id}

{
  "state_version": 8
}
```

3. 성공 응답의 `status`, `state_version`, `allowed_actions`로 화면 상태를 교체한다.
4. 확인창은 Hook 한 곳에서 한 번만 처리해 이중 팝업을 만들지 않는다.
5. 한예나님의 최신 단계형 상담 화면과 폼 검증 로직은 그대로 유지했다.

## 5. 변경하지 않은 범위

- `mobile/**`, `ai/**`, Data·Migration·Seed
- AWS RDS 데이터와 운영 상태
- 고객 공개 상담 결과 필드와 기존 미해결 흐름
- 기존 Idempotency·Correlation·권한·상태 버전 계약

Mobile 화면 갱신은 양정현 담당 변경이며 이번 Commit에 포함하지 않는다.

## 6. 검증 결과

### Backend·DB

- 고객 조회·피드백·상담 요청·Resolver 표적: `100 passed, 3 skipped`
  - Skip 3건은 SQLite에서 분리한 PostgreSQL 행 잠금 전용 Case다.
- 볼륨 없는 격리 PostgreSQL 16/pgvector 표적: `17 passed`
  - 서로 다른 Key의 동시 긍정 피드백: 200 한 건, 409 한 건
  - Followup·Idempotency 원장: 각 1건
- Contract Validator 5종: 모두 PASS
  - State Machine 13상태·33이벤트·37전이·43 Guard
  - OpenAPI 55 Path·60 Operation
  - Example 73건, Crosswalk 24 Action, Code 150건
- Python Compile: PASS
- Backend 전체 회귀: `1631 passed, 45 skipped`
  - Skip은 PostgreSQL 전용·외부 Socket 조건부 Case다.

### Web

- 표적 Vitest: `20 passed`
- 전체 Vitest 단일 Worker: `52 files passed`, `298 passed, 4 skipped`
- Lint: PASS
- TypeCheck: PASS
- E2E TypeCheck: PASS
- Production Build: PASS, 145 Module

## 7. DB 안전 증거

- 공용 DB·RDS·기존 보존 Volume에 쓰지 않았다.
- 검증 컨테이너는 고유 이름·고유 포트·Volume 없음으로 실행했다.
- 검증 후 임시 컨테이너는 종료되어 자동 삭제됐다.
- 기존 `waterbridge-ai-context-local-postgres`와
  `waterbridge-p1-team-isolated-postgres`는 그대로 유지됨을 확인했다.

## 8. 후속 통합 순서

1. PM이 Backend·Web Commit을 main에 병합한다.
2. 양정현이 최신 main에서 Mobile 상태 갱신·대기 화면을 연결한다.
3. 한예나는 Web Diff와 실제 `FINALIZE_INQUIRY` Browser 동작을 사후 확인한다.
4. 최지용은 배포 후 동일 AWS Inquiry로 API·상태 전이·RDS 원장을 대조한다.
5. 김은진은 중복·동시성·Replay·권한·409를 독립 검증한다.

이 문서는 로컬 코드·계약·격리 PostgreSQL 검증 완료 증거다. main 병합, AWS 배포,
실제 Mobile·Web E2E와 독립 QA 완료를 대신하지 않는다.
