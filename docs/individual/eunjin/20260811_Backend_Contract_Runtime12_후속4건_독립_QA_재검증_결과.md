# Backend Contract Runtime 12 후속 4건 독립 QA 재검증 결과

> 검토자: 김은진 — 데이터·QA·DevOps
>
> 검토일: 2026-08-11 KST
>
> 기준 Commit: `e146d2349d82c964ca57baa4c77b501f8e84c1ab`
>
> 비교 Base: `4dbf7c0e225757f193b8f326bd97b73edaed959e`
>
> 판정: `APPROVE`

이 판정은 위 고정 Commit의 재검증 요청 4건과 지정 Gate에 한정한다. 이후 Commit, Team Baseline 승인 또는 배포 승인을 뜻하지 않는다.

## 1. 김은진 역할에서 수행한 변경

- 현재 작업 트리를 전환하지 않고 후보 SHA의 detached worktree를 별도로 만들었다.
- Python 3.13.13과 공식 bootstrap으로 후보 전용 `backend/.venv`를 구성하고 환경 fingerprint를 검증했다.
- 계약 Validator·렌더 정합성·Root 계약 테스트, 지정 표적 8개, Django check, Migration drift, Backend 전체 회귀를 실행했다.
- 수정 작성자의 회귀만 재사용하지 않고 Git에서 무시되는 임시 QA 모듈로 후속 4건을 독립 검증했다.
- fresh PostgreSQL 16 + pgvector 0.8.6 일회용 컨테이너에서 전체 Migration과 row-lock 표적 5건을 실행했다.
- Backend·Contract·Backend Test Source는 수정하지 않았다. 임시 QA 모듈과 컨테이너는 검증 후 제거했다.

### 요구사항별 판정

| 후속 항목 | 판정 | 독립 검증 근거 |
|---|---|---|
| Cancel History canonical 사유 | PASS | 상세 사유는 trim 후 `CUSTOMER_REQUEST | Independent QA detail.`, 누락·`None`·빈 문자열·공백은 `CUSTOMER_REQUEST`만 저장됨. Actor·Correlation·Idempotency·실제 상태·Version도 유지됨 |
| `submitSymptom` `transaction.on_commit` 경계 | PASS | 성공 Transaction 내부 AI 0회, 등록 Callback 1개, Callback 실행 후 AI 1회, 동일 Replay의 Callback·AI 추가 호출 0회 |
| TR-INQ-028 재방문 일정 재설정 | PASS | `REVISIT_REQUIRED/FOLLOW_UP_REQUIRED`에서 `VISIT_SCHEDULING/SCHEDULING`으로 전이, 방문 lifecycle 필드 초기화, 기존 `VisitResult` 전체 값 불변, Replay 추가 변경 0 |
| Customer Snapshot 동적 `allowed_actions` | PASS | 질문 없음은 `CANCEL_INQUIRY`, 지원되는 미응답 질문 추가 시 `SUBMIT_ANSWERS` 추가, 답변 후 제거, 미지원 질문만 있을 때 노출하지 않음 |

## 2. 변경 파일과 관할 근거

- 추가: `docs/individual/eunjin/20260811_Backend_Contract_Runtime12_후속4건_독립_QA_재검증_결과.md`
- `docs/**`는 모든 팀원의 공동 편집 영역으로 김은진 직접 편집 범위다.
- 검증용 `.codex_work/**`, `backend/.venv`, `backend/.runtime/qa/**`는 Git 제외 영역이다.
- `backend/**`, `contracts/**`, `backend/tests/**`의 추적 파일은 변경하지 않았다.

## 3. 실행한 데이터·QA·CI 검증과 결과

### 후보·환경 Gate

| 검증 | 결과 |
|---|---|
| 후보 게시·고정 | `e146d2349d82c964ca57baa4c77b501f8e84c1ab` 존재, Base의 descendant 확인 |
| 후보 Range whitespace | `git diff --check 4dbf7c0... e146d234...` exit 0 |
| 장기 검증 SHA | 전체 회귀 시작·종료 모두 후보 SHA와 일치 |
| 장기 검증 tracked 상태 | 전체 회귀 시작·종료 dirty count 0 |
| Python / pip / Django | 3.13.13 / 26.0.1 / 5.2.16 |
| 환경 fingerprint | `69a9173c1beac40b596585eb1e9f232d3d7b4d66962c4cbdd45180cc3a3aff78` 일치 |
| 의존성 Gate | 고정 패키지 32개 일치, 추가 패키지 0개, `pip check` PASS, 환경 failure·warning 0 |

### 계약·회귀 Gate

| 검증 | 결과 | Exit |
|---|---:|---:|
| State Machine Validator | PASS — State 13, Event 30, Transition 34, Guard 39, Action 23 | 0 |
| State Machine Mermaid check | PASS — 산출물 최신, State 13, Transition 34 | 0 |
| Contract Crosswalk | PASS — Runtime 12, OpenAPI 7, Deferred 4, Contract-only 0 | 0 |
| OpenAPI Validator | PASS — YAML 108, Ref 436, Path 32, Operation 33 | 0 |
| Contract Example Validator | PASS — API 50, Integration 5, Wrapped response 33 | 0 |
| Code Registry Validator | PASS — Registry 28, Code 144 | 0 |
| Root 계약 테스트 | 38 passed, 0 failed | 0 |
| 지정 표적 8개 | 98 passed, 0 failed, 5 PostgreSQL-only skipped | 0 |
| 독립 QA Probe 4건 | 4 passed, 0 failed, 0 skipped | 0 |
| Django system check | No issues | 0 |
| Migration drift | No changes detected | 0 |
| Backend 전체 회귀 | 1004 passed, 0 failed, 19 skipped | 0 |

