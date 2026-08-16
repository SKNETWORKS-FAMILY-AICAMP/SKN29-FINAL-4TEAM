# AI Runtime 보호 파일 설치·주입 가이드

## 1. 목적

이 문서는 승인된 AI 담당자가 기존 Loader를 수정하지 않고 OpenAI Key와
AI Readonly DB 연결정보를 현재 PowerShell Process에 주입하는 방법을 설명한다.

Secret, DSN, Password, 실제 Host 절대경로와 Vector 본문은 이 문서에 기록하지
않는다.

## 2. 필요한 보호 파일

현재 Loader를 수정하지 않고 사용하려면 다음 세 파일이 모두 필요하다.

```text
admin.env
roles.env
ai.env
```

각 파일의 역할은 다음과 같다.

| 파일 | Loader가 사용하는 정보 | 주의사항 |
| --- | --- | --- |
| `admin.env` | DB 주소·포트·연결 설정 | Admin 자격증명도 포함하므로 승인된 사용자만 접근 |
| `roles.env` | AI Readonly Role 자격증명 | 다른 TEAM_INTEGRATION Role 자격증명도 포함 |
| `ai.env` | `OPENAI_API_KEY` | Key 원문 출력·로그·Git 기록 금지 |

## 3. 설치 경로

세 파일을 수신 측 저장소 루트 아래 다음 상대경로에 설치한다.

```text
<repository-root>/.runtime/team-integration/env/admin.env
<repository-root>/.runtime/team-integration/env/roles.env
<repository-root>/.runtime/team-integration/env/ai.env
```

파일명과 `env` 디렉터리 구조를 변경하지 않는다. `<repository-root>`는 실제
절대경로를 문서나 채팅에 기록하지 않고 수신 측에서 자신의 저장소 루트로
해석한다.

`.runtime/**`는 Git에 추가하거나 Commit하지 않는다.

## 4. 설치 후 보호 확인

일반 ZIP 압축은 기존 Windows ACL을 보존하지 않을 수 있다. 압축을 해제한 뒤
`.runtime/team-integration/` 전체를 승인된 수신 사용자만 읽을 수 있도록 다시
보호한다.

다음 항목을 확인한다.

```text
파일 3개 존재=YES
Git ignored=YES
승인되지 않은 사용자 접근=NO
Secret 값 출력=NO
```

파일 내용을 확인하기 위해 `Get-Content`, `Write-Output`, `echo` 등을 사용하지
않는다.

## 5. 현재 Process에 환경 주입

저장소 루트에서 새 PowerShell을 열고 다음 명령을 실행한다.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

$loaded = . .\scripts\deployment\import_team_integration_env.ps1 `
  -Role AI `
  -RequireOpenAIKey

$loaded | Select-Object `
  status, `
  role, `
  openai_key, `
  ai_readonly_dsn, `
  secret_values_printed
```

첫 번째 점과 공백인 dot-source 구문을 생략하지 않는다. 일반 실행으로 호출하면
Loader가 종료될 때 환경변수도 사라져 뒤이어 실행하는 AI Process에 전달되지
않는다.

정상 결과는 다음과 같다.

```text
status=LOADED
role=AI
openai_key=YES
ai_readonly_dsn=YES
secret_values_printed=False
```

실제 `OPENAI_API_KEY`, `AI_VECTOR_DSN`, Password 값은 출력하지 않는다.

## 6. 같은 Process에서 AI 실행

Loader 실행이 성공한 동일 PowerShell에서 AI Service를 시작한다.

```powershell
.\ai\.venv\Scripts\python.exe -m uvicorn ai.app.main:app `
  --host 127.0.0.1 `
  --port 8001
```

다른 PowerShell 창에서 실행하면 주입된 환경변수가 전달되지 않는다. 별도
checkout의 AI 코드를 실행해야 하는 경우에도 Loader를 실행한 같은 PowerShell
Process 안에서 대상 checkout으로 이동한 후 실행한다.

Health는 응답 상태만 확인하고 Secret이나 환경변수 전체를 출력하지 않는다.

```powershell
$response = Invoke-WebRequest `
  -UseBasicParsing `
  -Uri 'http://127.0.0.1:8001/health' `
  -TimeoutSec 5

if ($response.StatusCode -eq 200) {
  'AI_HEALTH=PASS'
}
else {
  'AI_HEALTH=FAIL'
}
```

## 7. 중단 조건

다음 중 하나라도 해당하면 AI를 실행하지 않고 환경 담당자에게 회신한다.

- 세 보호 파일 중 하나라도 없음
- `openai_key=NO` 또는 `ai_readonly_dsn=NO`
- Runtime 디렉터리가 Git ignore 대상이 아님
- 승인되지 않은 사용자가 보호 파일을 읽을 수 있음
- 다른 Host에서 DB Endpoint에 연결할 수 없음
- Loader 실행 중 Secret·DSN·Password 원문이 출력됨

보호 파일이 없다고 초기화 스크립트로 새 DB Password를 임의 생성하지 않는다.
새 Password는 기존 DB Role의 Password와 일치하지 않을 수 있다.

## 8. 회신 형식

환경 담당자에게는 실제 값 대신 다음 형식으로만 회신한다.

```ini
protected_files=READY|MISSING
openai_key_injected=YES|NO
ai_readonly_dsn_injected=YES|NO
ai_health=PASS|FAIL|NOT_RUN
secret_values_printed=NO
```
