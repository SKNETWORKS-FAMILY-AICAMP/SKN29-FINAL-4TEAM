# 김은진 — 5주차 Contract CI 적용·검증 요청

> 감사 기준: `main@92b0674cd1a3376a2c058715cd5ef32222125755`
> 현재 상태: **HANDOFF_REQUIRED**
> 상세 적용안: `docs/testing/contracts-ci.md`

## 요청 이유

현재 Data CI는 State Machine과 Mermaid 두 검사만 실행합니다. Code·OpenAPI·Example·Crosswalk·Root Contract Test와 주요 계약 경로 Trigger가 빠져 있어 로컬 계약 검증 누락을 완전히 차단하지 못합니다.

## 요청 작업

1. 별도 `.github/workflows/contracts-ci.yml` 분리안을 검토해 주세요.
2. `contracts/**`, `scripts/contracts/**`, `tests/contract/**`의 주요 경로를 Trigger에 포함해 주세요.
3. 다음 7개 Gate를 이름이 구분되는 Step으로 실행해 주세요.

```text
validate_state_machine.py
render_state_machine.py --check
validate_codes.py
validate_openapi.py
validate_examples.py
validate_contract_crosswalk.py
pytest tests/contract -q
```

4. 실제 Branch 또는 PR에서 전체 Step이 실행되는지 확인해 주세요.
5. Contract CI 원격 PASS 후 Data CI의 State·Mermaid 중복 유지 여부를 회신해 주세요.

CI 삭제, `continue-on-error`, Validator 완화는 요청 범위가 아닙니다.

## 회신 형식

```text
reviewer=김은진
reviewed_commit=<전체 SHA>
workflow_decision=SEPARATE_CONTRACT_CI | KEEP_IN_DATA_CI | CHANGE_REQUEST | HOLD
applied_commit=<전체 SHA 또는 NOT_APPLIED>
trigger_paths=<적용 경로>
gate_result=<7개 Step별 PASS/FAIL/NOT_RUN>
run_url=<GitHub Actions URL 또는 NOT_RUN>
data_ci_overlap=<KEEP | REMOVE_AFTER_PASS | CHANGE_REQUEST>
remaining_blocker=<없으면 NONE>
reviewed_at=<YYYY-MM-DD HH:mm KST>
```
