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
| `W5-BLK-008` | 3.7 | 8/13~8/14 일일 Gate·최종 Exit 미도래 | 윤승혁·김은진 | 매일 같은 SHA 증거를 기록하고 8/14 `PASS/CONDITIONAL_PASS/HOLD` 최종 승인 | 8/14 | `IN_PROGRESS` |

Blocker 해제는 파일 존재나 작성자 완료 보고만으로 처리하지 않는다. 후보 Commit·명령·Exit Code·Runtime·소비자·QA 증거를 연결한 뒤 일일 Gate와 Exit Gate를 함께 갱신한다.

## 2026-08-13 E2E 집중 업무 중간 판정

```text
baseline_commit=1289d4b3673d9b061833fa94d45096bde1541a02
scenario=SYN-JAC104-002 / WPUJAC104DWH / 출수량 저하
visit_scope=P1_EXCLUDED
targeted_backend_tests=8 PASS
root_e2e=HOLD
```

Backend 표적 검증에서는 AI 결과 저장·State 적용 경계, 상담 요청, 상담 시작·완료, stale `state_version` 409, 고객·상담사 실제 HTTP 조회 기반이 모두 통과했다. 실행 명령은 AI Service·실단말·Web Browser를 대신하지 않으며 Root E2E PASS로 합산하지 않는다.

현재 대표 흐름을 직접 멈추는 P0 Blocker는 다음과 같다.

| 연결 구간 | 확인된 Blocker | 담당 | 해제 조건 |
|---|---|---|---|
| Backend → AI → Backend State | 기본 Runtime 호출이 공식 Evidence Verifier를 주입하지 않아 정상 AI 결과를 저장해도 `SAFE_GUIDANCE_READY`가 적용되지 않는다. | 최지용·이동윤 | 공식 Evidence 검증기를 실제 호출 경로에 연결하고 Local AI HTTP 결과가 `AI_GUIDANCE`와 공개 Evidence로 저장되는 Test PASS |
| Backend → Customer Mobile | Customer Snapshot에는 Guidance·Evidence가 없고 Mobile Remote의 `getGuidance()`는 `GUIDANCE_ROUTE_UNAVAILABLE`로 Fail-closed 한다. | 최지용·양정현 | Customer Guidance·Evidence Route와 Mobile Remote 소비를 같은 Inquiry로 실단말 검증 |
| 공용 Runtime | 현재 로컬 작업공간에는 AI 실행 환경과 팀 pgvector 설정이 없어 실제 Baseline AI Preflight를 수행할 수 없다. | 김은진·이동윤·최지용 | 같은 SHA의 Backend·AI·DB 주소와 Seed를 공유하고 Health·Local Analyze·DB 저장 증거 확보 |
| Backend → Consultant Web | Backend 상담 Runtime과 Web Remote 코드는 있으나 같은 Backend에서 목록→상세→상담 완료를 실행한 증거가 없다. | 한예나·최지용·김은진 | 같은 Inquiry의 Web Remote Smoke와 상담 완료 후 Customer Snapshot 재조회 PASS |

위 네 항목 외의 챗봇·AI 비교 실험·방문기사·UX 고도화는 Backlog 상태를 유지한다. 8월 14일 실제 E2E 판정 전까지 WBS와 Exit Gate는 갱신하지 않는다.

## 2026-08-13 11:37 KST — 4.3 Blocker 중앙 조정 재판정

```text
scope_baseline=1289d4b3673d9b061833fa94d45096bde1541a02
local_main=f9f258a97d6db321ca7b4f43d400d1c13e2c0dc5
origin_main=df9c01c
local_main_ahead_of_origin=3
targeted_backend_regression=49 PASS
shared_runtime=NOT_CONFIRMED
overall=IN_PROGRESS
```

새 기준선에서 Backend의 공식 Evidence Verifier와 위험 판정 연결 코드는 확인됐고 관련 Backend 표적 회귀 49개가 통과했다. 다만 실제 AI·pgvector·공용 DB를 사용한 Runtime 결과는 아니므로 Backend→AI 구간 전체를 PASS로 닫지 않는다.

| 우선순위 | 연결 구간 | 11:37 판정 | 담당 | 즉시 해제 조건 |
|---:|---|---|---|---|
| 1 | 기준 SHA·공용 환경 | `P0_BLOCKER` | 김은진·전원 | 실제 E2E 후보를 원격 `main`의 40자리 SHA로 고정하고 Backend·AI·DB 접속 정보와 Seed PASS를 공유한다. 현재 Local `main`은 `origin/main`보다 3 Commit 앞서 있다. |
| 2 | Backend → 실제 AI → DB·State | `CODE_PASS_RUNTIME_PENDING` | 최지용·이동윤·김은진 | 같은 후보 SHA에서 Local AI HTTP, 공식 Evidence 검증·저장, `AI_GUIDANCE`, Correlation을 실제 PostgreSQL/pgvector로 확인한다. |
| 3 | Backend → Customer Mobile Guidance | `P0_BLOCKER` | 최지용·양정현 | 고객용 Guidance·Public Evidence Route를 제공하고 Mobile Remote `getGuidance()`의 `GUIDANCE_ROUTE_UNAVAILABLE`을 실제 소비로 교체해 실단말에서 확인한다. |
| 4 | Mobile 상담 요청 → Web 인계 | `DECISION_APPROVED_IMPLEMENTATION_PENDING` | 최지용 | 승인된 `SYNTHETIC_E2E_ASSIGNMENT`를 합성 Scenario 경계에 구현하고 다른 상담사 404·재현 가능한 Seed/Transaction·동일 Inquiry Web 노출 Test를 통과한다. |
| 5 | Consultant Web → 상담 완료 → Mobile | `RUNTIME_PENDING` | 한예나·최지용·양정현·김은진 | Mock Off Web에서 동일 Inquiry 상담 시작·기록·완료 후 Mobile Snapshot에 최신 State·Version이 반영되는 것을 확인한다. |

PM 조정 순서는 `원격 후보 SHA 고정 → 실제 AI·Evidence 저장 → Mobile Guidance → 합성 상담사 인계 → Web 상담 완료 → Mobile 최종 재조회`로 고정한다. 앞 구간 전체가 끝날 때까지 기다리지 않고 각 담당자는 가능한 Smoke를 병렬로 수행한다.
