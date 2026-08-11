# 5주차 Contract 소비자 검토 Matrix

> 검토 기준: `main@801f58e1512dfc9e12299465b6551fff2a276e3a`
> 현재 상태: **IN_PROGRESS**
> 요청 원본: `docs/handoffs/week5-contract-consumer-review-request.md`

## 1. 검토 현황

| 검토자 | 소비 영역 | 반드시 확인할 내용 | 요구 증거 | 상태 |
|---|---|---|---|---|
| 최지용 | Backend Runtime | Event·권한·`state_version`·멱등성·409와 Crosswalk Runtime 12개가 Source/Test와 일치 | 파일 또는 PR, 표적 Test 명령·결과 | REQUESTED |
| 이동윤 | AI | AI 결과의 Event·Schema·위험·근거 없음·Fallback 정합성, AI의 직접 상태 변경 금지 | 파일 또는 PR, Schema·Safety·Fallback Test | REQUESTED |
| 한예나 | Web | `allowed_actions`, 서버 상태, Date, 403/404/409/422 소비와 Mock 자동 성공 금지 | 파일 또는 PR, Test·Lint·Build 결과 | REQUESTED |
| 양정현 | Mobile | DTO·UiState·Action·Date·Error와 Remote/Mock 경계 정합성 | 파일 또는 PR, Unit/UI·Build 결과 | REQUESTED |
| 김은진 | QA | 현재 Commit의 Contract Test·대표 Fixture·Crosswalk·생성물 Drift | QA 문서, 실행 명령·Exit Code·결과 | REQUESTED |

기존 `docs/testing/results/week5-entry-gate-result.md`에는 이전 기준 Commit의 Contract Gate PASS가 있다. 이번 최종 폐쇄에는 위 현재 기준 Commit 또는 이후 최종 후보 Commit의 명시적 ACK가 필요하다.

## 2. 판정 규칙

- `APPROVE`: 계약 소비가 확인되고 재현 증거가 있다.
- `CHANGE_REQUEST`: 계약과 소비 코드가 다르며 수정 대상·재현 방법이 있다.
- `HOLD`: 필요한 Runtime 또는 환경이 없어 검토할 수 없다.
- “검토 완료”라는 문장만으로는 승인하지 않는다.
- 검토자가 다른 담당자의 계약·코드를 대신 고치지 않고 불일치 경로와 재현 증거를 회신한다.

## 3. 최종 PM 판정

```text
consumer_ack=0/5
contract_gate=PASS
crosswalk=12/7/0/4
final_baseline_commit=PENDING
baseline_status=PM_BASELINE_CANDIDATE
overall_decision=HOLD_FOR_CONSUMER_ACK
```

회신이 들어올 때마다 해당 행의 상태와 증거 경로를 갱신한다. 5명 모두 승인한 최종 후보 Commit에서 Contract Gate를 다시 실행한 뒤 `TEAM_BASELINE` 전환 여부를 결정한다.
