# 5주차 현재 HEAD 서비스 회귀 기준선

> 담당: 김은진 — 데이터·QA·DevOps
> 검증일: **2026-08-11 KST**
> Branch: `eunjin`
> Baseline Commit: `88148c97ba727c62fc520104aa20a796d089d10b`
> 시작 작업 트리: **CLEAN**
> 종료까지 HEAD 변경: **없음**
> 종합 판정: **LOCAL_BASELINE_PASS · LIVE_INTEGRATION_HOLD**

## 1. 판정 요약

현재 HEAD에 김은진 주관할 Contract CI·Root 계약·안전 Test 변경을 적용한
작업 트리에서 Contract, Data, Backend Test 설정, AI Unit, Web 로컬 회귀를
실행했다. 모든 명령은 같은 HEAD에서 실행했으며 과거 보고서 수치를 재사용하지
않았다.

| 영역 | 현재 결과 | 판정 제한 |
|---|---|---|
| Contract | Validator 6종·Root Contract `38 passed` | 원격 GitHub Actions는 미실행 |
| Root Safety | `4 passed` | Runtime Safety·E2E가 아닌 Data–AI 계약 교차 검증 |
| Data | Unit `76 passed`, QA 오류·경고 0, Drift 0 | PostgreSQL Seed Replay 미실행 |
| Backend | `966 passed, 17 skipped`, Migration Drift 0 | PostgreSQL·실제 AI Socket 의미론 미검증 |
| AI | Unit `142 passed, 3 warnings` | 실제 LLM·Multi-Agent 완료 증거 아님 |
| pgvector | `1 skipped` | 승인 DSN·Embedding Revision 없음 |
| Web | Lint·단일 worker `137 passed`·Build PASS | 실제 Backend Remote Smoke 없음 |
| Mobile | 환경 점검만 수행 | Android SDK·ADB·승인 JDK 없음 |

따라서 로컬 재현 가능한 기준선은 PASS지만 WBS 5주차 전체 판정은 `HOLD`다.

## 2. 검증 환경

| 항목 | 확인 결과 |
|---|---|
| Backend Python | `3.13.13`, requirements fingerprint PASS |
| AI Python | 프로젝트 `ai/.venv`, `pip check` PASS |
| Node.js / npm | `v24.18.0` / `11.16.0` |
| Java | `26.0.1` — Mobile 승인 JDK 여부 미검증 |
| `POSTGRES_DB` Process 환경 | 미설정 |
| `AI_VECTOR_DSN` Process 환경 | 미설정 |
| `AI_EMBEDDING_REVISION` Process 환경 | 미설정 |
| Android SDK 환경·`local.properties`·ADB | 모두 없음 |
| Backend Live HTTP opt-in | 미설정 |

환경값의 원문, `.env`, DSN, Token과 고객정보는 읽거나 기록하지 않았다.

## 3. Contract·Root Safety

### 실행 명령

```powershell
.\backend\.venv\Scripts\python.exe -B scripts\contracts\validate_state_machine.py
.\backend\.venv\Scripts\python.exe -B scripts\contracts\render_state_machine.py --check
.\backend\.venv\Scripts\python.exe -B scripts\contracts\validate_codes.py
.\backend\.venv\Scripts\python.exe -B scripts\contracts\validate_openapi.py
.\backend\.venv\Scripts\python.exe -B scripts\contracts\validate_examples.py
.\backend\.venv\Scripts\python.exe -B scripts\contracts\validate_contract_crosswalk.py
.\backend\.venv\Scripts\python.exe -B -m pytest tests\contract -q -p no:cacheprovider
.\backend\.venv\Scripts\python.exe -B -m pytest tests\safety -q -p no:cacheprovider
```

### 결과

| 검사 | 결과 | Exit Code |
|---|---|---:|
| State Machine | State 13, Event 30, Transition 34, Guard 39 | 0 |
| Mermaid Drift | Drift 없음 | 0 |
| Code Registry | Registry 28, Code 144, Action 23, Role 4 | 0 |
| OpenAPI | YAML 108, Ref 434, Path 32, Operation 33 | 0 |
| Example | API 50/50, Integration 5, Wrapper 33 | 0 |
| Crosswalk | Runtime 12, OpenAPI-only 7, Deferred 4 | 0 |
| Root Contract | `38 passed` | 0 |
| Root Safety | `4 passed` | 0 |

Contract CI Workflow 자체의 Trigger·권한·Runtime Pin·7개 Gate와
`continue-on-error` 부재도 Root Contract Test에 포함했다. Workflow 파일은
아직 Commit·Push하지 않았으므로 원격 결과는 `REMOTE_NOT_RUN`이다.

## 4. Data

```powershell
.\backend\.venv\Scripts\python.exe -B -m unittest discover -s data\tools\tests -v
.\backend\.venv\Scripts\python.exe -B data\tools\pipeline.py qa --verify-rebuild
git diff --exit-code -- data
```

