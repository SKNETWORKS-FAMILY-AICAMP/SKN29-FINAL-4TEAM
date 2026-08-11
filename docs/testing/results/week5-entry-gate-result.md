# 5주차 현재 HEAD 통합 QA 보고서

> 담당: 김은진 — 데이터·QA·DevOps
> 검증일: **2026-08-10 KST**
> 실행 구간: **2026-08-10 21:25~21:34 KST**
> Branch: `eunjin`
> Baseline Commit: `4d955116c00f715e1ba9e465104a381b858996b9`
> 실행 전 작업 트리: **CLEAN**
> 종합 판정: **WBS_WEEK5_HOLD**
> Gate 요약: [5주차 Gate Matrix](../matrices/week5-gate-matrix.md)

## 1. 판정 요약

현재 Commit에서 계약, Data, Backend test 설정, AI 단위 기준선과 Web 로컬 Gate는 재현됐다. 그러나 5주차 핵심 완료 조건인 실제 PostgreSQL, 팀 pgvector, Backend↔AI 최소 수직 연결, Public Evidence, Web·Mobile 실제 소비가 닫히지 않았다.

따라서 현재 상태는 다음과 같다.

- 계약 Gate: `PASS`
- Data·Backend·AI·Web 내부 기준선: 실행 가능한 범위 `PASS`
- PostgreSQL·Vector·Backend↔AI·Client Remote: `BLOCKED`
- WBS 5주차 Exit: `WBS_WEEK5_HOLD`

이 결과는 8월 10일 중간 기준선이다. 전체 5주차 실패나 Feature Complete 판정으로 확대하지 않는다.

## 2. 검증 환경

| 항목 | 확인 값 | 판정 |
| --- | --- | --- |
| OS | Windows NT 10.0.26200.0 | `INFO` |
| Backend Python | 3.13.13 | `PASS` |
| AI Python | 3.13.13 | `PASS` |
| Node.js | v24.18.0 | `PASS` |
| npm | 11.16.0 | `PASS` |
| Java | 26.0.1 | `INFO` — Mobile 승인 JDK 여부 미검증 |
| Backend Dependency | fingerprint `2bc6a96f5f135cd972687d5e70a33514a88a02382220a57b82547e7ffb8cb413` | `PASS` |
| Android SDK | 환경값·`local.properties`·ADB 없음 | `ENVIRONMENT_BLOCKED` |
| PostgreSQL | `POSTGRES_DB` 미설정 | `ENVIRONMENT_BLOCKED` |
| 팀 pgvector | 실행 환경 미설정 | `ENVIRONMENT_BLOCKED` |

비밀값·DSN·Token·실제 개인정보는 읽거나 기록하지 않았다.

## 3. 계약 Gate

### 3.1 실행 명령

```powershell
.\backend\.venv\Scripts\python.exe scripts\contracts\validate_openapi.py
.\backend\.venv\Scripts\python.exe scripts\contracts\validate_codes.py
.\backend\.venv\Scripts\python.exe scripts\contracts\validate_examples.py
.\backend\.venv\Scripts\python.exe scripts\contracts\validate_state_machine.py
.\backend\.venv\Scripts\python.exe scripts\contracts\validate_contract_crosswalk.py
.\backend\.venv\Scripts\python.exe -m pytest tests\contract -q -p no:cacheprovider
```

### 3.2 결과

| 검사 | 결과 | Exit Code |
| --- | --- | ---: |
| OpenAPI | YAML 108, Ref 434, Path 32, Operation 33 | 0 |
| Code Registry | Registry 28, Code 144, Action 23, Role 4 | 0 |
| Contract Example | API JSON 50/50, Integration 5, Wrapper 33 | 0 |
| State Machine | State 13, Event 30, Transition 34, Guard 39, 대표 단계 14 | 0 |
| Action Crosswalk | Runtime 12, OpenAPI-only 7, Contract-only 0, Deferred 4 | 0 |
| Root Contract Test | `12 passed` | 0 |

판정은 `PASS`다. 단, `contracts/api/components/schemas/evidence/**`와 `contracts/api/paths/evidence.yaml`의 Public Evidence 구조는 여전히 빈 객체이므로 Evidence Runtime 완료 증거는 아니다.

## 4. Data Gate

### 4.1 실행 명령

```powershell
.\backend\.venv\Scripts\python.exe -B -m unittest discover -s data\tools\tests -v
.\backend\.venv\Scripts\python.exe -B data\tools\pipeline.py qa --verify-rebuild
git diff --exit-code -- data
```

### 4.2 결과

