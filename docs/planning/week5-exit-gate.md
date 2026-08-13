# 5주차 Exit Gate

> 기준일: **2026-08-12 KST**
> WBS 기준: `docs/planning/md/WBS.md` v2.1
> 현행 감사 Commit: `main@f781e92be75d09a1f5bf0464f9ae1fdf90e97bdc`
> 현재 판정: **WBS_WEEK5_HOLD · INTERIM**

## 1. 판정 원칙

5주차 Exit는 현행 WBS의 5주차 필수 범위만 판정한다. 대표 전체 E2E·전체 회귀·Feature Complete는 조기 완료 조건부 Gate로 분리한다.

## 2. 필수 Gate 판정표

| Gate | 판정 기준 | 상태 | 증거 | 담당 |
|---|---|---|---|---|
| `W5-G01` 계획 기준선 | Scope·Backlog·Dependency·Owner·Exit 정합성 | `PASS` | Planning 세트·Blocker·후속 인계가 `f781e92`로 정렬됨 | 윤승혁 |
| `W5-G02` 계약 | Validator·Contract Test Exit 0 | `PASS` | `f781e92` Contract CI run `31572598233` PASS | 윤승혁·최지용 |
| `W5-G03` Data·Seed | 대표 입력·Hash·Seed·Crosswalk 검증 | `PASS` | `f781e92` Manifest·QA Report 갱신, Data CI run `31572598249` PASS | 김은진 |
| `W5-G04` AI·Vector 검색 | 실제 LLM·팀 DB 검색·제품·세대 Filter | `HOLD` | 실제 LLM 미구현·팀 pgvector 환경 차단 | 이동윤·김은진 |
| `W5-G05` AI Runtime·Mapping | 핵심 Agent·상담 요약 최소 Runtime·Schema–State Mapping | `HOLD` | Single RAG·규칙 기반, 실제 Multi-Agent 미구현 | 이동윤·최지용·김은진 |
| `W5-G06` Backend·DB | WBS 대상 Test·PostgreSQL·Migration·Seed | `IN_PROGRESS` | Runtime12 독립 QA APPROVE, `REQUEST_CONSULTATION` Runtime·표적 Test·Seed가 `60046c5`에 포함 | 최지용·김은진 |
| `W5-G07` Backend↔AI | 실제 HTTP·Schema·Event·DB·Trace | `HOLD` | P0-2 정상·Replay Mock PASS, Local RAG·pgvector·오류 시나리오 대기 | 최지용·이동윤·김은진 |
| `W5-G08` Web 소비 준비 | WBS 대상 Remote·Test·Build | `HOLD` | 상담·Visit·CONS-04 소비 코드는 main 포함, 상담사 실제 Backend Remote Smoke 대기 | 한예나·김은진 |
| `W5-G09` Mobile 소비 준비 | WBS 대상 Remote·Test·APK | `HOLD` | 고객 Follow-up 실단말 PASS, 상담요청 Runtime 제공; Guidance·기사 Visit Route와 재Smoke 대기 | 양정현·최지용·김은진 |
| `W5-G10` 잔여 Runtime | WBS 대상 Runtime별 PASS·BLOCKED 구분 | `CLASSIFIED` | Owner Matrix·Blocker Register·6주차 비상 인계에 PASS/HOLD 경계 기록 | 영역 담당자 |
| `W5-G11` 인계 | 미완료 담당자·목표일·해제 조건 확정 | `PASS` | `docs/planning/week5-blocker-register.md`, `docs/handoffs/week5-closeout-and-week6-contingency.md` | 윤승혁·김은진 |

## 3. WBS 5주차 최종 판정

| 판정 | 조건 |
|---|---|
| `WBS_WEEK5_PASS` | 필수 Gate가 모두 PASS하고 차단 Blocker가 없다. |
| `WBS_WEEK5_CONDITIONAL_PASS` | 핵심 최소 수직 연결은 PASS하고 잔여 제한이 담당자·목표일·해제 조건과 함께 인계됐다. |
| `WBS_WEEK5_HOLD` | 계약·Data·Backend↔AI 최소 연결 등 핵심 Gate가 실패하거나 증거가 없다. |

## 4. 조기 완료 조건부 판정

| Gate | 현재 상태 | 판정 조건 |
|---|---|---|
| 대표 전체 E2E | `CRITERIA_READY · EXECUTION_HOLD` | `docs/testing/e2e/week5-e2e-acceptance.md` 기준 확정. 필수 Gate 전체 PASS 후 실제 서비스 흐름 재현 |
| 전체 회귀 | `NOT_STARTED` | 대표 E2E 후보 Commit과 영역별 Test 준비 |
| Feature Complete | `NOT_ASSESSED` | 대표 E2E·전체 회귀·차단 결함 0 |

조건부 Gate의 `NOT_STARTED`·`NOT_ASSESSED`는 5주차 필수 실패가 아니다.

## 5. 최종 회신 형식

```text
reviewer=윤승혁
baseline_commit=<전체 SHA>
wbs_week5_decision=WBS_WEEK5_PASS | WBS_WEEK5_CONDITIONAL_PASS | WBS_WEEK5_HOLD
mandatory_gates=<Gate별 PASS/FAIL/BLOCKED/NOT_RUN>
optional_e2e=PASS | FAIL | BLOCKED | NOT_STARTED
optional_full_regression=PASS | FAIL | BLOCKED | NOT_STARTED
feature_complete=PASS | CONDITIONAL_PASS | HOLD | NOT_ASSESSED
evidence=<문서·Test·Log 경로>
remaining_blocker=<없으면 NONE>
week6_7_handoff=<담당자·목표일·해제 조건>
reviewed_at=<YYYY-MM-DD HH:mm:ss KST>
```
