# 이동윤 PC AI Context 5 Case 로컬 Bootstrap 인계

- 작성일: 2026-08-22 KST
- 작성자: 최지용(Backend·DB)
- 목적: 서로 다른 네트워크에서 최지용 PC에 접속하지 않고 이동윤 PC만으로
  Backend Context→MCP→pgvector→Provider 검증환경을 준비한다.

## 1. 핵심 변경

사설 IP나 원격 Token을 전달하는 방식은 사용하지 않는다. 이동윤 PC에서 다음을
각각 로컬로 생성한다.

- 전용 PostgreSQL 16·pgvector Container와 전용 Volume
- `waterbridge_team_integration` DB와 최소권한 Role
- `visits.0005`를 제외한 허용 Migration
- JAC104 공식 Evidence 7건과 Readonly View
- JAC104 정상 1건, IAC425·IAC606 일반·누수 4건
- Backend·AI Process가 함께 사용하는 일회성 내부 Token

모든 Runtime 파일은 Git 제외 경로인 `.runtime/ai-context-local`에 생성한다.
기존 DB·Docker Volume·개인 환경은 삭제하거나 초기화하지 않는다.

## 2. 사전 조건

1. 작업은 이 기능이 `main`에 병합된 뒤 최신 `main`에서 진행한다.
2. Git 작업트리는 Untracked 파일을 포함해 Clean 상태여야 한다.
3. Docker Desktop이 실행 중이어야 한다.
4. Python `3.13.13` 기반 `backend/.venv`, `ai/.venv`가 준비돼야 한다.
5. JAC104 공식 PDF를 Git 밖의 보호 폴더에 보관해야 한다.
6. 실제 Provider 실행 전 이동윤 본인의 OpenAI Key가 필요하다.

가상환경이 없다면 각 담당 환경에서 다음 잠금파일을 사용한다.

```powershell
py -3.13 -m venv .\backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt

py -3.13 -m venv .\ai\.venv
.\ai\.venv\Scripts\python.exe -m pip install -r .\ai\requirements.lock
```

## 3. 최신 main 확인

```powershell
git switch main
git pull --ff-only origin main
git status --short
git rev-parse HEAD
```

`git status --short`가 비어 있지 않으면 Bootstrap을 실행하지 않는다.

## 4. 비변경 Plan 확인

저장소 Root에서 실행한다.

```powershell
.\scripts\development\bootstrap_ai_context_local.ps1
```

다음이 확인돼야 한다.

```text
status=PLAN_READY
exact_origin_main=true
worktree_clean=true
target_database=waterbridge_team_integration
backend_base_url=http://127.0.0.1:18000
public_runtime=mvp
visits_0005=P1_HOLD_EXCLUDED
```

## 5. 로컬 격리환경 생성

`<보호된_공식PDF_폴더>`는 JAC104 공식 PDF가 있는 폴더로 교체한다. PDF는
파일 크기와 SHA-256이 정본과 정확히 일치해야 하며 Git에 넣지 않는다.

```powershell
.\scripts\development\bootstrap_ai_context_local.ps1 `
  -Apply `
  -RunIdPrefix dongyoon-20260822-r1 `
  -OfficialSourceSearchRoots '<보호된_공식PDF_폴더>'
