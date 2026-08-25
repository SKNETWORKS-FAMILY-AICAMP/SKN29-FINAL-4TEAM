[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$BackendPort = 18003,
    [ValidateRange(1024, 65535)]
    [int]$WebPort = 15173
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$backendRoot = Join-Path $repositoryRoot 'backend'
$webRoot = Join-Path $repositoryRoot 'web'
$python = Join-Path $backendRoot '.venv\Scripts\python.exe'
$node = (Get-Command node -ErrorAction Stop).Source
$viteScript = Join-Path $webRoot 'node_modules\vite\bin\vite.js'
$targetDatabase = 'waterbridge_p1_team_isolated'
$consultantUsername = 'DEMO-CONSULTANT-001'
$backendRuntime = Join-Path $backendRoot '.runtime'
$webRuntime = Join-Path $webRoot '.runtime'
$screenshot = Join-Path $webRuntime 'p1-consultant-password-login-smoke.png'
$backendOut = Join-Path $backendRuntime 'p1-consultant-smoke-backend.out.log'
$backendErr = Join-Path $backendRuntime 'p1-consultant-smoke-backend.err.log'
$webOut = Join-Path $webRuntime 'p1-consultant-smoke-web.out.log'
$webErr = Join-Path $webRuntime 'p1-consultant-smoke-web.err.log'
$previousPostgresDatabase = [Environment]::GetEnvironmentVariable(
    'POSTGRES_DB',
    'Process'
)
$managedEnvironmentNames = @(
    'WATERBRIDGE_CONSULTANT_PASSWORD',
    'VITE_USE_MOCK_API',
    'VITE_MOCK_AUTHENTICATED',
    'VITE_ENABLE_DESIGN_MOCK_FALLBACK',
    'VITE_BACKEND_PROXY_TARGET',
    'WB_SMOKE_PASSWORD',
    'WB_SMOKE_USERNAME',
    'WB_SMOKE_BASE_URL',
    'WB_SMOKE_SCREENSHOT',
    'WB_ORIGINAL_PASSWORD_HASH',
    'WB_ORIGINAL_AUTH_VERSION'
)
$previousProcessEnvironment = @{}
foreach ($environmentName in $managedEnvironmentNames) {
    $previousProcessEnvironment[$environmentName] =
        [Environment]::GetEnvironmentVariable($environmentName, 'Process')
}
$backendProcess = $null
$webProcess = $null
$passwordChanged = $false
$authSnapshot = $null
$browserResult = $null

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'backend/.venv Python을 찾을 수 없습니다.'
}
if (-not (Test-Path -LiteralPath $viteScript -PathType Leaf)) {
    throw 'web/node_modules Vite를 찾을 수 없습니다. npm ci를 먼저 실행해 주세요.'
}

New-Item -ItemType Directory -Path $backendRuntime -Force | Out-Null
New-Item -ItemType Directory -Path $webRuntime -Force | Out-Null

function Wait-Http200 {
    param(
        [Parameter(Mandatory)]
        [string]$Url
    )

    foreach ($attempt in 1..30) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                return
            }
        }
        catch {
            # Runtime이 기동하는 동안에만 재시도한다.
        }
        Start-Sleep -Milliseconds 500
    }
    throw "HTTP 200 대기 실패: $Url"
}

function Stop-SmokeProcess {
    param([AllowNull()][System.Diagnostics.Process]$Process)

    if ($null -ne $Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $Process.Id -Timeout 5 -ErrorAction SilentlyContinue
    }
}

