# Backend·AI G1-B 독립 QA 결과

- 검증 일시: 2026-08-13 KST
- `reviewed_commit=99dcfbd178c51e0ab76446d8f88459ae2daa5ca2`
- `qa_decision=ENVIRONMENT_BLOCKED`
- 기준 Branch: `eunjin`에서 `origin/main`을 fast-forward 반영
- 검증 경계: Backend·AI G1-B Audit, Provisioning 단위 검증, PostgreSQL Role 통합 검증

## 1. 김은진 역할에서 수행한 변경

- 원격 `main`을 조회하고 `b4dbddbde1c5fe3fa57ab30e2d62d0b324bf2dce`가 포함된 것을 확인했다.
- `git pull --ff-only origin main`으로 `eunjin`을 `99dcfbd178c51e0ab76446d8f88459ae2daa5ca2`까지 fast-forward했다.
- 사용자 범위에 Python `3.13.13`을 설치하고 공식 Bootstrap `--recreate`로 `backend/.venv`를 재생성했다.
- Bootstrap이 생성한 기존 venv 백업은 전체 Gate가 종료될 때까지 보존했다.
- 이번 재검증에서 제품 Runtime, Migration, 계약, Provisioning 코드는 수정하지 않았다.
- 동기화 전부터 있던 Audit 스크립트의 로컬 공백 1줄 변경은 수정·정리하지 않았다.
- 기존 미추적 문서 `docs/testing/week5/20260813-eunjin-p0-e2e-execution-plan.md`는 수정·이동하지 않았다.

## 2. 변경 파일과 관할 근거

- 본 결과 문서만 추가했다.
- `docs/**`는 AGENTS.md상 모든 팀원의 공동 편집 영역이다.
- `backend/.venv`와 `backend/.runtime/venv-backups/**`는 로컬 환경·백업 산출물이며 저장소 변경 파일에 포함되지 않는다.

## 3. 실행한 데이터·QA·CI 검증과 결과

### 기준 Commit 고정

| 항목 | 결과 |
| --- | --- |
| 원격 `main` | `99dcfbd178c51e0ab76446d8f88459ae2daa5ca2` |
| Audit Commit의 `origin/main` 포함 | YES, ancestor check Exit 0 |
| Pull 방식 | Fast-forward 성공 |
| 검증 시작·종료 HEAD | 동일 |
| `HEAD == origin/main` | TRUE |
| 결과 문서 갱신 전 tracked worktree | DIRTY — 기존 Audit 공백 1줄 변경 보존 |

### 필수 명령

| Gate | Exit Code | 결과 |
| --- | ---: | --- |
| Backend venv Python | 0 | Python `3.13.13` |
| `pip check` | 0 | Broken Requirement 0건 |
| Backend Environment Gate | 0 | failures=0, warnings=0, fingerprint 일치 |
| G1-B 강제 Audit, 팀 DB명 Process 주입 | 1 | `AUDIT_FAILED`, `ConnectionTimeout` |
| Audit·Provisioning 단위 Test | 0 | `25 passed in 0.18s` |
| PostgreSQL Role 통합 Test | 1 | `1 failed in 0.20s`, Skip 0건 |

Audit은 venv 복구 후 실행됐지만 PostgreSQL 연결 Timeout으로 Snapshot을 수집하지 못했다.
최종 Audit 상태는 `AUDIT_FAILED`, Exit Code는 `1`이다. 원본 연결 오류와 연결 값은
출력·기록하지 않았다.

### 실측 결과

| 항목 | 결과 |
| --- | --- |
| Crosswalk 활성·검증 | `NOT_MEASURED` |
| 승인 Embedding Identity | `NOT_MEASURED` |
| View 열·행·고유 Chunk | `NOT_MEASURED` |
| AI Role View SELECT | `NOT_VERIFIED` |
| AI Role Base Table SELECT 거부 | `NOT_VERIFIED` |
| AI Role View DML 거부 | `NOT_VERIFIED` |
| AI Role Schema CREATE 거부 | `NOT_VERIFIED` |
| 단위 Test 수치 | `25 passed, 0 failed, 0 skipped` |
| Role 통합 Test 수치 | `0 passed, 1 failed, 0 skipped` |

