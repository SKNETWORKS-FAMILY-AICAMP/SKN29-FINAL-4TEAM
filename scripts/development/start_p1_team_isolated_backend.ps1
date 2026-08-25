[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 18000,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$backendRoot = Join-Path $repositoryRoot 'backend'
$python = Join-Path $backendRoot '.venv\Scripts\python.exe'
$targetDatabase = 'waterbridge_p1_team_isolated'
$previousPostgresDatabase = [Environment]::GetEnvironmentVariable(
    'POSTGRES_DB',
    'Process'
)

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'backend/.venv Python을 찾을 수 없습니다.'
}

$env:POSTGRES_DB = $targetDatabase

Push-Location $backendRoot
try {
    $auditOutput = & $python manage.py audit_p1_team_runtime_scope --json
    if ($LASTEXITCODE -ne 0) {
        throw 'P1 팀 격리 DB 점검에 실패했습니다.'
    }
    $audit = ($auditOutput -join "`n") | ConvertFrom-Json
    if ($audit.database_name -ne $targetDatabase) {
        throw '연결된 DB가 승인된 P1 격리 DB가 아닙니다.'
    }
    if (
        $audit.preserve.customers -ne 6 -or
        $audit.preserve.active_primary_contacts -ne 6 -or
        $audit.preserve.active_subscriptions -ne 6 -or
        $audit.delete_candidates.customers -ne 0 -or
        $audit.delete_candidates.inquiries -ne 0
    ) {
        throw 'P1 격리 DB의 고객·문의 기준이 맞지 않습니다.'
    }

    & $python manage.py migrate --check
    if ($LASTEXITCODE -ne 0) {
        throw 'P1 격리 DB Migration 점검에 실패했습니다.'
    }

    Write-Output 'p1_isolated_database=READY'
    Write-Output "database_name=$targetDatabase"
    Write-Output 'customers=6'
    Write-Output 'inquiries=0'

    if ($CheckOnly) {
        return
    }

    Write-Output "backend_url=http://127.0.0.1:$Port"
    & $python manage.py runserver "127.0.0.1:$Port" --noreload
    if ($LASTEXITCODE -ne 0) {
        throw "Backend가 종료 코드 $LASTEXITCODE 로 종료됐습니다."
    }
}
finally {
    if ($null -eq $previousPostgresDatabase) {
        Remove-Item Env:POSTGRES_DB -ErrorAction SilentlyContinue
    }
    else {
        $env:POSTGRES_DB = $previousPostgresDatabase
    }
    Pop-Location
}
