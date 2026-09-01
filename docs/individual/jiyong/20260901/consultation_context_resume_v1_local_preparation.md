# 맥락 Agent HumanReview 재개 v1 로컬 준비 결과

## 판정

- 기준선: `origin/main@9f2d74897a8514ae396e4f83cc4e0186a67fe9eb`
- 작업 위치: 격리 Worktree `context-agent-resume-v1-20260901`
- 로컬 구현 판정: PASS
- AWS·RDS·외부 Provider·실제 Handoff: 미호출·미변경
- 운영 활성화: HOLD

## 고정 호출 계약

- 최초 분석 및 검토 대기: 맥락 Agent 0회, 맥락 Provider 0회, Handoff 0건
- Backend 공식 `REJECT` 확정 이후: 맥락 Agent 1회, Provider 최대 1회, Handoff 최대 1건
- 같은 공식 결정 Replay: Backend 재개 Dispatch 추가 0건
- 네트워크 호출을 시작한 Dispatch: 성공 여부가 불명확해도 자동 재전송 0회
- 상태 버전·AI 요청·문의·검토·Checkpoint·원인 Ledger 불일치: Fail-closed

## Backend 구현

- 공식 거절 트랜잭션 안에서 재개 Outbox를 1건만 저장
- 트랜잭션 Commit 이후에만 AI 보호 Endpoint 호출
- Commit 직후 프로세스가 종료돼도 `PENDING` Outbox를 로컬 Worker로 복구 가능
- Outbox가 네트워크 호출을 시작하면 최대 시도 횟수를 1회로 고정
- Timeout·전송 오류는 `OUTCOME_UNKNOWN`으로 기록하고 자동 재시도 금지
- 호출 전 결속 실패는 `FAILED_PRE_SEND`로 기록하며 Provider 호출 없음
- 분석 결과와 `ConsultationCauseLedger` 식별자·SHA-256 재검증
- `official_verified` Evidence와 Guidance·Crosswalk 결속 재검증
- 보호토큰은 AI→Backend Handoff 토큰과 분리하고 32-byte 이상만 허용
- 실패 코드와 비식별 실행 영수증만 저장하며 고객 원문·Prompt·Secret은 저장하지 않음
- Outbox `SUCCEEDED`는 HTTP 재개 영수증 수신을 뜻하며 Provider 성공은 별도 `context_synthesis_status=SUCCEEDED`, `fallback_reason=null`로 판정

## AI 구현

- 보호형 `HumanReview Resume` 내부 HTTP Endpoint 추가
- Backend 식별자·상태 버전·공식 Evidence·Checkpoint 결속 검증
- 메모리 Checkpoint 대신 Backend에 저장된 검증 분석 결과로 상태 재구성
- 기존 맥락 Agent와 Handoff 생성 경로를 공식 거절 뒤에만 실행
- 동일 AI 프로세스의 같은 요청은 결과를 재사용하고 변경 Payload는 충돌 처리
- JAC104만 Runtime 승인 유지
- IAC425·IAC606은 Runner 생성 전 Fail-closed 유지

## 로컬 Migration

- `inquiries.0018_humanreviewresumedispatch` 후보 추가
- `0017_consultationcauseledger` 다음 번호로 연결
- Outbox에 데이터가 남은 상태의 역 Migration은 차단
- 로컬 SQLite에서 `0018 적용 → 0017 롤백 → 0018 재적용` PASS
- NONPROD 및 Production RDS에는 적용하지 않음

## 검증 결과

- AI 맥락 Agent·HITL·Handoff 관련: `206 passed`
- Backend HumanReview·Envelope·Handoff 관련: `111 passed, 2 skipped`
- 제외 2건: 기존 PostgreSQL 행 잠금 전용 증거 테스트
- Django System Check: PASS
- Migration drift: 없음
- Python compile 및 Git diff whitespace 검사: PASS
- 테스트는 Fake Provider·Mock HTTP만 사용했으며 외부 Provider 호출 없음

## 기본 비활성 설정

- Backend와 AI: `AI_HUMAN_REVIEW_RESUME_ENABLED=false`
- AI→Backend 자동 Handoff: `AI_HANDOFF_BACKEND_ENABLED=false`
- Kill switch가 꺼져 있으면 기존 `PENDING` Outbox도 전송하지 않음

## 남은 HOLD

- AI 분석 API는 현재 내부 Envelope `1.0.0`이 아니라 기존 분석 응답을 반환함
- 따라서 실제 Runtime에서 `ConsultationCauseLedger`가 생성되는 연결은 이동윤 AI 범위 검수·구현 필요
- AI 프로세스가 직접 받은 요청의 영수증을 자체 영구 저장하지는 않음
- Backend Outbox가 동일 공식 결정을 한 번만 보내는 방식으로 자동 중복 호출을 차단함
- 실제 Provider, 실제 Handoff, NONPROD 결합 E2E, 운영 활성화는 별도 QA·PM 승인 필요

## 다음 인계

1. 이동윤: AI Envelope 실제 Runtime 반환과 맥락 Agent 재개 계약 검수
2. 최지용: Backend Outbox·Migration `0018` 독립 QA 요청
3. 양측 PASS 후 JAC104 한정 NONPROD 자동 재개 E2E
4. IAC425·IAC606, Provider·Handoff 운영 활성화는 계속 HOLD
