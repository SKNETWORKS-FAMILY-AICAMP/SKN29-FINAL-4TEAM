# 5주차 Blocker Register

> 기준일: **2026-08-11 KST**
> 기준 Commit: `main@4ac79e6227ce271252054b1e986d6ee24eefce4a`
> 상태: **ACTIVE**

| ID | 관련 업무 | Blocker | 담당자 | 해제 조건 | 목표일 | 상태 |
|---|---|---|---|---|---|---|
| `W5-BLK-001` | 3.3 | 원래 Backend 불일치는 수정됐으나 고객 Snapshot 동적 `allowed_actions` 후속과 독립 QA가 남음 | 최지용·김은진 | API·Runtime 후속 적용, 표적 회귀·PostgreSQL 독립 QA | 8/12 | `FIX_APPLIED_QA_PENDING` |
| `W5-BLK-002` | 3.3 | AI 소비 검토 회신 없음 | 이동윤 | Event·Schema·위험·근거 없음·Fallback Test와 기준 Commit 회신 | 8/12 | `REQUESTED` |
| `W5-BLK-003` | 3.3·3.6 | Web 보고 Commit의 기준선 포함 및 실제 Remote 소비 미확인 | 한예나·김은진 | 현재 후보 Commit 확인, 실제 Backend Remote Smoke·Build 재현 | 8/12 | `HOLD` |
| `W5-BLK-004` | 3.4 | Contract CI Workflow 적용과 원격 실행 | 김은진·윤승혁 | 후보 `83f7373`에서 필수 7개 Gate·Data CI PASS 확인 | 8/11 | `RESOLVED` |
| `W5-BLK-005` | 3.5 | 실제 Multi-Agent·LLM·팀 pgvector·Backend HTTP 통합 증거 없음 | 이동윤·최지용·김은진 | 같은 Inquiry의 HTTP·Schema·Event·DB·Trace와 4개 시나리오 PASS | 8/12 | `HOLD` |
| `W5-BLK-006` | 3.6 | Mobile Guidance·Follow-up·기사 Visit Route 및 Remote Smoke 미완료 | 최지용·양정현·김은진 | Route 제공, 고객·기사 Remote Mode·Mock 비대체·APK 결과 재현 | 8/13 | `HOLD` |

Blocker 해제는 파일 존재나 작성자 완료 보고만으로 처리하지 않는다. 후보 Commit·명령·Exit Code·Runtime·소비자·QA 증거를 연결한 뒤 일일 Gate와 Exit Gate를 함께 갱신한다.