표적 테스트의 최초 실행은 QA가 요청서 경로의 `api/`, `unit/workflow/` 하위 경로를 수기 전사하면서 누락해 `0 tests`, pytest exit 4로 종료됐다. 요청서 원문과 실제 파일 경로를 다시 확인해 동일 8개 대상을 교정 실행했으며, Test Harness 오류이므로 제품 FAIL로 집계하지 않았다.

### 실제 PostgreSQL Gate

- 로컬 고정 이미지: `pgvector/pgvector:0.8.6-pg16-bookworm`
- PostgreSQL: 16.14
- pgvector: 0.8.6
- 기존 DB가 아닌 fresh 일회용 QA DB를 `127.0.0.1:55433`에만 임시 바인딩했다.
- fresh DB Migration Plan 확인, 전체 Migration 적용, `migrate --check`: PASS
- 지정 row-lock·동시성 표적: 5 passed, 0 failed, 0 skipped, exit 0
- 자동 Test DB 잔존 수: 0
- QA Container 잔존 수: 0
- 기존 Container·DB·Volume은 변경하지 않았다.

### 요청 회신 형식

```text
reviewer=김은진
reviewed_commit=e146d2349d82c964ca57baa4c77b501f8e84c1ab
qa_decision=APPROVE
environment=Windows NT 10.0.26200.0/Python 3.13.13/Django 5.2.16/PostgreSQL 16.14/pgvector 0.8.6
contract_validators=PASS/6 commands + Root 38 passed/exit 0
targeted_tests=98 passed/0 failed/5 skipped/exit 0; independent probes=4 passed/0 failed/0 skipped/exit 0
backend_regression=1004 passed/0 failed/19 skipped/exit 0
postgresql_row_lock=5 passed/0 failed/0 skipped/exit 0
cancel_change_reason_with_detail=PASS
cancel_change_reason_without_detail=PASS
cancel_inquiry_fields_preserved=YES
cancel_replay_additional_history_count=0
submit_on_commit_boundary=PASS
submit_replay_additional_ai_call_count=0
update_visit_tr_inq_028=PASS
revisit_result_preserved=YES
customer_snapshot_allowed_actions=PASS
migration_drift=NONE
failed_test_ids=NONE
blockers=NONE
evidence_paths=docs/individual/eunjin/20260811_Backend_Contract_Runtime12_후속4건_독립_QA_재검증_결과.md
```

## 4. 실행하지 못한 검증과 이유

- 재검증 요청서가 필수로 지정한 계약·표적·전체 회귀·Migration drift·PostgreSQL 5건은 모두 실행했다.
- 외부 LLM Provider 실제 호출과 Backend-AI actual-socket 테스트는 이번 후속 4건의 완료 조건이 아니며 별도 Provider Key·AI 서비스가 필요하므로 실행하지 않았다.
- 전체 회귀에서 제외된 나머지 PostgreSQL 전용 구조 검사, TEAM_INTEGRATION Role 검증은 이번 요청의 지정 PostgreSQL 5건이 아니므로 별도 집계하지 않았다. 다만 fresh PostgreSQL 전체 Migration은 성공했다.

## 5. 발견했지만 수정하지 않은 관할 밖 문제

- 후보 SHA에서 재검증 요청 4건과 지정 Gate를 막는 Backend·Contract 결함은 재현되지 않았다.
- Backend Runtime과 `backend/tests/**`는 최지용 주관 영역이므로 QA 판정 외 수정은 하지 않았다.

## 6. 필요한 담당자 인계

### 최지용 — Backend 담당

- 고정 후보 `e146d234...`는 이번 후속 4건 독립 QA 기준 `APPROVE`다.
- 이후 Backend 변경이 후보에 추가되면 이 결과를 재사용하지 말고 새 SHA에서 회귀해야 한다.

### 윤승혁 — 계약 Owner / Team Baseline 담당

- 본 결과를 Contract·Backend 소비 ACK와 Team Baseline 판단 자료로 사용하되, QA `APPROVE`를 자동 Baseline 승인으로 해석하지 않는다.

## 7. 남은 위험과 확인 필요 항목

- 실제 외부 AI Provider·actual-socket 경계는 이번 검증에서 확인하지 않았다.
- 재방문 일정 재설정은 지정 Runtime 회귀와 독립 Probe, fresh PostgreSQL Migration으로 확인했지만 별도 다중 요청 동시성 시나리오는 요청 범위가 아니었다.
- 이 증거는 정확히 `e146d234...`에만 유효하다. 후속 Commit 또는 환경 조합이 달라지면 다시 검증해야 한다.
