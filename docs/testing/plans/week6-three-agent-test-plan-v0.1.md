# 6주차 3-Agent 후보 Runtime 테스트 계획 v0.1

> 기준 Branch: `dongyoon`  
> 기준선 Commit: `d00fca53fa024dd50624a42adb1e78c9582fd0eb`  
> 대상: 기본 OFF 후보 Runtime과 기존 Single RAG 회귀

## 1. 판정 경계

| 판정 | 의미 |
|---|---|
| `UNIT_PASS` | Fake Provider·격리 객체로 역할·Routing 계약 재현 |
| `CONTRACT_PASS` | 공개 Schema와 Backend Mapper 경계 유지 |
| `LOCAL_CANDIDATE_PASS` | 실제 pgvector·OpenAI를 후보 Runtime으로 직접 실행 |
| `JOINT_E2E_PASS` | Backend·DB·Mobile/Web까지 같은 Inquiry로 실행 |
| `NOT_RUN` | 실행 증거가 없음 |

Unit PASS를 실제 Provider·팀 DB·서비스 E2E PASS로 확대하지 않는다.

## 2. 자동 검증 Matrix

| ID | 검증 | 기대 결과 |
|---|---|---|
| `W6-MA-001` | 기본 Runtime | 설정이 없으면 `single_rag` |
| `W6-MA-002` | danger Routing | Symptom→Care, Retrieval·LLM 0회 |
| `W6-MA-003` | Evidence 있음 | Symptom→Evidence→Care, 공개 응답 Single RAG Parity |
| `W6-MA-004` | 정보 부족 Feedback | Evidence→Symptom→Care, 질문 반환, `NO_EVIDENCE` 미적용 |
| `W6-MA-005` | 답변 후 근거 없음 | 질문 0건, `FALLBACK/RETRIEVING`, `NO_EVIDENCE` 후보 |
| `W6-MA-006` | Hop 제한 | 최대 Hop 초과를 503으로 Fail-close |
| `W6-MA-007` | 잘못된 Runtime 설정 | Single RAG 우회 없이 503 |
| `W6-MA-008` | 역할별 출력 계약 | 세 Agent가 자기 소유 Pydantic 출력 반환 |
| `W6-MA-009` | 비교 실행기 | 상태·건수·Latency·Token·SHA만 기록, 본문 비노출 |
| `W6-MA-010` | HTTP 공개 계약 | Runtime/Handoff 내부 필드 비노출 |

## 3. 회귀 명령

```powershell
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit -q
.\ai\.venv\Scripts\python.exe -m pytest `
  tests\contract\ai `
  tests\safety\test_week5_ai_safety_crosswalk.py -q

Set-Location backend
.\.venv\Scripts\python.exe -m pytest `
  tests\unit\ai_integration\test_ai_adapter.py `
  tests\unit\ai_integration\test_ai_state_event_contract_conformance.py -q
```

## 4. 실제 Runtime 후속 Gate

다음 항목은 보호 환경변수가 주입된 Process에서 별도로 실행한다.

1. `AI_PIPELINE_RUNTIME=multi_agent`
2. 실제 Readonly pgvector와 고정 Embedding Revision
3. 실제 OpenAI Guidance 한정 호출
4. 신규 Inquiry 정상 Guidance와 Replay
5. 정보 부족→질문 저장→고객 답변→재검색
6. danger, `NO_EVIDENCE`, 503, Timeout
7. Single RAG와 동일 평가 입력의 품질·Latency·Token 비교

DSN, Key, 고객 원문, Prompt, Evidence·Vector 본문은 결과 파일에 기록하지 않는다.
