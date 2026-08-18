# 고객·AI·상담 통합 시나리오 검증 가이드

> 관련 업무: Backend·AI·Mobile·Web 수직 E2E
> 핵심 원칙: 과거 Fixture가 아닌 새 합성 Inquiry 1건을 끝까지 사용한다.

## 1. 목표 시나리오

```text
고객 Login
→ 구독 조회
→ 새 Inquiry 생성
→ 최초 증상 제출
→ 실제 AI 분석·RAG·Guidance 저장
→ 고객 Guidance 조회
→ 고객 상담 요청
→ 상담사 목록·상세
→ 상담 시작·기록·확정·완료
→ 같은 Inquiry 최종 재조회
```

## 2. 새 Inquiry가 필요한 이유

- 기존 Inquiry는 과거 Mock·상태·Idempotency 기록이 섞일 수 있다.
- 신규 제출 AI 호출 1회와 Replay 0회를 정확히 측정할 수 있다.
- 하나의 Correlation과 Aggregate 이력을 처음부터 추적할 수 있다.
- Seed 완료와 실제 Runtime 저장을 구분할 수 있다.

## 3. 시작 전 Gate

| 구간 | 준비 조건 |
| --- | --- |
| Git | 팀이 사용할 최종 코드 기준 |
| Backend | Health 200, Migration pending 0 |
| PostgreSQL | 승인 통합 DB·합성 Fixture·Crosswalk 준비 |
| AI | Health 200, 실제 Provider·RAG Mode 준비 |
| Mobile | Backend Remote Mode·Login 가능 |
| Web | Mock Off·상담사 Remote Adapter 준비 |

환경이 다르면 실행하지 않고 `ENVIRONMENT_BLOCKED`로 기록한다.

## 4. Backend·DB 사전검증

```powershell
.\backend\.venv\Scripts\python.exe .\backend\manage.py check
.\backend\.venv\Scripts\python.exe .\backend\manage.py showmigrations
.\backend\.venv\Scripts\python.exe -B `
  .\scripts\database\audit_backend_ai_g1b_readiness.py `
  --require-ready --require-team-database
```

## 5. 필수 증거

- Inquiry·Symptom·State·History·Idempotency
- AI 요청 1회와 Replay 추가 호출 0회
- AIRun·Assessment·Guidance·EvidenceLink
- Backend·AI Header·Body·DB Correlation 일치
- 고객 Guidance 공개 DTO와 내부 근거 비노출
- 상담 시작·기록·확정·완료 상태 전이
- 같은 Inquiry의 최종 Snapshot

## 6. 오류 최소 범위

Happy Path가 먼저 통과한 뒤 다음을 실행한다.

1. Replay
2. Stale `state_version` 409
3. AI 503
4. AI Timeout
5. NO_EVIDENCE
6. DANGER

오류 Case는 새 Process·별도 Fixture를 사용하고 제품 코드에 테스트용 Sleep·오류
Hook을 넣지 않는다.

## 7. 중단 조건

- Provider·DB·Role·CA 미주입
- Mock 응답만 사용
- Crosswalk·Readonly View 미검증
- 새 Inquiry가 아닌 과거 실패 Inquiry 재사용
- 다른 담당자의 공유 환경을 임의 Migration·Reset

## 8. 판정

작성자 사전검증은 E2E 준비 상태다. 같은 환경에서 정상 흐름과 필수 오류 경계를
재현하고 독립 QA가 증거를 확인한 뒤 PM이 최종 Gate를 판정한다.
