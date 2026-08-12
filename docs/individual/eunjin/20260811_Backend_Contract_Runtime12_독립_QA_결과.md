# Backend Contract Runtime 12 독립 QA 결과

> 검토자: 김은진 — 데이터·QA·DevOps
>
> 검토일: 2026-08-11 KST
>
> 고정 검토 Commit: `83f737326de75a6015a606c0050eaa81d1f67a4f`
>
> 판정: `CHANGE_REQUEST`

## 1. 김은진 역할에서 수행한 변경

- 현재 `eunjin` 작업 트리를 전환하지 않고, 고정 SHA의 detached Git worktree를 만들어 검증했다.
- 고정 SHA 전용 `backend/.venv`를 Python 3.13.13과 공식 bootstrap으로 새로 구성했다.
- 계약 검증기, Root 계약·안전 테스트, Runtime 12 표적 테스트, Backend 전체 회귀를 실행했다.
- 로컬 전용 일회성 PostgreSQL 16 + pgvector 컨테이너에서 Migration 왕복과 동시성·Row Lock 테스트를 실행했다.
- 기존 테스트가 직접 확인하지 않던 미존재 UUID, 잘못된 Version, cross-target Idempotency와 AI 부작용 경계를 임시 QA 모듈로 확인했다.
- 요구사항 2의 Transition History 취소 사유를 별도 임시 QA 모듈로 확인했고, `change_reason=None` 실패를 재현했다.
- Backend·Contract Runtime Source는 수정하지 않았다. 임시 QA 모듈과 컨테이너는 종료 후 제거했다.

## 2. 변경 파일과 관할 근거

- 추가 문서: `docs/individual/eunjin/20260811_Backend_Contract_Runtime12_독립_QA_결과.md`
- `docs/**`는 모든 팀원의 공동 편집 영역이므로 김은진 직접 편집 범위다.
- `backend/**`, `contracts/**`, `backend/tests/**`는 수정하지 않았다.
- 검증용 `backend/.venv`, `backend/.runtime/qa/**`와 detached worktree는 Git 제외 영역이며 검증 대상 Commit의 tracked diff를 만들지 않았다.

## 3. 요구사항 분석과 판정

| 요구사항 | 판정 | 독립 QA 근거 |
|---|---|---|
| 고객 본인·담당 상담사·권한 운영자의 DRAFT/QIP 취소 | PASS | 3 Role × 2 State 성공, 미배정 상담사·무권한 운영자·기사 거부 확인 |
| 실제 이전 상태·증가 Version·사유·Actor·Correlation History | **FAIL** | 이전/이후 상태·Version·Actor·Correlation은 일치했으나 `TransitionHistory.change_reason`이 `None` |
| Replay, 다른 Payload/Target 409, 추가 Write·AI Side Effect 0 | PASS | SQLite 경계 Probe와 PostgreSQL 동시성 4건에서 중복 Transition·History 없음. cross-target 409에서 대상의 QUEUED AIRun이 변경되지 않음 |
| State Machine·Guard·Crosswalk 기반 `allowed_actions` | PASS | State Machine·Crosswalk 검증기와 Resolver 표적 테스트 통과, Runtime 미구현 Action 필터 확인 |
| 성공과 stale 409의 Snapshot·Resolver 일치 | PASS | Cancel 및 Consultation 성공/409 Snapshot 결과와 공통 Resolver 경로 확인 |
| 취소와 늦은 AI 성공·실패 경쟁 시 상태·Projection 보호 | PASS | 성공·실패 Mock 경로에서 Inquiry CANCELLED 유지, Assessment·Guidance·Question 추가 0 확인 |

### 변경 요청 결함

독립 Probe는 취소 API 200 응답 뒤 History를 조회해 다음 순서로 확인했다.

1. `history.actor_id == owner.pk` — PASS
2. `history.correlation_id == response.metadata.correlation_id` — PASS
3. `history.change_reason is not None` — FAIL, 실제 값 `None`