| 검사 | 결과 | Exit Code |
| --- | --- | ---: |
| Data 단위 테스트 | `69 passed` | 0 |
| Data QA | 오류 0, 경고 0, 48 files, 740 records | 0 |
| 대표 E2E Invariant | 17/17 PASS | 0 |
| 결정적 재생성 | changed 0, canonical drift 0, regenerated 0 | 0 |
| Dataset 핵심 수량 | Manual 44, FAQ 119, RAG Chunk 7, Evidence 9, Synthetic Fixture 367 | 0 |
| 작업 트리 Data Diff | 없음 | 0 |
| Raw 비보존 정책 | `data/.temp` 없음, 관련 단위 테스트 PASS | 0 |

청킹 실험 임시 파일은 폐기됐고 공식 승인 RAG Chunk 7건 기준선만 유지된다. Data 산출물 내부의 `generated_at`과 `source_commit`은 결정적 산출물 메타데이터이며, 이 QA 실행 Commit은 보고서 상단의 `4d955116...`이다.

Data 자체는 `PASS`지만 `W5-G03`은 실제 PostgreSQL Seed Replay가 현재 Commit에서 실행되지 않아 `BLOCKED`를 유지한다.

## 5. Backend Gate

### 5.1 Test 설정 전체 Gate

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\development\check_environment.py --service backend --full
```

| 검사 | 결과 |
| --- | --- |
| Python·Dependency·Fingerprint | PASS |
| `pip check` | PASS |
| Django System Check | 문제 0 |
| Migration Drift | 변경 0 |
| 전체 pytest | `933 passed, 15 skipped` |
| 전체 명령 Exit Code | 0 |

15개 Skip은 PostgreSQL 전용 Vector·Catalog·Composite FK·Row Lock 의미론 또는 명시적으로 요청해야 하는 Team Integration Role 검사다. SQLite 기반 전체 회귀 PASS로 PostgreSQL 의미론을 대체하지 않는다.

### 5.2 PostgreSQL Gate

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\development\check_environment.py --service backend --postgresql
```

결과는 Exit Code 1이다. 필수 환경값 중 `POSTGRES_DB`가 설정되지 않아 읽기 전용 연결과 적용 Migration 확인을 실행하지 못했다. 이는 현재 제품 Assertion 실패가 아니라 `ENVIRONMENT_BLOCKED`이며, 임의 DB를 추측하거나 Migration을 적용하지 않았다.

다음 PostgreSQL 전용 의미론은 미검증이다.

- Visit nullable technician 관계 Row Lock 수정본
- 문의 상태 전환 Row Lock
- pgvector Catalog·Exact Search
- Composite FK
- Team Integration 4-Role Matrix
- Seed Replay와 실패 시 Rollback

## 6. AI Gate

### 6.1 실행 명령

```powershell
.\ai\.venv\Scripts\python.exe -m pip check
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit -q -p no:cacheprovider
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\integration\test_pgvector_runtime.py -q -rs -p no:cacheprovider
```

### 6.2 결과

| 검사 | 결과 | Exit Code |
| --- | --- | ---: |
| Dependency | No broken requirements | 0 |
| AI Unit | `127 passed, 3 warnings` | 0 |
| pgvector Integration | `1 skipped` — 실제 pgvector 환경 미설정 | 0 |

경고 3건은 Starlette TestClient 1건과 `jsonschema.RefResolver` 2건의 폐기 예정 API 경고다. 현재 실패는 아니지만 의존성 후속 정리 대상으로 남긴다.

단위 Test 통과는 실제 외부 LLM, 팀 pgvector, Multi-Agent Runtime 또는 Backend 실제 HTTP 완료 증거가 아니다. `W5-G04`, `W5-G05`, `W5-G07`은 `BLOCKED`다.

## 7. Web Gate

### 7.1 실행 명령

```powershell
Set-Location web
npm.cmd run lint
npm.cmd run test
npm.cmd run test -- --pool=vmThreads --maxWorkers=1
npm.cmd run build
```

### 7.2 결과

| 검사 | 결과 | Exit Code |
| --- | --- | ---: |
| Lint | 오류 없음 | 0 |
| 기본 Vitest | 32 files, `137 passed` | 0 |
| 단일 worker Vitest | 32 files, `137 passed` | 0 |
| TypeScript·Vite Build | PASS, 133 modules | 0 |

로컬 소비자 회귀는 `PASS`다. 그러나 실제 Backend를 대상으로 목록·상세·상담·방문·Evidence Remote Smoke와 correlation ID 대조를 실행하지 않았으므로 `W5-G08`은 `BLOCKED`다.

## 8. Mobile Gate

Mobile Build·Test는 실행하지 않았다.