try {
    $env:POSTGRES_DB = $targetDatabase

    Push-Location $backendRoot
    try {
        $auditOutput = & $python manage.py audit_p1_team_runtime_scope --json
        if ($LASTEXITCODE -ne 0) {
            throw 'P1 격리 DB 사전 점검에 실패했습니다.'
        }
        $audit = ($auditOutput -join "`n") | ConvertFrom-Json
        if (
            $audit.database_name -ne $targetDatabase -or
            $audit.preserve.customers -ne 6 -or
            $audit.preserve.consultant_users -lt 1 -or
            $audit.delete_candidates.customers -ne 0 -or
            $audit.delete_candidates.inquiries -ne 0
        ) {
            throw 'P1 격리 DB 고객·상담사·문의 기준이 맞지 않습니다.'
        }

        $snapshotOutput = & $python manage.py shell -c (
            "import json; from apps.accounts.models import User; " +
            "u=User.objects.get(username='$consultantUsername'); " +
            "print(json.dumps({'password':u.password,'auth_version':u.auth_version}))"
        )
        if ($LASTEXITCODE -ne 0) {
            throw '상담사 원본 인증 상태 조회에 실패했습니다.'
        }
        $authSnapshot = ($snapshotOutput | Select-Object -Last 1) | ConvertFrom-Json

        $randomBytes = New-Object byte[] 24
        [System.Security.Cryptography.RandomNumberGenerator]::Fill($randomBytes)
        $encodedPassword = [Convert]::ToBase64String($randomBytes)
        $encodedPassword = $encodedPassword.Replace('/', 'x')
        $encodedPassword = $encodedPassword.Replace('+', 'y').TrimEnd('=')
        $temporaryPassword = 'TmpA9!' + $encodedPassword
        $env:WATERBRIDGE_CONSULTANT_PASSWORD = $temporaryPassword
        $setOutput = & $python manage.py set_synthetic_consultant_password `
            --username $consultantUsername `
            --password-env WATERBRIDGE_CONSULTANT_PASSWORD `
            --json
        if ($LASTEXITCODE -ne 0) {
            throw '임시 상담사 비밀번호 설정에 실패했습니다.'
        }
        $setResult = ($setOutput | Select-Object -Last 1) | ConvertFrom-Json
        if ($setResult.status -ne 'APPLIED' -or $setResult.secret_exposed -ne $false) {
            throw '상담사 비밀번호 설정 안전 판정에 실패했습니다.'
        }
        $passwordChanged = $true
    }
    finally {
        Pop-Location
    }

    $backendProcess = Start-Process `
        -FilePath $python `
        -ArgumentList 'manage.py', 'runserver', "127.0.0.1:$BackendPort", '--noreload' `
        -WorkingDirectory $backendRoot `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $backendOut `
        -RedirectStandardError $backendErr
    Wait-Http200 -Url "http://127.0.0.1:$BackendPort/health"

    $env:VITE_USE_MOCK_API = 'false'
    $env:VITE_MOCK_AUTHENTICATED = 'false'
    $env:VITE_ENABLE_DESIGN_MOCK_FALLBACK = 'false'
    $env:VITE_BACKEND_PROXY_TARGET = "http://127.0.0.1:$BackendPort"
    $webProcess = Start-Process `
        -FilePath $node `
        -ArgumentList $viteScript, '--host', '127.0.0.1', '--port', "$WebPort" `
        -WorkingDirectory $webRoot `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $webOut `
        -RedirectStandardError $webErr
    Wait-Http200 -Url "http://127.0.0.1:$WebPort/login"

    $env:WB_SMOKE_USERNAME = $consultantUsername
    $env:WB_SMOKE_PASSWORD = $temporaryPassword
    $env:WB_SMOKE_BASE_URL = "http://127.0.0.1:$WebPort"
    $env:WB_SMOKE_SCREENSHOT = $screenshot
    $browserScript = @'
import { chromium } from "@playwright/test";

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.goto(`${process.env.WB_SMOKE_BASE_URL}/login`, {
    waitUntil: "networkidle",
  });
  await page.locator('input[name="username"]').fill(process.env.WB_SMOKE_USERNAME);
  await page.locator('input[name="password"]').fill(process.env.WB_SMOKE_PASSWORD);
  const assignedList = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname.endsWith("/api/v1/inquiries")
    );
  });
  const unassignedList = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname.endsWith("/api/v1/inquiries/unassigned-consultations")
    );
  });
  await page.getByRole("button", { name: "ID/PW로 로그인" }).click();
  await page.waitForURL(/\/consultant\/inquiries/, { timeout: 15000 });
  const [assignedResponse, unassignedResponse] = await Promise.all([
    assignedList,
    unassignedList,
  ]);
  if (assignedResponse.status() !== 200 || unassignedResponse.status() !== 200) {
    throw new Error("consultant inquiry API did not return HTTP 200");
  }
  await page
    .getByText("상담 문의 목록을 불러오고 있습니다.")
    .waitFor({ state: "hidden", timeout: 15000 });
  await page.locator('[aria-label="상담 문의 목록"]').waitFor();
  const alerts = await page.getByRole("alert").count();
  if (alerts !== 0) {
    throw new Error("consultant page contains an error alert");
  }
  await page.screenshot({
    path: process.env.WB_SMOKE_SCREENSHOT,
    fullPage: true,
  });
  console.log(
    JSON.stringify({
      login: "PASS",
      role: "CONSULTANT",
      final_path: new URL(page.url()).pathname,
      assigned_list_http: assignedResponse.status(),
      unassigned_list_http: unassignedResponse.status(),
      loading_finished: true,
      screenshot_created: true,
      secret_exposed: false,
    }),
  );
} finally {
  await browser.close();
}
'@

    Push-Location $webRoot
    try {
        $browserOutput = & $node --input-type=module -e $browserScript
        if ($LASTEXITCODE -ne 0) {
            throw 'Playwright 상담사 ID/PW 로그인 Smoke에 실패했습니다.'
        }
        $browserResult = ($browserOutput | Select-Object -Last 1) | ConvertFrom-Json
        if (
            $browserResult.login -ne 'PASS' -or
            $browserResult.final_path -ne '/consultant/inquiries' -or
            $browserResult.assigned_list_http -ne 200 -or
            $browserResult.unassigned_list_http -ne 200
        ) {
            throw 'Playwright 상담 문의 조회 판정에 실패했습니다.'
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    Stop-SmokeProcess -Process $webProcess
    Stop-SmokeProcess -Process $backendProcess

    if ($passwordChanged) {
        $env:WB_ORIGINAL_PASSWORD_HASH = [string]$authSnapshot.password
        $env:WB_ORIGINAL_AUTH_VERSION = [string]$authSnapshot.auth_version
        Push-Location $backendRoot
        try {
            & $python manage.py shell -c (
                "import os; from apps.accounts.models import User; " +
                "User.objects.filter(username='$consultantUsername').update(" +
                "password=os.environ['WB_ORIGINAL_PASSWORD_HASH'], " +
                "auth_version=int(os.environ['WB_ORIGINAL_AUTH_VERSION']))"
            ) | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw '상담사 원본 인증 상태 복원에 실패했습니다.'
            }
            $restoreCheckOutput = & $python manage.py shell -c (
                "import json; from apps.accounts.models import User; " +
                "u=User.objects.get(username='$consultantUsername'); " +
                "print(json.dumps({'password':u.password,'auth_version':u.auth_version}))"
            )
            if ($LASTEXITCODE -ne 0) {
                throw '상담사 인증 상태 복원 확인에 실패했습니다.'
            }
            $restoreCheck = ($restoreCheckOutput | Select-Object -Last 1) |
                ConvertFrom-Json
            if (
                $restoreCheck.password -ne $authSnapshot.password -or
                $restoreCheck.auth_version -ne $authSnapshot.auth_version
            ) {
                throw '상담사 인증 상태가 원본과 일치하지 않습니다.'
            }
        }
        finally {
            Pop-Location
        }
    }

    foreach ($environmentName in $managedEnvironmentNames) {
        $previousValue = $previousProcessEnvironment[$environmentName]
        if ($null -eq $previousValue) {
            [Environment]::SetEnvironmentVariable(
                $environmentName,
                $null,
                'Process'
            )
        }
        else {
            [Environment]::SetEnvironmentVariable(
                $environmentName,
                [string]$previousValue,
                'Process'
            )
        }
    }
    if ($null -eq $previousPostgresDatabase) {
        Remove-Item Env:POSTGRES_DB -ErrorAction SilentlyContinue
    }
    else {
        $env:POSTGRES_DB = $previousPostgresDatabase
    }
}

$browserResult | Add-Member -NotePropertyName database_name -NotePropertyValue $targetDatabase
$browserResult | Add-Member -NotePropertyName credential_restored -NotePropertyValue $true
$browserResult | ConvertTo-Json -Compress
