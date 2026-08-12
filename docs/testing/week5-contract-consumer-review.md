# 5주차 Contract 소비자 검토 Matrix

> 최초 검토 기준: `main@92b0674cd1a3376a2c058715cd5ef32222125755`
> 현재 재검증 후보: `main@f781e92be75d09a1f5bf0464f9ae1fdf90e97bdc`
> 현재 상태: **IN_PROGRESS**
> 요청 원본: `docs/handoffs/week5-contract-consumer-review-request.md`

## 1. 검토 현황

| 검토자 | 소비 영역 | 반드시 확인할 내용 | 요구 증거 | 상태 |
|---|---|---|---|---|
| 최지용 | Backend Runtime | Event·권한·`state_version`·멱등성·409와 Crosswalk Runtime 12개가 Source/Test와 일치 | 파일 또는 PR, 표적 Test 명령·결과 | APPROVE |
| 이동윤 | AI | AI 결과의 Event·Schema·위험·근거 없음·Fallback 정합성, AI의 직접 상태 변경 금지 | 파일 또는 PR, Schema·Safety·Fallback Test | CODE_ON_MAIN · FINAL_ACK_PENDING |
| 한예나 | Web | `allowed_actions`, 서버 상태, Date, 403/404/409/422 소비와 Mock 자동 성공 금지 | 파일 또는 PR, Test·Lint·Build 결과 | CODE_ON_MAIN · FINAL_ACK_PENDING |
| 양정현 | Mobile | DTO·UiState·Action·Date·Error와 Remote/Mock 경계 정합성 | 파일 또는 PR, Unit/UI·Build 결과 | APPROVE |
| 김은진 | QA | 현재 Commit의 Contract Test·대표 Fixture·Crosswalk·생성물 Drift | QA 문서, 실행 명령·Exit Code·결과 | APPROVE · EVIDENCE_PATH_FOLLOWUP |

기존 `docs/testing/results/week5-entry-gate-result.md`에는 이전 기준 Commit의 Contract Gate PASS가 있다. 이번 최종 폐쇄에는 위 현재 기준 Commit 또는 이후 최종 후보 Commit의 명시적 ACK가 필요하다.

## 2. 판정 규칙

- `APPROVE`: 계약 소비가 확인되고 재현 증거가 있다.
- `CHANGE_REQUEST`: 계약과 소비 코드가 다르며 수정 대상·재현 방법이 있다.
- `HOLD`: 필요한 Runtime 또는 환경이 없어 검토할 수 없다.
- “검토 완료”라는 문장만으로는 승인하지 않는다.
- 검토자가 다른 담당자의 계약·코드를 대신 고치지 않고 불일치 경로와 재현 증거를 회신한다.

## 3. 최종 PM 판정

```text
consumer_ack=3/5
contract_gate=PASS
crosswalk=13/6/0/4
final_baseline_commit=PENDING
baseline_status=PM_BASELINE_CANDIDATE
overall_decision=HOLD_FOR_AI_WEB_ACK_AND_LATEST_GATE
```

회신이 들어올 때마다 해당 행의 상태와 증거 경로를 갱신한다. 5명 모두 승인한 최종 후보 Commit에서 Contract Gate를 다시 실행한 뒤 `TEAM_BASELINE` 전환 여부를 결정한다.

## 4. 2026-08-11 접수 회신

- 정규화 기록: `docs/handoffs/week5-contract-consumer-responses-20260811.md`
- Mobile은 구현 Commit이 현재 main에 포함돼 ACK로 인정한다.
- Web은 내용상 승인했으나 기재 Commit을 현재 저장소에서 확인할 수 없어 ACK 수치에는 아직 포함하지 않는다.
- QA의 기존 ACK는 `92b0674` 증거다. 이후 Backend·AI·Contract가 변경됐으므로 최종 후보 ACK는 재검증이 필요하다.
- Backend 원래 불일치 두 건은 `e290fe3`에서 작성자 수정됐고 현재 main에 포함됐다.
- PM은 작성자 수정을 수용했지만 고객 Snapshot 동적 `allowed_actions` 등 계약 후속 3건과 독립 QA 전까지 Backend ACK를 보류한다.
- 최초 결정: `docs/decisions/Backend Contract 소비 불일치 PM 결정.md`
- 후속 결정: `docs/decisions/Backend Runtime12 후속 계약 PM 결정.md`

## 5. 2026-08-12 Backend QA·AI 공동 Mock 판정

- Backend Runtime12 후속 4건은 `e146d23`에서 독립 QA `APPROVE`를 받아 Backend ACK를 최종 승인한다.
- QA 결과는 표적 `98 passed/5 skipped`, Backend 전체 `1004 passed/19 skipped`, PostgreSQL Row Lock `5 passed/0 skipped`, Migration Drift `NONE`이다.
- QA 증거 파일 경로는 아직 정확한 파일명·Commit이 없어 감사 추적 보완으로 남긴다.
- P0-2 정상 제출·Replay 공동 Mock은 PASS로 종료한다.
- AI No-Evidence 정합화는 최신 `origin/dongyoon@692ccd5` 병합을 승인하며 AI ACK는 실제 main 반영 뒤 계산한다.
- PM 결정: `docs/decisions/20260812-backend-ai-gate-pm-decision.md`

## 6. 2026-08-12 현재 main 재판정

- AI와 Web 소비 코드는 `main@f781e92`에 포함됐다.
- `REQUEST_CONSULTATION`이 Backend Runtime으로 승격돼 Crosswalk는 `13/6/0/4`다.
- 병합은 담당자의 최종 ACK를 대신하지 않으므로 ACK 수치는 `3/5`로 유지한다.
- 현재 로컬 Python에는 `PyYAML`이 없어 첫 Validator가 실행되지 않았지만, 동일 SHA의 원격 Contract CI run `31572598233`과 Data CI run `31572598249`가 모두 PASS했다.
- 기술 Gate는 폐쇄됐다. 남은 조건은 AI·Web 명시적 ACK와 최종 고정 SHA 기록이다.
