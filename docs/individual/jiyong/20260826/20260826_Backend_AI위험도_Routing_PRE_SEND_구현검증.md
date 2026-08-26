# Backend AI 위험도 Routing·PRE_SEND 구현 검증

- 작성일: 2026-08-26
- 담당: 최지용 (Backend·DB)
- 기준선: `origin/main@139a4082d2c6148164387d41eb6b5d66d43fef00`
- 작업 브랜치: `codex/jiyong-hitl-backend-20260826`
- 판정: `BACKEND_SAFE_SLICE_PASS / HUMAN_REVIEW_DECISION_API_PENDING`

## 1. 목적

AI가 분류한 `danger / caution / general` 결과를 Backend가 그대로 공개하지 않고,
기존 안전·Evidence Gate와 검토 상태를 함께 확인하도록 최소 범위를 구현했습니다.

이번 변경은 다음 두 문제를 우선 닫습니다.

1. `danger` 문의가 `CONSULTATION_REQUIRED` 상태만 되고 실제 상담 대기열에는 나타나지 않던 문제
2. `caution` AI 초안이 상담사 검토 전에 고객 Guidance API로 노출될 수 있던 문제

## 2. 안전한 작업 경계

수정 범위는 `backend/**`, `backend/tests/**`, `docs/individual/jiyong/**`로 제한했습니다.

다음 영역은 수정하지 않았습니다.

- `ai/**`
- `web/**`
- `mobile/**`
- `data/**`
- `.github/**`
- `contracts/state-machine/**`
- 기존 Migration
- 다른 작업자의 개인 문서

원래 `jiyong` 작업트리에 있던 수정·미추적 문서는 별도 Worktree로 격리해 그대로 보존했습니다.

## 3. 적용한 Backend 정책

| AI 결과 | 최초 Guidance 검토 상태 | 고객 공개 | Backend 처리 |
|---|---|---|---|
| `general` | `CONFIRMED` | 기존 공식 Evidence·안전 Gate까지 통과한 경우만 허용 | 기존 `SAFE_GUIDANCE_READY` 유지 |
| `danger` | `CONFIRMED` | 기존 danger 검증을 통과한 안전 안내만 허용 | 기존 `DANGER_DETECTED`와 같은 Transaction에서 상담 대기 1건 생성 |
| `caution` | `PENDING` | 금지, `409 AI_GUIDANCE_NOT_READY` | 상담사 PRE_SEND 검토 대기 |
| Fallback·근거 없음 | `REJECTED` | 금지 | 기존 Fail-closed 상태 전이 유지 |
| 알 수 없는 위험도 | `REJECTED` | 금지 | 공개하지 않음 |

`CONFIRMED`는 상담사의 수동 승인이 아니라 기존 Backend 안전·계약 검증을 통과했다는 뜻입니다.
향후 상담사가 직접 승인한 결과에는 `APPROVED`를 사용합니다.

## 4. 구현 내용

### 4.1 Guidance 초기 검토 상태 분류

`GuidanceReviewPolicy`를 추가해 AI 결과의 최초 검토 상태를 한 곳에서 결정합니다.

- Fallback 또는 근거 없음은 항상 `REJECTED`
- `caution`은 `PENDING`
- `general`, 검증된 `danger`는 `CONFIRMED`
- 계약 밖 값은 `REJECTED`

### 4.2 고객의 미검토 초안 조회 차단

고객 Guidance 조회는 `APPROVED` 또는 `CONFIRMED`만 대상으로 읽습니다.

Repository 필터와 Service 재검사를 함께 적용했으므로, 다른 조회 코드가 잘못 변경되더라도
`PENDING / REJECTED` 원문은 고객 응답에 포함되지 않습니다.

### 4.3 danger 자동 상담 대기열

`DANGER_DETECTED` 상태 전이가 성공한 경우 동일 DB Transaction 안에서
미배정 `Consultation(status=WAITING)`을 생성합니다.

- 고객의 별도 상담 요청 버튼을 기다리지 않음
- `state_version`과 `correlation_id`를 Inquiry 전이와 일치시킴
- 기존 WAITING·ASSIGNED 상담이 있으면 중복 생성하지 않음
- 동일 AI 결과 Replay에서도 Consultation은 1건 유지

## 5. 2026-08-26 Safety 후속 정합화

- 온수 히터 Rule의 적용 범위를 `RUNTIME_APPROVED_PRODUCTS`로 명시했습니다.
- "온수 히터 고장은 아닙니다" 같은 명시적 부정문은 히터 고장으로 탐지하지 않습니다.
- 부정문 뒤에 실제 누수·증기·점화 위험 문장이 있으면 해당 위험 Rule은 계속 탐지합니다.
- 기존 danger `TOTAL_STOP`, 복합 Rule 우선순위, 일반 안내 동작은 바꾸지 않았습니다.
- 정책 확장은 `OWNER_PROPOSED_PM_MERGE_REQUIRED`로 표시해 PM 병합 전 확정으로 과장하지 않습니다.

