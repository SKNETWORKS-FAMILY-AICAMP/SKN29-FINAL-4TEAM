# 5주차 Contract Baseline 실행 결과

> 실행일: 2026-08-11 12:36 KST
> 계약 검증 기준: `main@801f58e1512dfc9e12299465b6551fff2a276e3a`
> 판정: **VALIDATOR_PASS · CONSUMER_ACK_PENDING**

## 1. 결론

계약 자체와 Root Contract Test는 모두 통과했다. 다만 Backend·AI·Web·Mobile·QA의 현재 Commit 소비 증거가 아직 모이지 않았으므로 `TEAM_BASELINE`으로 최종 폐쇄하지 않는다.

## 2. 실행 결과

| Gate | 결과 | 현재 수치 |
|---|---|---|
| State Machine Validator | PASS | State 13, Event 30, Transition 34, Guard 39, 외부 Action 23, 대표 단계 14 |
| Mermaid 최신성 | PASS | State 13, Transition 34 |
| Code Registry Validator | PASS | 파일 28, Code 144, Inquiry 상태 13, Workflow Action 23, Role 4, Visit 상태 7 |
| OpenAPI Validator | PASS | YAML 108, Ref 434, Path 32, Operation 33 |
| Example Validator | PASS | API JSON 50/50, Integration 5, Wrapped Response 33 |
| Action Crosswalk Validator | PASS | Runtime 12, OpenAPI-only 7, Contract-only 0, Deferred 4 |
| Root Contract Test | PASS | 12 passed |

실행 명령은 다음과 같다.

```text
python -B scripts/contracts/validate_state_machine.py
python -B scripts/contracts/render_state_machine.py --check
python -B scripts/contracts/validate_codes.py
python -B scripts/contracts/validate_openapi.py
python -B scripts/contracts/validate_examples.py
python -B scripts/contracts/validate_contract_crosswalk.py
python -B -m pytest tests/contract -q -p no:cacheprovider
```

모든 명령의 Exit Code는 `0`이다.

## 3. 계약·Runtime 연결 이력

| 구분 | Commit | 의미 |
|---|---|---|
| 8개 Action 계약 적용 | `264dfdf951f9a1853594cf36fab142a6929475d6` | OpenAPI 0.8 경계 적용 |
| 상담·방문 Runtime | `a9bac6be5aff3494313bfe0d31b83b0f4ddec05b` | 상담·방문 P0 Runtime과 회귀검증 |
| 추가답변 Runtime | `52a141e3ec5fef9c71eb59df8c0847a73138f4b2` | `SUBMIT_ANSWERS` Runtime과 API 계약 |
| 현행 검증 기준 | `801f58e1512dfc9e12299465b6551fff2a276e3a` | 위 변경이 포함된 현재 `main` |

현재 Crosswalk는 23개 Action 중 Runtime 12개, OpenAPI-only 7개, Deferred 4개다. 대표 8개 Action은 모두 OpenAPI에 연결됐으며 `SUBMIT_ANSWERS`만 Runtime 구현, 나머지 7개는 OpenAPI-only다.

## 4. 변경 영향과 최종 폐쇄 조건

- State·Event·Transition·Guard 의미와 State Machine `1.0.0`은 바뀌지 않았다.
- Backend는 Event·Version·권한·멱등성·409 의미를 확인해야 한다.
- AI는 State를 직접 바꾸지 않고 Event·Schema·Fallback 경계를 확인해야 한다.
- Web·Mobile은 서버의 상태와 `allowed_actions`를 소비하고 Date·Error 의미를 자체 변형하지 않아야 한다.
- QA는 현재 기준 Commit의 Contract Test·Fixture·Gate 재현성을 확인해야 한다.

다섯 소비자 검토가 모두 승인되고 증거가 기록된 뒤 최종 문서 Commit을 새 기준 Commit으로 기록한다. 그전까지 기계 계약의 `PM_BASELINE_CANDIDATE`를 임의로 `TEAM_BASELINE`으로 변경하지 않는다.