| 확인 | 결과 |
| --- | --- |
| Gradle Wrapper·JAR | 존재 |
| Java | 26.0.1 |
| `ANDROID_HOME`·`ANDROID_SDK_ROOT` | 미설정 |
| `mobile/local.properties` | 없음 |
| ADB | 없음 |
| `origin/jeonghyun` HEAD | `eb78910ce1b82a8d0fc3dd53dd5e9c43eb3b19f1` |
| 현재 HEAD 포함 여부 | 미포함 |

Android SDK·승인 JDK와 5주차 Mobile 변경이 현재 Commit에 없으므로 `ENVIRONMENT_BLOCKED / NOT_INTEGRATED`다. 원격 브랜치의 작성자 결과를 현재 HEAD PASS로 재사용하지 않는다.

## 9. Root Integration·E2E·Safety 상태

Root `tests/**`에서 실제 실행되는 파일은 현재 Contract Test 3개뿐이다. 다음 경로는 `.gitkeep` 중심의 골격이며 서비스 경계를 검증하는 Test가 없다.

- `tests/integration/backend-ai/**`
- `tests/integration/backend-vector-store/**`
- `tests/integration/tracing/**`
- `tests/e2e/**`
- `tests/safety/**`
- `tests/smoke/**`

따라서 Data의 대표 E2E Invariant 17/17을 실제 고객→Backend→AI→상담→방문 서비스 E2E로 확대 판정하지 않는다.

## 10. 현재 문서·명세 Drift

| 대상 | 현재 Drift | 영향 |
| --- | --- | --- |
| `docs/planning/week5-*.md` | 계획 SHA `dd172c7...`, 상태 `PM_BASELINE_CANDIDATE` | G01·G11 미확정 |
| `docs/planning/week5-exit-gate.md` | 전 Gate가 `NOT_RUN` | 현재 실행 결과와 불일치 |
| `docs/api/runtime_implementation_status.md` | 8월 2일 10 Operation 기준 | 현재 OpenAPI 33 Operation과 불일치 |
| `docs/testing/web/week5-web-entry-gate.md` | 상담·방문 Runtime 미구현으로 기록 | 현재 Backend Runtime 12 Action과 불일치 |
| `docs/testing/ai/week5-ai-entry-gate.md` | Backend 환경 없음으로 기록 | 현재 Backend `.venv`·전체 회귀 가능 상태와 불일치 |
| `docs/decisions/week5-e2e-action-decision.md` | `OWNER_APPLY_PENDING` | OpenAPI·Crosswalk·Contract Test 적용 상태와 불일치 |
| Public Evidence 계약 | Card·Source·Verification·Path가 빈 객체 | Backend DTO·Web 실제 소비 차단 |

과거 문서는 삭제 대상이 아니라 시점별 증거다. 현재 기준 문서에서 `SUPERSEDED` 또는 후속 상태를 명시해야 한다.

## 11. 관할 밖 발견 문제와 인계

### 윤승혁 — PM·기술 통합

- Planning 기준 Commit을 `4d955116...` 또는 후속 승인 SHA로 갱신한다.
- `week5-exit-gate.md`를 본 Matrix와 대조해 현행화한다.
- WBS 5주차 대상 Action과 6~7주차 Deferred Action을 확정한다.

### 최지용 — Backend·DB

- 독립 QA DB 이름과 실행 범위를 제공한다.
- Visit Row Lock, Composite FK, Seed Replay, Role Matrix를 PostgreSQL에서 재검증한다.
- Public Evidence DTO·Route와 비노출 Test를 계약 담당자와 확정한다.

### 이동윤 — AI·RAG

- 승인된 pgvector DSN·Embedding Revision으로 검색 Case를 실행한다.
- 실제 LLM 사용 여부, Timeout·Fallback과 Backend Payload를 확정한다.
- Multi-Agent 초안을 실제 Runtime·Routing 결과와 구분한다.

### 한예나 — Web

- 현재 Backend Runtime 기준 Remote Smoke를 실행한다.
- 401·403·404·409·422·Network와 입력 보존·Correlation을 검증한다.

### 양정현 — Mobile

- 현재 기준 Branch에 5주차 변경을 병합한다.
- 승인 SDK/JDK에서 Unit·APK·고객/기사 Remote Smoke를 제공한다.

## 12. 다음 재검증 순서

1. PM 기준 SHA 확정
2. 독립 PostgreSQL Gate와 Visit Lock 표적 회귀
3. 팀 pgvector 검색·금지 Hit·실제 LLM 경계
4. Backend↔AI 실제 HTTP·DB 최소 수직 연결
5. Public Evidence Allowlist·비노출 Test
6. Web·Mobile 동일 Commit Remote Smoke
7. `week5-exit-gate.md`와 6~7주차 인계 갱신

G07 최소 수직 연결과 PostgreSQL·Vector 실증 전에는 `WBS_WEEK5_CONDITIONAL_PASS`로 승격하지 않는다.