최초 Root Assertion:

```text
FAILED backend/.runtime/qa/test_runtime12_cancel_history_metadata.py::test_cancel_history_preserves_actor_correlation_and_reason
E assert None is not None
E where None = TransitionHistory.change_reason
```

확인된 원인은 다음과 같다.

- `backend/apps/inquiries/services/inquiry_service.py`는 `Inquiry`에 `reason_code`와 `reason_detail`을 저장한 뒤 History 기록을 호출한다.
- `backend/apps/workflow/services/transition_history_service.py`의 `record_cancel_inquiry()`는 취소 사유 인자를 받지 않는다.
- `backend/apps/workflow/repositories/workflow_repository.py`의 `create_transition_history()`는 `change_reason`을 전달하거나 저장하지 않는다.
- 기존 `backend/tests/api/test_t023_cancel_inquiry.py`는 Inquiry 취소 사유와 History 상태·Version을 각각 확인하지만 History 사유는 확인하지 않는다.

## 4. 실행한 데이터·QA·CI 검증과 결과

### 환경 Gate

- OS: Microsoft Windows NT 10.0.26200.0
- Python: 3.13.13
- pip: 26.0.1
- Django: 5.2.16
- constraints 고정 패키지: 32개 일치
- constraints 밖 추가 패키지: 0개
- requirements fingerprint: 일치
- `pip check`: PASS
- Django system check: PASS

### 계약·표적·전체 회귀

| 검증 | 결과 | Exit |
|---|---:|---:|
| State Machine validator | PASS — State 13, Event 30, Transition 34, Guard 39, Action 23 | 0 |
| Contract Crosswalk validator | PASS — Runtime 12, OpenAPI 7, Deferred 4, Contract-only 0 | 0 |
| OpenAPI validator | PASS — YAML 108, Ref 435, Path 32, Operation 33 | 0 |
| Example validator | PASS — API 50, Integration 5, Wrapped response 33 | 0 |
| Code Registry validator | PASS — Registry 28, Code 144 | 0 |
| Root Contract·Safety | 42 passed, 0 failed | 0 |
| Runtime 12 표적 | 128 passed, 5 PostgreSQL-only skipped, 0 failed | 0 |
| Django check | No issues | 0 |
| Migration drift | No changes detected | 0 |
| Backend 전체 회귀 | 993 passed, 19 skipped, 0 failed | 0 |
| 추가 경계 Probe | 4 passed — UUID masking, invalid Version write 0, cross-target 409, AI side effect 0 | 0 |
| History 사유 Probe | 1 failed — `change_reason=None` | 1 |

전체 회귀 시작·종료 SHA는 동일한 `83f737326de75a6015a606c0050eaa81d1f67a4f`였고, 시작·종료 dirty count는 모두 0이었다.

### PostgreSQL

- 이미지: `pgvector/pgvector:0.8.6-pg16-bookworm` 로컬 고정 이미지
- PostgreSQL: 16.14
- pgvector: 0.8.6
- 네트워크: `127.0.0.1:55432`만 임시 바인딩
- fresh DB Migration Plan 확인 후 전체 적용 및 `migrate --check`: PASS
- `inquiries.0012` 적용 → `0011` 역방향 → `0012` 재적용 → 미적용 0: PASS
- Cancel Runtime + Contract: 25 passed, 0 skipped, 0 failed
- 필수 PostgreSQL Row Lock·동시성: 5 passed, 0 skipped, 0 failed
- 자동 Test DB 잔존 수: 0
- QA Container 잔존 수: 0
- 기존 Container·DB·Volume은 변경하지 않았다.

## 5. 실행하지 못한 검증과 이유

- 요청서의 계약·표적·전체·PostgreSQL 필수 검증은 모두 실행했다.
- 외부 LLM Provider 호출과 실제 AI 서비스 Socket은 이번 요청의 완료 조건이 아니며 Provider Key·별도 서비스가 필요하므로 실행하지 않았다. AI 취소 경쟁은 Mock HTTP Runtime 테스트로 확인했다.
- Data CI 동등 Gate는 작성자 가이드에는 있으나 독립 QA 요청서의 필수 명령에는 포함되지 않아 이번 판정 집계에서 실행하지 않았다.

