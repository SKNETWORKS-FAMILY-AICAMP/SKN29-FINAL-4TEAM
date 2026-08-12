# 5주차 Contract Baseline 실행 결과

> 실행일: 2026-08-11 14:21 KST
> 계약 검증 기준: `main@92b0674cd1a3376a2c058715cd5ef32222125755`
> 현재 작업 기준: `main@2a1b308ed5eae8bdbaec57ee6026f14529b10794`
> 판정: **REMOTE_CONTRACT_PASS · CONSUMER_REVALIDATION_REQUIRED**

## 1. 결론

최초 기준의 정적 계약과 Root Contract Test는 모두 통과했다. Backend 의미 불일치 두 건은 `e290fe3`에서 작성자 수정됐고 원격 Contract CI·Data CI도 통과했다. 다만 후속 고객 Snapshot 계약 적용과 현재 후보의 독립 QA·소비자 ACK가 남아 `TEAM_BASELINE`으로 최종 폐쇄하지 않는다.

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
| 현행 검증 기준 | `92b0674cd1a3376a2c058715cd5ef32222125755` | 위 변경과 Mobile 병합이 포함된 현재 `main` |

현재 Crosswalk는 23개 Action 중 Runtime 12개, OpenAPI-only 7개, Deferred 4개다. 대표 8개 Action은 모두 OpenAPI에 연결됐으며 `SUBMIT_ANSWERS`만 Runtime 구현, 나머지 7개는 OpenAPI-only다.

## 4. 변경 영향과 최종 폐쇄 조건

- State·Event·Transition·Guard 의미와 State Machine `1.0.0`은 바뀌지 않았다.
- Backend는 Event·Version·권한·멱등성·409 의미를 확인해야 한다.
- AI는 State를 직접 바꾸지 않고 Event·Schema·Fallback 경계를 확인해야 한다.
- Web·Mobile은 서버의 상태와 `allowed_actions`를 소비하고 Date·Error 의미를 자체 변형하지 않아야 한다.
- QA는 현재 기준 Commit의 Contract Test·Fixture·Gate 재현성을 확인해야 한다.

다섯 소비자 검토가 모두 승인되고 증거가 기록된 뒤 최종 문서 Commit을 새 기준 Commit으로 기록한다. 그전까지 기계 계약의 `PM_BASELINE_CANDIDATE`를 임의로 `TEAM_BASELINE`으로 변경하지 않는다.

## 5. Backend 의미 불일치

- 정적 Crosswalk 수치 `12/7/0/4`와 Test PASS는 유지되지만, `CANCEL_INQUIRY`의 승인 역할·상태 전체가 Runtime에 구현되지 않았다.
- `allowed_actions`가 계약의 Visit·Transition·Domain Guard와 Runtime availability를 평가하지 않는다.
- 이 불일치는 Validator 수치로 발견되지 않는 Runtime 소비 결함이었다.
- 최초 PM 결정: `docs/decisions/Backend Contract 소비 불일치 PM 결정.md`

## 6. Backend 수정 이후 재판정

- Runtime 수정 `e290fe3`과 작성자 후보 `83f7373`은 현재 `main@4ac79e6`에 포함된다.
- 후보 이후 현재 main까지 Contract·Validator·Contract CI Workflow Diff는 없다.
- 원격 Contract CI와 Data CI는 작성자 후보에서 PASS했다.
- 작성자 검증은 취소·Resolver 수정의 기술 후보 증거로 인정한다.
- `submitSymptom` AI 경계, 재방문 일정 전이, 고객 Snapshot 동적 `allowed_actions` 후속 적용이 필요하다.
- 기존 QA ACK는 변경 전 `92b0674` 기준이므로 현재 최종 후보에서 재검증한다.
- PM 후속 결정: `docs/decisions/Backend Runtime12 후속 계약 PM 결정.md`

## 7. 2026-08-12 소비자 재판정

- Backend Runtime12는 `e146d23` 독립 QA `APPROVE`로 Backend ACK를 승인했다.
- QA는 Runtime12 표적 98건, Backend 전체 1004건, PostgreSQL Row Lock 5건과 Migration Drift 없음으로 승인됐다.
- Mobile·Backend·QA의 소비자 ACK를 인정해 현재 `3/5`다.
- AI No-Evidence Runtime 병합은 `origin/dongyoon@692ccd5`를 승인했으며 main 반영 전까지 AI ACK에는 포함하지 않는다.
- Web 현재 기준선 ACK와 최종 후보 전체 Contract Gate가 남아 `TEAM_BASELINE`은 계속 `HOLD`다.
