# Contract CI 감사 및 운영안

> 감사일: 2026-08-11 KST
> PM 감사 기준: `main@92b0674cd1a3376a2c058715cd5ef32222125755`
> 적용·로컬 검증 기준: `eunjin@88148c97ba727c62fc520104aa20a796d089d10b`
> 현재 판정: **WORKFLOW_LOCAL_PASS · REMOTE_NOT_RUN**
> Workflow 주관: 김은진 / 계약 정책·Validator 주관: 윤승혁

## 1. 결론

기존 `.github/workflows/data-ci.yml`은 State Machine Validator와 Mermaid Drift만
자동 실행한다. 이를 약화하지 않고 별도 `.github/workflows/contracts-ci.yml`을
추가해 전체 계약 변경을 검증하도록 구성했다.

신규 Workflow와 자체 Contract Test는 Local Gate를 통과했다. Commit·Push가 없어
GitHub Actions 원격 결과는 아직 없으며, Data CI의 State·Mermaid 중복은 원격
PASS 전까지 유지한다.

## 2. 현재 Workflow 감사

### 자동 검증 범위

| 필수 Gate | 현재 자동화 | 판정 |
|---|---|---|
| `validate_state_machine.py` | Data CI·Contract CI | LOCAL PASS |
| `render_state_machine.py --check` | Data CI·Contract CI | LOCAL PASS |
| `validate_codes.py` | Contract CI에 추가 | LOCAL PASS |
| `validate_openapi.py` | Contract CI에 추가 | LOCAL PASS |
| `validate_examples.py` | Contract CI에 추가 | LOCAL PASS |
| `validate_contract_crosswalk.py` | Contract CI에 추가 | LOCAL PASS |
| `pytest tests/contract -q` | Contract CI에 추가 | `38 passed` |

### Trigger 범위

| 변경 경로 | 현재 Trigger | 요구 상태 |
|---|---|---|
| `contracts/**` | Contract CI에 추가 | API·AI·State·Code·Example·Error·Changelog 전체 포함 |
| `scripts/contracts/**` | Contract CI에 추가 | Validator·Renderer 변경 포함 |
| `tests/contract/**` | Contract CI에 추가 | Root 계약 회귀 포함 |
| `.github/workflows/contracts-ci.yml` | Contract CI에 추가 | Workflow 자체 변경 시 실행 |

`contracts/CHANGELOG.md`에는 `contracts/**`, `scripts/contracts/**`, `tests/contract/**`
변경 시 전체 계약 Gate가 실행된다고 적혀 있었으나 기존 Workflow와 일치하지
않았다. 신규 Workflow로 Trigger를 정렬했으며 원격 실행 확인만 남았다.

## 3. 적용 Workflow

각 검사를 별도 Step으로 두어 실패 원인이 로그 이름에서 바로 드러나게 했다.
Root Contract Test가 실제로 import하는 `jsonschema`를 깨끗한 Runner에도 명시하고,
Backend Python Constraints로 최소 의존성을 고정한다.

```yaml
name: Contract CI

on:
  workflow_dispatch:
  pull_request:
    paths:
      - "contracts/**"
      - "scripts/contracts/**"
      - "tests/contract/**"
      - ".github/workflows/contracts-ci.yml"
  push:
    paths:
      - "contracts/**"
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
          python-version: "3.13.13"
          cache: "pip"
          cache-dependency-path: |
            backend/requirements/base.txt
            backend/requirements/local.txt
            backend/requirements/constraints-py313.txt

      - name: Install contract gate dependencies
        run: >-
          python -m pip install
          --constraint backend/requirements/constraints-py313.txt
          PyYAML==6.0.3 jsonschema==4.26.0 pytest==9.1.1

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

1. 김은진 Branch에 별도 Contract CI와 자체 검증 Test를 적용한다. **완료**
2. 로컬에서 7개 Gate를 같은 HEAD로 실행한다. **완료**
3. Workflow 파일 자체가 Trigger 경로에 포함된 Branch 또는 PR에서 최초 실행을 확인한다. **미실행**
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

현재 로컬 7개 Gate와 Workflow 자체 Test는 PASS했지만 Workflow는 아직
Commit·Push되지 않았다. 다음 조건이 모두 충족될 때 3.4를 완료한다.

- 주요 계약 경로가 모두 Trigger 대상이다.
- 7개 Gate가 별도 Step으로 자동 실행된다.
- 실제 Branch 또는 PR Run이 전체 PASS한다. **현재 `REMOTE_NOT_RUN`**
- Data CI와의 중복·장애 대응 책임이 확정된다.
- Run URL과 대상 SHA가 기록된다.

### 2026-08-11 로컬 결과

| Gate | 결과 |
|---|---|
| State Machine | PASS — State 13, Event 30, Transition 34, Guard 39 |
| Mermaid Drift | PASS |
| Code Registry | PASS — Registry 28, Code 144, Action 23 |
| OpenAPI | PASS — Path 32, Operation 33 |
| Example | PASS — API 50/50, Integration 5, Wrapper 33 |
| Crosswalk | PASS — Runtime 12, OpenAPI-only 7, Deferred 4 |
| Root Contract | `38 passed` |

현재 상태는 `LOCAL_PASS_REMOTE_NOT_RUN`이며 원격 Run URL은 없다.
