# Context API 병행 Backend 회귀검증 및 후속 인계

> 작성일: 2026-08-20 KST
>
> 작성자: 최지용(Backend·Database)
>
> 목적: AI 내부 Context API 작업과 겹치지 않는 Backend 단독 검증 결과를 기록한다.

## 1. 검증 경계

이번 검증은 작업 중인 Context API 후보를 수정하지 않고 별도 Clean Worktree에서 수행했다.

```text
main_baseline=11f50f4c363d59560d58c7271e3ced6ea873fe0d
clean_worktree=SKN29-FINAL-4TEAM_parallel_20260820
context_api_candidate=1bca409d36bbc1742a74b1c4acf66b67ceca6754
context_api_candidate_in_main=NO
```

- `main@11f50f4c`를 Detached Clean Worktree로 고정했다.
- Context API 후보 `1bca409d`는 검증 기준 main에 포함하지 않았다.
- 기존 작업트리의 수정 문서와 Context API 산출물을 Stash·Merge·수정하지 않았다.
- 공용 DB·RDS·Migration·Seed·Secret은 변경하지 않았다.
- 이번 작업에서 기능 코드 수정은 하지 않았다.

## 2. 검증 결과 요약

| 범위 | 결과 | 정확한 판정 |
| --- | ---: | --- |
| T-023·T-055 상태 전이 | 72 passed | `PASS` |
| T-005·T-047 Backend 기준선 | 73 passed | `PASS` |
| 계약·Action Crosswalk | 12 passed | `PASS` |
| Web G4 Backend Fixture·API | 43 passed | `PASS_CODE_API` |
| Web 상세·Repository 단위 | 11 passed | `PASS_UNIT` |
| Web 목록·Dashboard·전화문의 통합 | 42 passed, 5 skipped | `PASS_COMPONENT` |
| T-024·T-028B Backend 추적·Evidence | 69 passed, 1 skipped | `PASS_CODE`, PG Row Lock 1건 별도 |
| AI RAG Runtime Profile | 7 passed | `PASS_UNIT` |
| AI Retrieval | 35 passed | `PASS_UNIT` |
| Web 실제 Browser·PostgreSQL G4 | 미실행 | `NOT_RUN_ENVIRONMENT_UNAVAILABLE` |
| AI MCP·Harness | 수집 차단 | `BLOCKED_LOCAL_VENV_MISSING_MCP` |
| 실제 OpenAI·53행 View 관통 | 미실행 | `NOT_RUN` |

## 3. Backend 기준선 확인

### 상태 전이

- 완료·재개·상담 요청·고객 Snapshot 관련 72개 회귀가 통과했다.
- State·`state_version`·`allowed_actions`의 기존 계약을 변경하지 않았다.
- 현재 Context API 작업과 겹치는 파일을 수정하지 않았다.

### 공통 Backend·계약

- Django Check: `PASS`
- Migration drift: `No changes detected`
- Backend 권한·인증·Correlation·Schema 표적 73개: `PASS`
- API 계약·Action Operation Crosswalk 12개: `PASS`

## 4. Web G4 확인

### 통과한 범위

- 고유 `run_id` 기반 Web 상담 Fixture와 상담 API 43개가 통과했다.
- Web은 Remote 실패를 Mock 성공으로 바꾸지 않는 Repository 경계를 유지했다.
- 상담 목록·Dashboard·전화문의 통합 42개가 통과했다.
- Web 통합 테스트의 5개 Skip은 테스트가 명시한 조건부 경계이며 실패가 아니다.

### 실제 Browser G4를 실행하지 않은 이유

```text
docker_engine=UNAVAILABLE
postgres_5432=CLOSED
postgres_55432=CLOSED
postgres_55434=CLOSED
```

실제 Browser G4에는 격리 PostgreSQL, Backend Runtime, Demo Seed와 새로운
`run_id`가 필요하다. 현재 PC에는 해당 실행환경이 없으므로 DB를 새로 만들거나
공용 DB·RDS를 임의 변경하지 않았다.

따라서 위 테스트 결과를 실제 Browser G4 PASS 또는 Mobile→AI E2E PASS로 확대하지 않는다.

## 5. T-019·T-020·T-021 종료 상태

| WBS | Backend·독립 QA | 남은 종점 |
| --- | --- | --- |
| T-019 케어 이력 | 완료 | Web·Mobile 실제 소비 결과와 PM WBS 반영 |
| T-020 다음 케어일 | 완료 | PM WBS 완료 반영 |
| T-021 CARE_PRECHECK | 완료 | Mobile 물리기기 소비 결과와 PM WBS 반영 |

- 세 항목 모두 Backend를 처음부터 다시 구현할 필요가 없다.
- T-019·T-021은 소비자 실제 결과가 없으므로 전체 기능 종결로 단정하지 않는다.
- T-020은 구현·정책·PostgreSQL 독립 QA까지 완료된 상태다.

