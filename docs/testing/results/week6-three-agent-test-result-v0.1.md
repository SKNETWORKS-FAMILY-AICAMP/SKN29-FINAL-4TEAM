# 6주차 3-Agent 후보 Runtime 1차 테스트 결과 v0.1

> 검증일: 2026-08-18 KST  
> 시작 기준 Commit: `d00fca53fa024dd50624a42adb1e78c9582fd0eb`  
> Branch: `dongyoon`  
> 종합 판정: `CANDIDATE_RUNTIME_UNIT_PASS / LIVE_AND_JOINT_E2E_NOT_RUN`

## 1. 구현 결과

- `Symptom Analysis Agent`, `Evidence Analysis Agent`, `Care Decision Agent`의
  독립 출력 계약과 허용 Tool 경계를 구현했다.
- Supervisor Handoff, 최대 8 Hop, 한 실행의 Evidence Feedback 1회 제한을 구현했다.
- 정보 부족 질문 대기와 공식 근거 부재 `NO_EVIDENCE`를 분리했다.
- 기본 Runtime은 `single_rag`이며 `AI_PIPELINE_RUNTIME=multi_agent`에서만 후보
  Runtime을 실행한다.
- 공개 `SymptomAnalysisResponse 3.0.0`에는 Runtime·Handoff 내부 정보를 추가하지
  않았다.
- 비교 실행기는 공개 결과 SHA, Evidence Identity SHA, 건수, 상태, Latency,
  Token만 반환하며 입력·Evidence 본문을 저장하지 않는다.

## 2. 실행 증거

| 범위 | 결과 | 판정 |
|---|---|---|
| 변경 전 기준 회귀 | `58 passed, 2 warnings` | `BASELINE_PASS` |
| 신규 3-Agent Unit | `9 passed` | `UNIT_PASS` |
| 신규+HTTP 표적 | `30 passed, 1 warning` | `UNIT_PASS` |
| AI Unit 전체 | `240 passed, 5 warnings, 7 subtests passed` | `REGRESSION_PASS` |
| Root AI Contract·Safety | `27 passed` | `CONTRACT_PASS` |
| Backend AI Adapter·State Event | `10 passed` | `CONTRACT_PASS` |
| AI 의존성 | `pip check`: No broken requirements | `PASS` |
| `git diff --check` | 오류 없음, Windows CRLF 안내만 존재 | `PASS` |

Backend 교차검증을 AI 가상환경으로 함께 수집하려 한 최초 명령은 해당 환경에
Django가 없어 `ModuleNotFoundError`로 중단됐다. 코드 실패로 처리하지 않고 Root
Test와 Backend 전용 `.venv` 명령으로 분리해 각각 Exit 0을 확인했다.

## 3. 통과한 핵심 경계

- danger는 Vector Store와 무관하게 Symptom→Care로 종료하고 LLM을 호출하지 않는다.
- Evidence 정상 경로의 공개 결과는 동일 Fake 조건에서 Single RAG와 일치한다.
- 정보 부족·검색 0건은 질문을 반환하되 `NO_EVIDENCE`로 승격하지 않는다.
- 이전 답변으로 누락 필드가 해소된 뒤 검색 0건이면 기존 `NO_EVIDENCE`가 적용된다.
- Handoff Metadata에 고객 원문과 Evidence Summary가 포함되지 않는다.
- 지원하지 않는 Runtime 값은 기본 경로로 우회하지 않고 HTTP 503으로 종료한다.

## 4. 아직 완료로 표시하지 않는 범위

| 범위 | 상태 | 완료 조건 |
|---|---|---|
| 실제 Readonly pgvector 후보 Runtime | `NOT_RUN` | 보호 DSN Process 주입 후 실제 Query |
| 실제 OpenAI 후보 Runtime | `NOT_RUN` | Provider·Schema·Token·Latency 검증 |
| 질문→고객 답변→재검색 Backend 저장 | `NOT_RUN` | 같은 Inquiry의 실제 HTTP·DB 증거 |
| Single RAG 대비 실제 품질·비용 비교 | `NOT_RUN` | 동일 승인 평가셋 양쪽 실행 |
| 상담 인계 | `CONTRACT_DECISION_REQUIRED` | 별도 Consultation Summary 또는 Backend 조합 확정 |
| Mobile·Web 최소 E2E | `NOT_RUN` | 공동 실행 및 동일 Inquiry 조회 |

따라서 현재 결과는 후보 Runtime의 코드·계약·Unit 기준선이다. 기본 Runtime 전환이나
6주차 Feature Complete 근거로 사용할 수 없다.
