[CmdletBinding()]
param(
    [string]$Username = 'DEMO-CONSULTANT-001',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$backendRoot = Join-Path $repositoryRoot 'backend'
$python = Join-Path $backendRoot '.venv\Scripts\python.exe'
$targetDatabase = 'waterbridge_p1_team_isolated'
$passwordEnvironmentName = 'WATERBRIDGE_CONSULTANT_PASSWORD'
$previousPostgresDatabase = [Environment]::GetEnvironmentVariable(
    'POSTGRES_DB',
    'Process'
)
$previousPassword = [Environment]::GetEnvironmentVariable(
    $passwordEnvironmentName,
    'Process'
)
$passwordPointer = [IntPtr]::Zero

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'backend/.venv Python을 찾을 수 없습니다.'
}
if ([string]::IsNullOrWhiteSpace($Username)) {
    throw '상담사 아이디를 입력해 주세요.'
}

try {
    $env:POSTGRES_DB = $targetDatabase
    Push-Location $backendRoot
    try {
        $auditOutput = & $python manage.py audit_p1_team_runtime_scope --json
        if ($LASTEXITCODE -ne 0) {
            throw 'P1 격리 DB 점검에 실패했습니다.'
        }
        $audit = ($auditOutput -join "`n") | ConvertFrom-Json
        if (
            $audit.database_name -ne $targetDatabase -or
            $audit.preserve.customers -ne 6 -or
            $audit.delete_candidates.customers -ne 0 -or
            $audit.delete_candidates.inquiries -ne 0
        ) {
            throw 'P1 격리 DB 고객·문의 기준이 맞지 않습니다.'
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
    [Environment]::SetEnvironmentVariable(
        $passwordEnvironmentName,
        $previousPassword,
        'Process'
    )
    if ($null -eq $previousPostgresDatabase) {
        Remove-Item Env:POSTGRES_DB -ErrorAction SilentlyContinue
    }
    else {
        $env:POSTGRES_DB = $previousPostgresDatabase
    }
}
