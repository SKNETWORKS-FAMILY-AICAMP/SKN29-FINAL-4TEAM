# TEAM_INTEGRATION QA PostgreSQL

이 Compose는 기존 루트 `watercare-local` PostgreSQL과 분리된
`waterbridge_team_integration` 준비용 PostgreSQL 16·pgvector 환경이다.

## 안전 경계

- 기본 Bind는 `127.0.0.1:55433`이며 상태는 `QA_ISOLATED`다.
- 실제 고객정보·운영 Dump를 적재하지 않고 합성 데이터만 사용한다.
- 실제 Password·DSN·Token·CA를 이 디렉터리나 Git에 기록하지 않는다.
- Runtime Secret은 `.runtime/team-integration/env/**` 또는 승인된 Secret
  Manager에서 Process로 주입한다.
- Volume `waterbridge-team-integration-postgres-data`는 기존 로컬 Volume과
  분리하며 `docker compose down -v`를 실행하지 않는다.
- `TEAM_SHARED` 판정에는 전용 비운영 Host, 제한된 Network, TLS
  `verify-full`, DNS SAN 일치와 독립 QA가 추가로 필요하다.

## 초기화

저장소 루트에서 Runtime Secret을 한 번 생성한다. 기존 파일이 있으면 기본
실행은 실패하며 자동 덮어쓰지 않는다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\scripts\deployment\initialize_team_integration_runtime.ps1
```

기존 `admin.env`, `roles.env` 또는 전용 Volume이 있으면 위 초기화를 다시
실행하지 않는다. 특히 `-Rotate`는 명시적인 Secret 회전 작업에서만 사용한다.

기존 환경 재기동 전에는 Volume을 먼저 확인한다. Volume이 없으면 새 환경을
자동 생성하지 않고 중단한다.

```powershell
docker volume inspect waterbridge-team-integration-postgres-data
```

PostgreSQL만 기동한다.

```powershell
docker compose `
  --env-file .\.runtime\team-integration\env\admin.env `
  -f .\infra\docker\compose\team-integration\compose.yaml `
  up -d postgres
```

환경 주입은 역할별 Loader를 명령과 같은 PowerShell Process에서 사용한다.
값은 출력하지 않는다. 아래 예시는 Plan만 실행한다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '& {
  . .\scripts\deployment\import_team_integration_env.ps1 -Role Admin |
    Out-Null
  & .\backend\.venv\Scripts\python.exe -B `
    .\scripts\database\provision_team_integration.py
}'
```

## Backend·AI Process 전용 입력

공식 PDF는 복사하거나 경로를 기록하지 않는다. Loader가 사용자 표준 문서
위치에서 기대 크기와 SHA-256이 모두 일치하는 파일을 정확히 하나 찾은 경우에만
Backend Runtime Process에 경로를 주입한다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '& {
  . .\scripts\deployment\import_team_integration_env.ps1 `
    -Role Runtime -LoadOfficialSource | Out-Null
  # 같은 Process에서 Backend Importer를 실행한다.
}'
```

OpenAI Key는 대화형 입력으로 ACL 보호 Runtime 파일에 저장한다. 기존 값은
기본 실행으로 덮어쓰지 않으며 실제 Key를 명령 인자·문서·로그에 쓰지 않는다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\scripts\deployment\set_team_integration_openai_key.ps1
```

AI Runtime은 Loader와 Uvicorn을 반드시 같은 PowerShell Process에서 실행한다.
`-RequireOpenAIKey`는 보호된 Key가 없으면 기동 전에 실패한다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '& {
  . .\scripts\deployment\import_team_integration_env.ps1 `
    -Role AI -RequireOpenAIKey | Out-Null
  & .\ai\.venv\Scripts\python.exe -m uvicorn ai.app.main:app `
    --host 127.0.0.1 --port 8001
}'
```

이동윤이 전달하는 Fixture는 `.runtime/backend-ai/`에 수신한다. Q0에서는
수신함과 Git ignore만 준비하고 Reference Builder·AI Exporter·Import는 실행하지
않는다.

DB·Role 구성은 저장소의 Fail-closed Provisioning 도구를 사용한다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '& {
  . .\scripts\deployment\import_team_integration_env.ps1 -Role Admin |
    Out-Null
  & .\backend\.venv\Scripts\python.exe -B `
    .\scripts\database\provision_team_integration.py `
    --apply --confirm-database waterbridge_team_integration
}'
```

Migration 적용 전에는 `-Role Migrator`, Application·Seed 실행에는
`-Role Runtime`, G1-B Audit에는 `-Role Readonly`, AI pgvector Gate에는
`-Role AI`를 같은 방식으로 선택한다. Migration 후 Provisioning Apply를 한 번
더 실행해 신규 Table·View 권한을 재조정한다.

Loader는 `Admin`과 `Matrix`에서만 네 Role Secret을 함께 주입한다. 개별 Runtime
Role에서는 선택하지 않은 Role Secret과 이전 AI·공식 원본 환경변수를 먼저
제거해 같은 Shell의 잔존 값을 사용하지 않는다.

## 종료

검증을 시작한 Compose Service만 중지하고 Volume은 보존한다.

```powershell
docker compose `
  --env-file .\.runtime\team-integration\env\admin.env `
  -f .\infra\docker\compose\team-integration\compose.yaml `
  stop postgres
```
