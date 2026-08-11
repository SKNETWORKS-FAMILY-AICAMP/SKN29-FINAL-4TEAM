# 최지용·이동윤·김은진 — Backend↔AI Integration Gate 실행 요청

> 기준 Commit: `92b0674cd1a3376a2c058715cd5ef32222125755`
> 현재 판정: **HOLD**
> 감사 결과: `docs/testing/week5/backend-ai-integration-gate.md`

## 공통 요청

현재 연결 코드를 실제 Multi-Agent·LLM·팀 pgvector 환경에서 같은 Commit으로 실행해 주세요. MockTransport, FastAPI `mock` 모드, 개인 DB 결과만으로는 PASS 처리하지 않습니다.

## 담당자별 요청

| 담당자 | 요청 작업 | 필수 증거 |
|---|---|---|
| 최지용 | Mock이 아닌 Local AI 모드로 Django→FastAPI 호출, AIRun·구조화·질문·Guidance·Evidence·Transition 저장 확인 | Backend·AI URL 요약, Test 명령, DB Assertion, Trace ID |
| 이동윤 | 실제 Multi-Agent·LLM Provider·팀 pgvector를 사용해 정상·위험·근거 없음·Timeout 실행 | Agent Routing·Handoff, Provider 호출, 검색 결과, Fallback Test |
| 김은진 | 두 담당자의 같은 SHA 환경을 독립 재현하고 Mock·Skip·실행 범위를 구분 | 명령별 Exit Code, Test 수치, Run/QA 문서 |

추가로 최지용·이동윤은 공식 Evidence Verifier를 실제 `InquiryAIService` 호출 경로에 연결하고, 검증된 근거가 있을 때만 `SAFE_GUIDANCE_READY`가 적용되는지 확인해 주세요.

## 완료 조건

- Django→FastAPI 실제 소켓과 AI Local 모드 사용
- 실제 역할 기반 Multi-Agent와 제한된 실제 LLM 호출
- 팀 PostgreSQL·pgvector 제품·세대·공식 근거 검색
- `correlation_id`가 Backend→AI→Backend DB·State History로 연결
- AIRun·구조화 증상·추가 질문·Evidence·Guidance 저장
- 상태 전이 최종 권위가 Backend에 있음
- 정상·위험·근거 없음·Timeout 결과가 같은 Commit에서 PASS

## 회신 형식

```text
reviewer=<최지용 | 이동윤 | 김은진>
reviewed_commit=<전체 SHA>
decision=APPROVE | CHANGE_REQUEST | HOLD
environment=<서비스·DB·Provider 요약, Secret 제외>
commands=<실행 명령>
exit_codes=<명령별 Exit Code>
django_fastapi_http=PASS | FAIL | NOT_RUN
multi_agent_runtime=PASS | FAIL | NOT_RUN
actual_llm=PASS | FAIL | NOT_RUN
team_pgvector=PASS | FAIL | NOT_RUN
backend_persistence=PASS | FAIL | NOT_RUN
state_authority=PASS | FAIL | NOT_RUN
normal_scenario=PASS | FAIL | NOT_RUN
danger_scenario=PASS | FAIL | NOT_RUN
no_evidence_scenario=PASS | FAIL | NOT_RUN
timeout_scenario=PASS | FAIL | NOT_RUN
evidence=<Test·Log·QA 문서 경로>
remaining_blocker=<없으면 NONE>
reviewed_at=<YYYY-MM-DD HH:mm KST>
```
