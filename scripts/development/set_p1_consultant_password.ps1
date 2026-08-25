[CmdletBinding()]
param(
    [string]$Username = 'DEMO-CONSULTANT-001',
    [string]$RuntimeRoot,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot '..\..')
)
$backendRoot = Join-Path $repositoryRoot 'backend'
$python = Join-Path $backendRoot '.venv\Scripts\python.exe'
$targetDatabase = 'waterbridge_p1_team_isolated'
$environmentLoader = Join-Path (
    $repositoryRoot
) 'scripts\development\import_p1_team_isolated_env.ps1'
$passwordEnvironmentName = 'WATERBRIDGE_CONSULTANT_PASSWORD'
$managedEnvironmentNames = @(
    'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_HOST',
    'POSTGRES_PORT', 'POSTGRES_CONNECT_TIMEOUT', 'POSTGRES_SSLMODE',
    'DJANGO_SETTINGS_MODULE', 'DJANGO_SECRET_KEY', 'DJANGO_DEBUG',
    'DJANGO_ALLOWED_HOSTS', 'DJANGO_CORS_ALLOWED_ORIGINS',
    'DJANGO_TIME_ZONE', 'DJANGO_LOG_LEVEL', 'AI_SERVICE_BASE_URL',
    'AI_SERVICE_MODE', 'NO_PROXY', 'no_proxy',
    $passwordEnvironmentName
)
$previousEnvironment = @{}
foreach ($name in $managedEnvironmentNames) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable(
        $name,
        'Process'
    )
}
$passwordPointer = [IntPtr]::Zero

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'backend/.venv Python을 찾을 수 없습니다.'
}
if (-not (Test-Path -LiteralPath $environmentLoader -PathType Leaf)) {
    throw 'P1 격리 Runtime 환경 Loader를 찾을 수 없습니다.'
}
if ([string]::IsNullOrWhiteSpace($Username)) {
    throw '상담사 아이디를 입력해 주세요.'
}

try {
    . $environmentLoader -RuntimeRoot $RuntimeRoot -Role Runtime | Out-Null
    if ($env:POSTGRES_DB -ne $targetDatabase) {
        throw '연결된 DB가 승인된 P1 격리 DB가 아닙니다.'
    }
    Push-Location $backendRoot
    try {
        $auditOutput = @(
            & $python manage.py audit_p1_team_runtime_scope `
                --json --operational 2>&1
        )
        if ($LASTEXITCODE -ne 0) {
            throw 'P1 격리 DB 점검에 실패했습니다.'
        }
        $audit = ($auditOutput -join "`n") | ConvertFrom-Json
        if (
            $audit.database_name -ne $targetDatabase -or
            $audit.preserve.customers -ne 6 -or
            $audit.preserve.consultant_users -ne 1 -or
            $audit.delete_candidates.customers -ne 0 -or
            @($audit.blockers).Count -ne 0
        ) {
            throw 'P1 격리 DB 고객·상담사·문의 소유권 기준이 맞지 않습니다.'
        }

        $securePassword = Read-Host `
            -Prompt "$Username 합성 상담사 비밀번호(12~64자, 영문·숫자 포함)" `
            -AsSecureString
        $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR(
            $securePassword
        )
        $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
            $passwordPointer
        )
        [Environment]::SetEnvironmentVariable(
            $passwordEnvironmentName,
            $plainPassword,
            'Process'
        )
        $plainPassword = $null

        $arguments = @(
            'manage.py',
            'set_synthetic_consultant_password',
            '--username',
            $Username,
            '--password-env',
            $passwordEnvironmentName,
            '--json'
        )
        if ($DryRun) {
            $arguments += '--dry-run'
        }
        & $python @arguments
        if ($LASTEXITCODE -ne 0) {
            throw '합성 상담사 비밀번호 적용에 실패했습니다.'
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    foreach ($name in $managedEnvironmentNames) {
        [Environment]::SetEnvironmentVariable(
            $name,
            $previousEnvironment[$name],
            'Process'
        )
    }
}