## 6. T-024·T-028B 정적 Gate

### 확인된 것

- RetrievalRun·RetrievalHit 추적 모델 회귀가 통과했다.
- 안전 Evidence Projection과 Evidence Card 준비 회귀가 통과했다.
- 3모델 Evidence Import 코드 회귀가 통과했다.
- Backend AI Handoff 저장·Web Projection 테스트는 현재 main에서 strict xfail이 아니다.
- Backend 관련 표적 테스트는 69 passed, PostgreSQL Row Lock 증거 1건만 Skip이다.
- AI RAG Runtime Profile 7개와 Retrieval 35개가 통과했다.

### 아직 확인되지 않은 것

- 로컬 AI 가상환경에는 저장소가 요구하는 `mcp==2.0.0`이 설치돼 있지 않다.
- 이 때문에 MCP·Harness·AI Handoff 단위 테스트 7개 파일이 수집 단계에서 차단됐다.
- `ai/requirements.txt`, `requirements.lock`, `pyproject.toml`에는 의존성이 이미 선언돼 있다.
- 공유 가상환경을 임의 변경하지 않기 위해 이번 작업에서 설치하지 않았다.
- 실제 OpenAI Provider, 실제 3모델 53행 Readonly View, MCP stdio 관통은 실행하지 않았다.
- F02의 정상 No-Evidence 재시도 0회·1회 선택은 PM 정책 결정 전 변경하지 않는다.

## 7. 담당자별 인계

### 이동윤(AI·RAG)

- 최신 main의 `ai/requirements.lock`으로 격리 AI 가상환경을 동기화한다.
- `mcp==2.0.0` 설치 확인 후 MCP·Harness·Handoff 표적 테스트를 재실행한다.
- 실제 53행 Readonly View와 Provider 환경이 준비되면 실제 Runtime을 검증한다.
- F02는 PM 결정 전 Fixture나 Runtime을 임의 변경하지 않는다.

### 한예나(Web)

- 최신 main에서 고유 `run_id`와 격리 PostgreSQL을 사용해 Browser G4를 실행한다.
- 상담 시작→저장→요약 확정→완료→새로고침 복구와 404·409를 확인한다.
- 공용 DB·RDS와 기존 완료 Inquiry는 재사용하지 않는다.

### 양정현(Mobile)

- 최신 main 기반 APK로 T-019 케어 이력과 T-021 CARE_PRECHECK를 물리기기에서 확인한다.
- Fake 전환 없이 새로운 고객 Flow의 Inquiry·상태·재조회 결과를 전달한다.

### 김은진(QA·DevOps)

- Web Browser 또는 Mobile 물리기기 실행환경이 준비된 뒤 같은 실행 건을 독립 확인한다.
- 이미 완료된 Backend 단위 회귀를 반복하기보다 실제 DB 변경·Correlation·Replay를 확인한다.

### 윤승혁(PM)

- T-020의 공식 WBS 완료 상태를 현행화한다.
- T-019·T-021은 소비자 결과 수신 후 WBS 종결을 판정한다.
- F02 정상 No-Evidence 재시도 정책을 0회 또는 1회로 확정한다.

## 8. 최지용 후속 순서

1. Context API 후보가 main에 병합되면 최신 main에서 해당 API 표적 회귀를 다시 실행한다.
2. 이동윤에게 내부 API URL·인증·입력·응답·오류 계약을 인계한다.
3. Web·Mobile 실제 소비 결과를 수집한다.
4. 같은 실행 건의 DB 변경·Correlation·Replay 증거를 김은진에게 넘긴다.
5. PM에게 T-019·T-020·T-021 WBS 현행화를 요청한다.

## 9. 금지 경계

- 현재 작업 중인 Context API 파일의 임의 수정·Stash·Merge
- 공용 DB·RDS에 개인 Migration·Seed 적용
- 단위·Mock·Health PASS를 실제 Provider 또는 전체 E2E PASS로 확대
- F02 정책을 Backend 또는 AI 담당자가 단독 확정
- T-019·T-021을 소비자 실측 없이 전체 완료 처리

## 10. 최종 판정

```text
backend_regression=PASS
web_component_regression=PASS
web_browser_g4=NOT_RUN_ENVIRONMENT_UNAVAILABLE
backend_trace_evidence_gate=PASS_CODE_WITH_1_PG_SKIP
ai_rag_profile_retrieval=PASS_UNIT
ai_mcp_harness=BLOCKED_LOCAL_VENV_MISSING_MCP
actual_provider_53row_e2e=NOT_RUN
context_api_candidate=EXCLUDED_FROM_THIS_BASELINE
overall=SAFE_TO_CONTINUE_WITH_OWNER_HANDOFFS
```
