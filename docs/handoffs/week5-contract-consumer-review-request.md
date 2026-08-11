# 5주차 Contract 소비자 검토 요청

> 기준 Commit: `92b0674cd1a3376a2c058715cd5ef32222125755`
> 목적: Validator 통과 계약이 각 영역에서 실제로 소비 가능한지 확인

## 담당자별 요청

| 수신자 | 확인 범위 | 최소 회신 증거 |
|---|---|---|
| 최지용 | Backend Event·권한·`state_version`·멱등성·409·Crosswalk Runtime 상태 | 관련 파일과 표적 Test 결과 |
| 이동윤 | AI Event·Schema·위험·근거 없음·Fallback, 직접 상태 변경 금지 | 관련 파일과 Schema·Safety Test 결과 |
| 한예나 | Web `allowed_actions`·상태·Date·403/404/409/422 | 관련 파일과 Test·Lint·Build 결과 |
| 양정현 | Mobile DTO·UiState·Action·Date·Error | 관련 파일과 Unit/UI·Build 결과 |
| 김은진 | Contract Test·대표 Fixture·Crosswalk·생성물 Drift | QA 결과와 명령별 Exit Code |

자기 관할 소비 코드만 검토하고, 계약 불일치는 임의 수정하지 말고 경로와 재현 방법을 회신해 주세요. Runtime이 없는 Action은 구현 완료로 간주하지 않습니다.

## 회신 형식

```text
reviewer=<이름>
reviewed_commit=<전체 SHA>
decision=APPROVE | CHANGE_REQUEST | HOLD
files=<확인한 파일 또는 PR>
commands=<실행 명령>
result=<passed/failed/not_run 및 수치>
contract_mismatch=<없으면 NONE>
remaining_blocker=<없으면 NONE>
reviewed_at=<YYYY-MM-DD HH:mm KST>
```

다섯 회신은 `docs/testing/week5-contract-consumer-review.md`에 취합한다.
