# 백엔드·AI 호출·추적·오류 처리 가이드

> 관련 업무: 문의 AI 분석 Wiring·Runtime Trace
> 시스템 경계: Backend가 상태와 저장을 소유하고 AI는 분석 결과를 반환한다.

## 1. 호출 흐름

```text
고객 요청
→ Backend 업무 Transaction Commit
→ transaction.on_commit Callback
→ FastAPI /api/v1/ai/analyze
→ 계약 검증
→ AIRun·Assessment·Guidance 저장
→ Backend State Event 재검증·적용
```

## 2. 주요 경로

- `backend/apps/inquiries/services/inquiry_transition_service.py`
- `backend/apps/inquiries/services/followup_answer_service.py`
- `backend/apps/inquiries/services/inquiry_ai_service.py`
- `backend/integrations/ai/**`
- `backend/common/logging/**`
- `contracts/ai/**`
- `backend/tests/unit/ai_integration/**`
- `backend/tests/integration/test_backend_ai_submit_symptom_live_http.py`

## 3. Transaction·멱등 경계

- 고객 입력과 State를 먼저 Commit한다.
- 신규 제출만 AI를 1회 호출한다.
- 동일 Idempotency-Key Replay는 AI 추가 호출 0회다.
- 같은 Key의 다른 Payload는 AI 호출 전 409다.
- Callback 실패는 이미 Commit된 고객 입력을 Rollback하지 않는다.
- Backend 자동 재시도는 하지 않고 AIRun 상태와 오류 분류를 기록한다.

## 4. Correlation

고객 요청, Backend Context, AI Header·Body, AIRun, State History가 동일한
Canonical UUID를 사용한다. 외부에서 주입된 임의 문자열은 UUID 검증 후 사용한다.

## 5. 오류 처리

| 오류 | Backend 처리 |
| --- | --- |
| AI 503 | AIRun `FAILED`, 업무 Commit 보존 |
| Timeout | AIRun `TIMED_OUT`, 재시도 0 |
| Schema 오류 | Fail-closed, 결과 미적용 |
| Stale Version | 최신 Snapshot 기준 Event 보류 |
| NO_EVIDENCE | 안전한 Fallback, 내부 근거 비노출 |
| DANGER | Safety Rule·Guard 검증 후 전이 |

예상 밖 Callback 예외는 안전한 오류 코드만 구조화 로그에 남기고 원문 예외로
민감정보를 재노출하지 않는다.

## 6. 추적 원장

- AIRun: 상태·호출 시각·계약 버전·Correlation
- SymptomAssessment: 구조화 증상·위험 결과
- CustomerGuidance: 공개 가능한 안내와 안전 행동
- TransitionHistory: 적용 Event·Actor·Version
- IdempotencyRecord: 최초 요청·응답과 Replay

## 7. 검증

1. 신규 제출 AI 1회
2. Replay 추가 호출 0회
3. Payload 충돌 AI 호출 0회
4. 503·Timeout 후 고객 입력·State 보존
5. AIRun 성공·실패·Timeout 저장
6. Header·Body·DB Correlation 일치
7. Prompt·Token·원문 증상 로그 비노출

## 8. 판정

결정적 단위 테스트는 코드 경계를 증명하고, 실제 Django→Uvicorn Socket Test는
Process 간 연결을 증명한다. 둘 중 하나만으로 전체 AI 통합 PASS를 선언하지 않는다.