| 검사 | 결과 | Exit Code |
|---|---|---:|
| Unit | `76 passed` | 0 |
| QA | 오류 0, 경고 0, 48 files, 740 records | 0 |
| 대표 Data E2E Invariant | 17/17 PASS | 0 |
| 결정적 재생성 | changed 0, canonical drift 0, regenerated 0 | 0 |
| Data Diff | 없음 | 0 |

이 결과는 합성 Data·Fixture의 정합성 증거이며 실제 서비스 E2E PASS가 아니다.
QA 출력의 `source_commit=b937c0a...`는 결정적 Data 생성 메타데이터이고, 이번
실행 Commit은 문서 상단의 `88148c9...`다.

## 5. Backend

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\development\check_environment.py --service backend --full
```

- Python·Dependency·Fingerprint·`pip check`: PASS
- Django System Check: 문제 0
- Migration Drift: 변경 0
- 전체 Test: `966 passed, 17 skipped`
- Exit Code: 0

17개 Skip은 PostgreSQL Catalog·Vector·Composite FK·Row Lock, Team Role, 실제
AI Socket opt-in이다. SQLite Test 설정 회귀로 해당 의미론을 대체하지 않는다.

## 6. AI·Vector

```powershell
.\ai\.venv\Scripts\python.exe -m pip check
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit -q -p no:cacheprovider
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\integration\test_pgvector_runtime.py -q -rs -p no:cacheprovider
```

| 검사 | 결과 | Exit Code |
|---|---|---:|
| Dependency | No broken requirements | 0 |
| Unit | `142 passed, 3 warnings` | 0 |
| pgvector | `1 skipped` — 실제 환경 미설정 | 0 |

경고는 Starlette TestClient 1건과 AI 소유 Test의 `jsonschema.RefResolver` 2건이다.
신규 Root Contract Test는 `referencing` Registry를 사용해 같은 경고를 추가하지
않았다. 실제 LLM은 `EXTERNAL_LLM_NOT_VERIFIED`, 목표 Multi-Agent는
`TARGET_RUNTIME_NOT_IMPLEMENTED`다.

## 7. Web

```powershell
Set-Location web
npm.cmd run lint
npm.cmd run test
npm.cmd run test -- --pool=vmThreads --maxWorkers=1
npm.cmd run build
```

기본 병렬 Test는 Exit Code 0을 반환했지만 15개 Worker Timeout과 15개 Test File
미실행이 함께 발생했다. 이를 PASS로 집계하지 않고 Harness를 단일 worker로
교정해 재실행했다.

| 검사 | 결과 | 판정 |
|---|---|---|
| Lint | 오류 없음 | PASS |
| 기본 Test | 17 files·45 passed·15 worker errors | `HARNESS_FAILED` |
| 단일 worker Test | 32 files·`137 passed` | PASS |
| TypeScript·Vite Build | 133 modules, Build 완료 | PASS |

실제 Backend Remote Smoke·409 입력 보존·Correlation 대조는 미실행이므로 Web
소비 Gate 전체는 계속 `BLOCKED`다.

## 8. 실행하지 않은 Gate

| Gate | 상태 | 이유·해제 조건 |
|---|---|---|
| PostgreSQL·Seed·Row Lock | `ENVIRONMENT_BLOCKED` | 명시된 독립 QA DB 없음 |
| 팀 pgvector | `ENVIRONMENT_BLOCKED` | 승인 DSN·Embedding Revision 없음 |
| 외부 LLM | `EXTERNAL_LLM_NOT_VERIFIED` | Provider Mode·Key 실행 증거 없음 |
| Backend↔AI Live | `INTEGRATION_BLOCKED` | Local Mode·독립 DB·실행 opt-in 없음 |
| Mobile Build | `ENVIRONMENT_BLOCKED` | SDK·ADB·승인 JDK 없음 |
| Web·Mobile Remote | `INTEGRATION_BLOCKED` | 실제 Backend 대상 실행환경 없음 |
| 대표 E2E | `NOT_RUN` | 5주차 필수 Live Gate 미통과 |

## 9. 작업 트리와 기준선 주의

검증 시작 시 작업 트리는 Clean이었고 종료까지 HEAD는
`88148c97ba727c62fc520104aa20a796d089d10b`로 유지됐다. 실행 중 별도 작업으로
`docs/daily-scrum/5주차_데일리스크럼.md` 수정이 감지됐다. 이 파일은 이번 QA
변경에 포함하거나 수정하지 않았으며 최종 Diff 판정에서 별도 사용자 변경으로
분리한다.

현재 QA 변경은 Commit 전이므로 실행 기준은 **고정 HEAD + 명시된 QA Workflow·Test
작업 트리**다. Commit·Push 후 원격 Contract CI가 PASS하기 전에는 W5-BLK-004를
닫지 않는다.
