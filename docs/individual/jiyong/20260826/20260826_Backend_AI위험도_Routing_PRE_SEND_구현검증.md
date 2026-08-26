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

## 5. DB·Migration 영향

- 신규 테이블·컬럼·인덱스: 없음
- 신규 Migration: 없음
- 기존 `Guidance.review_status_code`와 `Consultation`을 재사용
- `visits.0005`: 변경·적용하지 않음
- 팀 공용 DB·RDS·보존 Volume: 접근하지 않음

기존 DB에 남아 있는 과거 `PENDING` Guidance는 자동으로 승인 처리하지 않습니다.
잘못된 고객 노출보다 안전한 비공개를 우선하며, 필요하면 별도 승인된 Backfill 정책으로 처리해야 합니다.

## 6. 검증 결과

### 6.1 표적 검증

- Guidance Routing·AI 저장·고객 조회: `67 passed`
- danger 상담 대기 생성과 Replay 중복 방지: PASS
- caution PENDING 초안 고객 비노출: PASS

### 6.2 관련 상담·Handoff 회귀

- 상담사 API·AI Handoff·Inquiry 단위 범위: 고유 테스트 `242 passed`
- 테스트 임시 폴더 권한 충돌 5건은 정상 권한의 격리 경로에서 재실행해 모두 PASS

### 6.3 전체 Backend 회귀

- `1567 passed`
- `41 skipped`
- 실패: `0`

Skip은 PostgreSQL 전용 락·카탈로그 검증 또는 실제 AI Socket 환경값이 필요한 기존 조건입니다.
이번 변경은 스키마를 바꾸지 않으며 SQLite 테스트 DB에서 전체 회귀를 통과했습니다.

### 6.4 정적·구성 검사

- Django system check: PASS
- `makemigrations --check --dry-run`: `No changes detected`
- `pip check`: PASS
- `git diff --check`: PASS

## 7. 이번 단계에서 의도적으로 구현하지 않은 것

다음 항목은 Backend 코드를 임의로 우회하면 Actor·Audit 의미가 틀어지므로 보류했습니다.

1. 상담사 Pending Review 목록·상세·결정 API
2. `APPROVE_AI_GUIDANCE` 또는 `ESCALATE_TO_CONSULTANT` 상태 전이
3. 수정 승인과 AI Resume
4. 일반 MCP·Provider·Schema 실패용 신규 State Event
5. `danger + PARTIAL_STOP` 정책 변경

기존 `SAFE_GUIDANCE_READY`는 SYSTEM 이벤트이고 `REQUEST_CONSULTATION`은 CUSTOMER 이벤트입니다.
상담사 결정에 둘을 재사용하면 실제 실행자와 감사 기록이 달라집니다.

## 8. 다음 공동 작업의 선행 조건

1. 이동윤 작업자가 확정 AI 응답 필드와 Routing 결과를 main에 반영
2. 윤승혁(PM)이 상담사 검토용 additive Event와 Actor·전이 의미를 동결
3. 이후 Backend가 Review 결정 API, `select_for_update`, 멱등 Replay, 동시 결정 409를 구현
4. 한예나가 Pending Review Web 화면을 연결
5. 양정현이 고객의 검토 중·긴급 연결·일반 안내 상태를 연결
6. 김은진이 PostgreSQL 동시성·Replay·권한을 독립 검증

## 9. 결론

Backend 단독으로 안전하게 가능한 범위는 완료했습니다.

- 긴급 문의는 고객 동작 없이 Web 상담 대기열에 들어갈 DB 행을 만듭니다.
- 주의 AI 초안은 고객에게 먼저 보이지 않습니다.
- 일반 안내는 기존 공식 Evidence·안전 Gate를 계속 사용합니다.
- 공용 State Machine과 타 담당자 영역은 변경하지 않았습니다.

상담사의 실제 승인·상담 전환까지 포함한 HITL 완성 판정은 신규 공용 Event 계약 이후에만 가능합니다.