```

이 명령은 다음 단계에서 하나라도 실패하면 중단한다.

1. 전용 PostgreSQL Health
2. DB·Role Provisioning
3. Migration Allowlist 및 `visits.0005` HOLD
4. Demo 계정·db-smoke·신규 2모델 Product Import
5. BGE-M3 7×1024 Fixture 생성
6. JAC104 공식 Evidence Import
7. Canonical Crosswalk 7건·Page Link 8건 동기화
8. 5개 신규 Inquiry 생성
9. Baseline Readiness READY

정상 완료 시 다음 두 파일이 만들어진다.

```text
.runtime/ai-context-local/evidence/five-case-crosswalk.json
.runtime/ai-context-local/env/ai-context-handoff.env
```

첫 파일은 5개 `inquiry_id·correlation_id·state_version`을 담고, 두 번째 파일은
Backend·AI가 공유하는 보호 Token과 로컬 URL을 담는다. 두 번째 파일의 내용은
채팅·문서·Git에 복사하지 않는다.

## 6. OpenAI Key 로컬 주입

다음 파일을 이동윤 PC에만 만들고 실제 Key를 입력한다.

```text
.runtime/ai-context-local/env/ai.env
```

형식은 한 줄이다.

```text
OPENAI_API_KEY=<이동윤_보호키>
```

이 파일은 `.runtime` 아래에 있으므로 Git에서 제외된다. `git status`와
`git ls-files .runtime`으로 노출 0건을 다시 확인한다.

## 7. Backend 실행 — PowerShell 1

```powershell
.\scripts\development\start_ai_context_backend_local.ps1
```

정상 기준:

```text
Django check=0 issues
Backend URL=http://127.0.0.1:18000
GET /health=200
```

이 창은 Backend가 실행되는 동안 닫지 않는다.

## 8. AI 환경 주입·실행 — PowerShell 2

환경 Loader는 반드시 Dot-source로 실행한다.

```powershell
. .\scripts\development\load_ai_context_local_env.ps1 -RequireOpenAIKey
```

정상 기준:

```text
status=AI_CONTEXT_LOCAL_ENV_LOADED
backend_health=PASS
context_cases=5/5_PASS
retrieval_transport=mcp
runtime_profile=mvp
vector_dsn=PRESENT_NOT_PRINTED
openai_key=PRESENT_NOT_PRINTED
```

같은 PowerShell에서 AI를 시작한다.

```powershell
.\ai\.venv\Scripts\python.exe -m uvicorn ai.app.main:app `
  --host 127.0.0.1 --port 8001
```

새 PowerShell을 열면 Process 환경값이 사라지므로 Loader부터 다시 실행한다.

## 9. 5 Case 기대값

| Case | MVP 기대값 | Vector·Provider |
| --- | --- | --- |
| JAC104 정상 | 실제 근거 기반 `SUCCEEDED` | 최초 요청 실행 |
| IAC425 일반 | `RUNTIME_PRODUCT_NOT_APPROVED` | 0회 |
| IAC425 누수 | 위험 안전판정 유지 후 제품 미승인 | 0회 |
| IAC606 일반 | `RUNTIME_PRODUCT_NOT_APPROVED` | 0회 |
| IAC606 누수 | 위험 안전판정 유지 후 제품 미승인 | 0회 |

`public_runtime=mvp`와 `AI_RAG_RUNTIME_PROFILE=mvp`를 유지한다.
`three_model_integration`, F02 재시도 정책, `danger+PARTIAL_STOP`은 바꾸지 않는다.
후보 Product의 DB Flag 활성화는 이 로컬 격리 Fixture 생성용이며 Public Runtime
승인을 의미하지 않는다.

## 10. Replay·회신 증거

완료 후 다음만 회신한다.

- 실행한 main SHA와 Dirty 여부
- AI Health·Readiness
- Crosswalk 파일의 Case별 Inquiry·Correlation·상태 버전
- Case별 상태·Fallback 사유·Vector·Provider 호출 수
- 동일 요청 Replay의 추가 Vector·Provider 호출 0회
- Backend·AI·DB Correlation 일치 여부
- Blocker와 공개 오류 코드

Token·DSN·OpenAI Key·공식 PDF 경로·고객 원문은 회신하지 않는다.

## 11. 종료·재실행

- Backend와 AI는 각 창에서 `Ctrl+C`로 종료한다.
- PostgreSQL은 `docker compose stop`만 사용해 보존한다.
- `docker compose down -v`, Volume 삭제, DB Drop은 실행하지 않는다.
- 같은 환경을 재사용할 때는 Backend·AI를 먼저 종료하고 Bootstrap에
  `-ReuseLocalRuntime`을 명시한다.
- 소비된 Inquiry를 초기화하지 말고 새로운 `RunIdPrefix`를 사용한다.

## 12. 판정 경계

Bootstrap 성공은 이동윤 PC의 로컬 통합환경 READY다. 전체 팀 E2E PASS는 아니다.
실제 5 Case 실행결과와 Replay 증거를 만든 뒤 김은진 독립 QA에서 최종 판정한다.
