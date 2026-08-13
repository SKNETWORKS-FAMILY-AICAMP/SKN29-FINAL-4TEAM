# 5주차 Contract 소비자 검토 요청

> 기준 Commit: `f781e92be75d09a1f5bf0464f9ae1fdf90e97bdc`
> 목적: Validator 통과 계약이 각 영역에서 실제로 소비 가능한지 확인
> 현재 상태: Backend·Mobile·QA 승인, AI·Web 최종 ACK 대기

현재 SHA의 Contract CI run `31572598233`과 Data CI run `31572598249`는 모두 PASS했습니다. 아래 두 담당자만 현재 main 기준으로 최종 회신해 주세요.

## 담당자별 요청

| 수신자 | 확인 범위 | 최소 회신 증거 |
|---|---|---|
| 이동윤 | AI Event·Schema·위험·근거 없음·Fallback, 직접 상태 변경 금지 | 관련 파일과 Schema·Safety Test 결과 |
| 한예나 | Web `allowed_actions`·상태·Date·403/404/409/422 | 관련 파일과 Test·Lint·Build 결과 |

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

두 회신을 `docs/testing/week5-contract-consumer-review.md`에 추가해 ACK `5/5`가 되면 윤승혁이 `TEAM_BASELINE`을 선언한다.