요청된 `7/7`, `8열/7행`, Role 권한 Matrix를 실측하지 못했으며, 기존 문서의 작성자
결과를 현재 Commit의 PASS로 재사용하지 않았다.

## 4. 실행하지 못한 검증과 이유

- Python `3.13.13` 설치와 Backend venv 재생성으로 기존 Python Process Exit `101` Blocker는 해소했다.
- Audit은 팀 DB명을 현재 Process에만 명시해 재실행했지만 PostgreSQL 연결 Timeout으로
  Crosswalk·View·Role Snapshot을 수집하지 못했다.
- Role 통합 Test는 수집됐지만 필수 Migrator Role Credential 환경변수가 주입되지 않아
  첫 Role 연결 전에 실패했다. Credential 값은 출력·기록하지 않았다.

### 원격 G1-B 재검증 필수 주입 항목

본 보고 후 확인된 원격 팀 DB 선행조건은 다음과 같다. 실제 값은 Git·문서·채팅으로
전달하지 않고, 공용환경 Provision 후 승인된 보안 채널에서 Process로만 주입한다.

- DB 메타데이터: `waterbridge_team_integration`, Port `5432`, QA Readonly Role,
  TLS `verify-full`
- 외부 주입: TLS DNS Endpoint, QA Readonly Role 비밀값, QA PC CA PEM 경로
- Role Matrix 추가 주입 키:
  `TEAM_INTEGRATION_MIGRATOR_PASSWORD`, `TEAM_INTEGRATION_RUNTIME_PASSWORD`,
  `TEAM_INTEGRATION_READONLY_PASSWORD`, `TEAM_INTEGRATION_AI_PASSWORD`

이 항목이 제공되기 전까지 `qa_decision=ENVIRONMENT_BLOCKED`를 유지한다. Secret이 필요 없는
Audit·Provisioning 단위 Test 두 파일은 고정 Commit에서 `25 passed`로 완료했다.

## 5. 발견했지만 수정하지 않은 관할 밖 문제

- 팀 PostgreSQL 연결이 Timeout이며, 현재 실행 환경에 Role 통합 Test용 Credential이 주입되지 않았다.
- G1-B DB 데이터와 Role 권한의 정상 여부는 이번 결과로 판정할 수 없다.

## 6. 필요한 담당자 인계

1. 팀 DB 담당자: 공유 또는 공식 DB 여부를 확인하고, 김은진 QA 환경에서 팀 DB 접속이 가능하도록 조치한다.
2. 팀 DB 담당자: TLS Endpoint·CA와 Role 통합 Test용 필수 Credential을 로그에
   노출되지 않는 승인 보안 채널로 전달한다.
3. 김은진 QA: 같은 `reviewed_commit`이 유지되는 동안 Audit과 Role 통합 Test를 재실행한다.
4. 재실행 전에는 팀 DB 이름과 PostgreSQL/Extension Version을 비밀값 없이 확인하고, 공유 DB에 Migration·Seed·Provisioning을 임의 적용하지 않는다.

## 7. 남은 위험과 확인 필요 항목

- Crosswalk `7/7`, View `8열/7행`은 미확인이다.
- AI Role의 View SELECT 허용과 Base Table SELECT·View DML·Schema CREATE 거부는 미확인이다.
- Role 통합 Test `1 passed / 0 skipped`는 미확인이며, 현재 실측은 `1 failed / 0 skipped`이다.
- DB 환경 복구 후 HEAD가 바뀌면 현재 결과와 재검증 결과를 합산하지 않고 새 `reviewed_commit`으로 시작해야 한다.
- 본 수치는 `reviewed_commit=99dcfbd178c51e0ab76446d8f88459ae2daa5ca2`와 동기화 전부터 있던
  Audit 공백 1줄 변경이 포함된 Worktree에서 실행했다. Clean-tree 검증으로 확대하지 않는다.

본 문서에 Secret, DSN, Credential 실제 값은 기록하지 않았다.
