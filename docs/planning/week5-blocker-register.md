# 5주차 Blocker Register

> 기준일: **2026-08-12 KST**
> 기준 Commit: `main@f781e92be75d09a1f5bf0464f9ae1fdf90e97bdc`
> 상태: **ACTIVE**

| ID | 관련 업무 | Blocker | 담당자 | 해제 조건 | 목표일 | 상태 |
|---|---|---|---|---|---|---|
| `W5-BLK-001` | 3.3 | Backend Runtime12 후속과 독립 QA | 최지용·김은진 | `e146d23` 독립 QA APPROVE | 8/12 | `RESOLVED` |
| `W5-BLK-002` | 3.3 | AI No-Evidence Runtime이 main 미포함 | 이동윤·윤승혁 | AI 변경이 main에 병합됨 | 8/12 | `RESOLVED` |
| `W5-BLK-003` | 3.3·3.6 | Web 코드 병합 후 최종 ACK·실제 Remote 소비 미확인 | 한예나·김은진 | `f781e92` 계약 ACK와 상담사 목록→상세→상담→Visit 실제 Backend Smoke·Build 재현 | 8/13 | `HOLD` |
| `W5-BLK-004` | 3.4 | Contract CI Workflow 적용과 원격 실행 | 김은진·윤승혁 | 후보 `83f7373`에서 필수 7개 Gate·Data CI PASS 확인 | 8/11 | `RESOLVED` |
| `W5-BLK-005` | 3.5 | 실제 Multi-Agent·LLM·팀 pgvector·Backend HTTP 통합 증거 없음 | 이동윤·최지용·김은진 | 같은 Inquiry의 HTTP·Schema·Event·DB·Trace와 4개 시나리오 PASS | 8/12 | `HOLD` |
| `W5-BLK-006` | 3.6 | Mobile Guidance·상담요청·기사 Visit 소비 Gate 미완료 | 최지용·양정현·김은진 | Follow-up은 실단말 PASS. 상담요청 Runtime의 실단말 재검증, Guidance·기사 Visit Route 제공과 Remote Mode·Mock 비대체·APK 결과 재현 | 8/14 | `PARTIALLY_RESOLVED` |
| `W5-BLK-007` | 3.3 | AI·Web 명시적 최종 ACK 없음 | 이동윤·한예나·윤승혁 | `f781e92` Contract CI·Data CI는 PASS. AI·Web ACK 수집 후 최종 Baseline Commit 기록 | 8/13 | `PARTIALLY_RESOLVED` |
| `W5-BLK-008` | 3.7 | 8/13~8/14 일일 Gate·최종 Exit 미도래 | 윤승혁·김은진 | 매일 같은 SHA 증거를 기록하고 8/14 `PASS/CONDITIONAL_PASS/HOLD` 최종 승인 | 8/14 | `SCHEDULED` |

Blocker 해제는 파일 존재나 작성자 완료 보고만으로 처리하지 않는다. 후보 Commit·명령·Exit Code·Runtime·소비자·QA 증거를 연결한 뒤 일일 Gate와 Exit Gate를 함께 갱신한다.