## 6. 발견했지만 수정하지 않은 관할 밖 문제

1. `CANCEL_INQUIRY` History의 `change_reason` 누락
   - 판정 영향: 요구사항 2 FAIL, `CHANGE_REQUEST`
   - Backend Runtime과 `backend/tests/**`는 최지용 주관 영역이므로 수정하지 않았다.
2. 후보 범위 `5669960...83f7373`에 대한 `git diff --check`는 exit 2다.
   - `docs/testing/rag/d01-evidence-match-policy-contract.md:3`의 Markdown hard-break 공백이 trailing whitespace로 탐지된다.
   - Backend Runtime 기능 실패는 아니지만 작성자 가이드의 Git whitespace PASS를 후보 Range 기준으로 재현할 수 없다.

## 7. 필요한 담당자 인계

### 최지용 — Backend 담당

- 다음 파일에서 취소 사유를 동일 Transaction의 Transition History에 기록하도록 수정이 필요하다.
  - `backend/apps/inquiries/services/inquiry_service.py`
  - `backend/apps/workflow/services/transition_history_service.py`
  - `backend/apps/workflow/repositories/workflow_repository.py`
- `backend/tests/api/test_t023_cancel_inquiry.py`에 최소한 취소 History의 Actor, Correlation, `change_reason`을 함께 확인하는 회귀가 필요하다.
- 사유 코드·상세를 단일 `change_reason`에 어떤 canonical 형식으로 저장할지는 계약 Owner와 확인해야 한다. QA가 임의 형식을 확정하지 않는다.

### 윤승혁 — 계약 Owner

- `reason_code`와 선택적 `reason_detail`을 History `change_reason`에 저장하는 canonical 표현을 확정해야 한다.
- 작성자 가이드에 남은 `submitSymptom` AI 호출 설명과 `updateVisitSchedule` Transition Rule 정합성도 별도 ACK가 필요하다.

## 8. 남은 위험과 확인 필요 항목

- History 사유 수정 후 같은 고정 후보 또는 새 고정 SHA에서 계약·표적·전체·PostgreSQL Gate를 다시 실행해야 한다.
- History 사유가 개인정보성 자유문을 포함할 수 있으므로, 저장 필요 범위와 로그 비노출 정책을 함께 확인해야 한다.
- 현재 판정은 Backend Runtime 12 독립 QA이며 Backend 소비 ACK와 Team Baseline 승인을 의미하지 않는다.

## 9. 요청 회신 형식

```text
reviewer=김은진
reviewed_commit=83f737326de75a6015a606c0050eaa81d1f67a4f
qa_decision=CHANGE_REQUEST
environment=Windows NT 10.0.26200.0/Python 3.13.13/Django 5.2.16/PostgreSQL 16.14/pgvector 0.8.6
contract_validators=PASS/5 validators + Root 42 passed/exit 0
targeted_tests=128 passed/0 failed/5 skipped/exit 0; independent boundary 4 passed/exit 0; history reason 0 passed/1 failed/exit 1
backend_regression=993 passed/0 failed/19 skipped/exit 0
postgresql_row_lock=5 passed/0 failed/0 skipped/exit 0
cancel_roles_states=PASS
idempotency_409=PASS
success_409_parity=PASS
ai_cancel_race=PASS
migration_roundtrip=PASS
failed_test_ids=backend/.runtime/qa/test_runtime12_cancel_history_metadata.py::test_cancel_history_preserves_actor_correlation_and_reason
blockers=CANCEL_INQUIRY TransitionHistory.change_reason is None
evidence_paths=docs/individual/eunjin/20260811_Backend_Contract_Runtime12_독립_QA_결과.md
```