## 6. HITL Backend·DB 구현

### 6.1 상태와 저장 경계

`HumanReview`는 Inquiry 상태를 재사용하지 않는 별도 원장입니다.

- `PENDING`: 상담사 결정 대기
- `APPROVED`: AI 초안을 그대로 승인
- `MODIFIED`: 상담사가 안전 문구를 수정해 새 Guidance 버전 발행
- `REJECTED`: 초안을 고객에게 공개하지 않고 반려
- `RESUME_FAILED`: 결정 후 AI Resume 실패를 제한된 사유 코드로 기록

원장에는 원문 Prompt·고객 증상 원문·전화·주소·계약번호·내부 오류 원문을 저장하지 않습니다.
Inquiry의 `status_code`와 `state_version`도 HITL 결정 때문에 임의로 바꾸지 않습니다.

### 6.2 상담사 Runtime

- `GET /api/v1/inquiries/human-reviews`: 본인 배정 또는 미배정 합성 Review 목록
- `GET /api/v1/inquiries/human-reviews/{review_id}`: 최소 안전 Projection 상세
- `POST /api/v1/inquiries/human-reviews/{review_id}/decision`: 승인·수정·반려

결정은 상담사 권한, `Idempotency-Key`, `X-Correlation-ID`, Review 버전을 요구합니다.
행잠금과 멱등 원장을 같은 Transaction에서 사용하므로 동시 결정은 한 건만 성공하고
나머지는 409가 됩니다. 동일 Key·동일 Payload는 저장 없이 Replay하고, 다른 Payload는
`DUPLICATE-EVENT-01`로 차단합니다.

공용 DTO·소비 연결 승인이 아직 없으므로 세 API는 Public OpenAPI에서 제외했습니다.
Web·Mobile이 임의 연결할 수 있다는 뜻이 아니며 PM 계약 동결 뒤 별도 공개해야 합니다.

## 7. DB·Migration 영향

- 신규 테이블: `support_human_review`
- 신규 Migration: `inquiries.0015_humanreview`
- Allowlist: Inquiries Leaf를 0015로 갱신
- T-005: 불변 32개 도메인 계약 밖 승인 Runtime 지원 테이블로 별도 등록
- `visits.0005`: 계속 미적용 P1 HOLD
- 기존 Migration·공용 State Machine·Data 파일: 수정하지 않음

## 8. 작성자 검증

| 범위 | 결과 |
| --- | --- |
| AI Safety 표적 | 53 passed |
| Backend Safety Registry | 10 passed |
| HumanReview API·권한·Replay·제약 | 9 passed |
| T-005 구현준비도·Schema 회귀 | 43 passed |
| AI 회귀(A2A·실환경 Vector Gate 제외) | 585 passed, 13 skipped, 37 subtests passed |
| Backend 전체 회귀 | 1588 passed, 41 skipped, 0 failed |
| Django Check·Migration Drift | PASS / No changes detected |

격리 PostgreSQL 16.14·pgvector 0.8.6에서는 승인 Target 18개와 의존 Closure 98개만
적용했습니다. `inquiries.0015=APPLIED`, `visits.0005=NOT_APPLIED`를 확인했고,
동시 결정은 `1x200 + 1x409`, Replay 추가 멱등 행은 0건이었습니다.

AI 전체 수집은 현재 가상환경의 A2A 패키지 미설치로 별도 차단됐습니다. 또한 실제 AI
Vector Gate는 보호된 `AI_VECTOR_DSN`이 필요한 실환경 검증이므로 위 585건에 포함하지
않았습니다. 이를 PASS로 확대하지 않습니다.

## 9. 아직 완료로 판정하지 않는 범위

1. 이동윤: 영속 Checkpointer와 실제 HTTP Resume·재시작 복구
2. 윤승혁(PM): Public HITL API·DTO·소비 연결 및 Event 의미 승인
3. 한예나·양정현: 승인 후 Web·Mobile 화면 연결
4. 김은진: PostgreSQL 권한·동시성·Replay·민감정보 독립 QA
5. RDS: 최종 main 기준 Plan·PM 승인·Migrator 적용

따라서 이번 결과는 `Backend_DB_LOCAL_IMPLEMENTED`입니다. 전체 HITL E2E, 독립 QA,
PM WBS 완료 또는 RDS 적용 완료를 의미하지 않습니다.
