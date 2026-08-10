# 4주차 Exit Gate

> 검증일: **2026-08-07 KST**
> 코드 기준 Commit: `dad0e7a2c0e6c184ac8811bce6c6974bd7cb3fe0`
> 작업 트리: 3.3·3.6 문서 변경 미커밋
> 종합 판정: **CONDITIONAL_EXIT / WEEK5_BLOCKERS_OPEN**

## 1. 증거 분류

| 분류 | 의미 |
|---|---|
| `RERUN_PASS` | 2026-08-07 현재 작업 트리에서 직접 실행해 통과 |
| `CARRIED_PASS` | 기준 Commit 사이 대상 Source 변경이 없어 이전 Gate 증거를 승계 |
| `BLOCKED` | 환경 또는 선행 Runtime 부재로 실행하지 못함 |
| `NOT_READY` | 구현·통합 증거가 완료 기준에 미달 |

## 2. 최종 Gate 결과

| Gate | 결과 | 판정 | 근거·제한 |
|---|---|---|---|
| Git 코드 기준선 | PASS | `RERUN_PASS` | HEAD `dad0e7a`; 3.3·3.6 문서는 Commit 전 |
| State Machine Validator | PASS | `RERUN_PASS` | Version 1.0.0, 상태 13·이벤트 30·전이 34·Guard 39·Action 23 |
| Mermaid Drift Check | PASS | `RERUN_PASS` | 최신 Mermaid와 입력 계약 일치 |
| Action Crosswalk Validator | PASS | `RERUN_PASS` | Runtime 2·OpenAPI 9·계약 전용 2·Deferred 10, 합계 23 |
| Code Registry Validator | PASS | `RERUN_PASS` | Registry 28·Code 143·상태 13·Action 23·역할 4·방문 상태 7 |
| OpenAPI Validator | PASS | `RERUN_PASS` | YAML 101·Ref 303·Path 22·Operation 23 |
| Example Validator | PASS | `RERUN_PASS` | API 예시 34/34 연결·통합 예시 5·Wrapper 25 |
| Contract Test | 7/7 기존 통과 | `CARRIED_PASS` | `dad0e7a` 반영 전 실행 증거 승계; 현재 Python 환경에 pytest가 없어 재실행하지 못함 |
| Data Test·QA·Finalize | 67/67·QA PASS·Finalize PASS | `CARRIED_PASS` | `e95e633..dad0e7a` 사이 `data/**` 변경 없음 |
| Web Test·Lint·Build | Test 113·Lint·TypeScript·Build PASS | `CARRIED_PASS` | 같은 구간 `web/**` 변경 없음; 상담·방문은 계속 `MOCK_ONLY` |
| Backend Test·Migration | 미실행 | `BLOCKED` | 요구 Python 3.13.13 재현 환경 부재 |
| AI Test·팀 DB pgvector | 미재실행 | `BLOCKED` | AI 가상환경·팀 DB 현재 증거 없음; 과거 95개·12/12는 후보 증거 |
| Mobile Test·APK | 실패 상태 유지 | `BLOCKED` | Core Compile Task의 SDK Platform Provider 값 부재 |
| Backend↔AI 수직 E2E | 없음 | `NOT_READY` | 실제 HTTP·Schema 검증·State Event·DB 저장 증거 없음 |
| 상담·방문 Runtime | 없음 | `NOT_READY` | Operation은 계약·후속 분류, Web은 Mock UI |
| 발표 피드백 정리 | 완료 | `RERUN_PASS` | `week4-midterm-feedback.md`에 분류·우선순위 연결 |

## 3. 2026-08-07 재실행 명령

기존 격리 PyYAML 6.0.3 경로를 사용해 다음 Validator를 실행했다.

```text
python scripts/contracts/validate_state_machine.py
python scripts/contracts/render_state_machine.py --check
python scripts/contracts/validate_contract_crosswalk.py
python scripts/contracts/validate_codes.py
python scripts/contracts/validate_openapi.py
python scripts/contracts/validate_examples.py
```

6개 Validator는 모두 Exit Code 0으로 통과했다. `python -m pytest tests/contract -q`는 기본·번들 Python 모두 pytest가 없어 Test 수집 전에 중단됐으므로 새 PASS로 계산하지 않는다.

## 4. 5주차 선행 해제 항목

| 순서 | 해제 항목 | 책임 | 해제 증거 |
|---:|---|---|---|
| 1 | 3.3·3.6 문서 Commit과 외부 Issue 대조 | 윤승혁·김은진 | 깨끗한 기준 Commit, Issue 링크·담당자 회신 |
| 2 | Backend 공식 환경과 Test·Migration Gate | 최지용·김은진 | Python Version, pytest 집계, Migration Drift |
| 3 | AI Test·팀 DB Vector 검색 재현 | 이동윤·김은진 | Test 집계, Index·검색 평가, 같은 Commit |
| 4 | Backend–AI 최소 수직 연결 | 최지용·이동윤 | HTTP 요청·응답, Schema, Event, DB 저장, 추적 ID |
| 5 | Mobile Build 환경 복구 | 양정현·김은진 | Core·Customer·Technician Test와 APK 결과 |

## 5. Exit 결정

4주차 계약 기준선과 Data·Web의 변경 없는 Gate는 5주차 입력으로 사용할 수 있다. Backend·AI·Mobile 환경과 Backend↔AI·상담·방문 Runtime은 완료되지 않았으므로 전체 통합 PASS로 판정하지 않는다.

따라서 4주차는 **조건부 종료**하며, 5주차는 신규 기능을 동시에 확대하기보다 위 선행 해제 항목부터 처리한다.
