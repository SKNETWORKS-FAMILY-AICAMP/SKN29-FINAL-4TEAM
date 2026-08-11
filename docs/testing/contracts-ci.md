# Contract CI 감사 및 운영안

> 감사일: 2026-08-11 KST
> 감사 기준: `main@92b0674cd1a3376a2c058715cd5ef32222125755`
> 현재 판정: **LOCAL_GATE_PASS · WORKFLOW_OWNER_APPLY_PENDING**
> Workflow 주관: 김은진 / 계약 정책·Validator 주관: 윤승혁

## 1. 결론

현재 `.github/workflows/data-ci.yml`은 State Machine Validator와 Mermaid Drift만 자동 실행한다. Code·OpenAPI·Example·Crosswalk·Root Contract Test가 빠져 있고, 계약 Trigger도 `contracts/state-machine/**`에만 걸려 있어 전체 Contract Gate라고 볼 수 없다.

계약 검증은 별도 `.github/workflows/contracts-ci.yml`로 분리하는 안을 권고한다. 실제 Workflow 생성과 Data CI 중복 제거는 `.github/workflows/**` 주관 담당자인 김은진의 적용·실행 결과로 확정한다.

## 2. 현재 Workflow 감사

### 자동 검증 범위

| 필수 Gate | 현재 Data CI | 판정 |
|---|---|---|
| `validate_state_machine.py` | 실행 | PASS |
| `render_state_machine.py --check` | 실행 | PASS |
| `validate_codes.py` | 없음 | MISSING |
| `validate_openapi.py` | 없음 | MISSING |
| `validate_examples.py` | 없음 | MISSING |
| `validate_contract_crosswalk.py` | 없음 | MISSING |
| `pytest tests/contract -q` | 없음 | MISSING |

### Trigger 범위

| 변경 경로 | 현재 Trigger | 요구 상태 |
|---|---|---|
| `contracts/state-machine/**` | 있음 | 유지 |
| `contracts/api/**` | 없음 | 추가 |
| `contracts/codes/**` | 없음 | 추가 |
| `contracts/examples/**` | 없음 | 추가 |
| `contracts/error-codes/**` | 없음 | 추가 |
| `scripts/contracts/**` | 있음 | 유지 |
| `tests/contract/**` | 없음 | 추가 |

`contracts/CHANGELOG.md`에는 `contracts/**`, `scripts/contracts/**`, `tests/contract/**` 변경 시 전체 계약 Gate가 실행된다고 적혀 있었으나 실제 Workflow와 일치하지 않았다. 현행 Changelog에는 이 감사 결과와 담당자 적용 대기를 명시한다.

## 3. 권장 Workflow 초안

김은진은 아래 안을 검토해 `.github/workflows/contracts-ci.yml`에 적용한다. 각 검사를 별도 Step으로 두어 실패 원인이 로그 이름에서 바로 드러나게 한다.

```yaml
name: Contract CI

on:
  workflow_dispatch:
  pull_request:
    paths:
      - "contracts/state-machine/**"
      - "contracts/api/**"
      - "contracts/codes/**"
      - "contracts/examples/**"
      - "contracts/error-codes/**"
      - "scripts/contracts/**"
      - "tests/contract/**"
      - ".github/workflows/contracts-ci.yml"
  push:
    paths:
      - "contracts/state-machine/**"
      - "contracts/api/**"
      - "contracts/codes/**"
      - "contracts/examples/**"
      - "contracts/error-codes/**"
      - "scripts/contracts/**"
      - "tests/contract/**"
      - ".github/workflows/contracts-ci.yml"

permissions:
  contents: read

jobs:
  verify-contracts:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: "pip"
          cache-dependency-path: |
            backend/requirements/base.txt
            backend/requirements/local.txt

      - name: Install contract gate dependencies
        run: python -m pip install PyYAML==6.0.3 pytest==9.1.1

      - name: Validate state machine
        run: python -B scripts/contracts/validate_state_machine.py

      - name: Reject Mermaid drift
        run: python -B scripts/contracts/render_state_machine.py --check

      - name: Validate code registry
        run: python -B scripts/contracts/validate_codes.py

      - name: Validate OpenAPI
        run: python -B scripts/contracts/validate_openapi.py

      - name: Validate contract examples
        run: python -B scripts/contracts/validate_examples.py

      - name: Validate action-operation crosswalk
        run: python -B scripts/contracts/validate_contract_crosswalk.py

      - name: Run root contract tests
        run: python -B -m pytest tests/contract -q -p no:cacheprovider
```

## 4. 적용·검증 순서

1. 김은진이 별도 Contract CI 분리 여부를 `APPROVE` 또는 `CHANGE_REQUEST`로 결정한다.
2. 승인 시 위 Workflow를 담당자 Branch에 적용한다.
3. Workflow 파일 자체가 Trigger 경로에 포함된 PR에서 최초 실행을 확인한다.
4. 7개 Step이 모두 실제 실행되고 Exit Code `0`인지 확인한다.
5. 실패 로그가 State·Mermaid·Code·OpenAPI·Example·Crosswalk·Test별로 구분되는지 확인한다.
6. Data CI의 State·Mermaid 중복은 Contract CI 원격 PASS와 병합 Gate 전환을 확인한 뒤 제거 여부를 결정한다.
7. CI를 삭제하거나 `continue-on-error`를 사용해 Gate를 약화하지 않는다.

## 5. 책임 경계

| 구분 | 담당 |
|---|---|
| State·Action·완료 정책과 Validator 의미 | 윤승혁 |
| Workflow·Python 환경·Dependency Cache·장애 대응 | 김은진 |
| OpenAPI·Code·Error 계약 불일치 조치 | 최지용, 윤승혁 협업 |
| Root Contract Test 실패 분류 | 김은진, 대상 계약 담당자 협업 |

Contract CI가 실패하면 Step 이름, 대상 SHA, 재현 명령과 Exit Code를 기록한다. 계약 오류는 해당 계약 담당자에게, Runner·Dependency·Trigger 오류는 김은진에게 전달한다.

## 6. 완료 경계

현재 로컬 7개 Gate는 모두 PASS했지만, 원격 Workflow는 아직 적용되지 않았다. 다음 조건이 모두 충족될 때 3.4를 완료한다.

- 주요 계약 경로가 모두 Trigger 대상이다.
- 7개 Gate가 별도 Step으로 자동 실행된다.
- 실제 Branch 또는 PR Run이 전체 PASS한다.
- Data CI와의 중복·장애 대응 책임이 확정된다.
- Run URL과 대상 SHA가 기록된다.
