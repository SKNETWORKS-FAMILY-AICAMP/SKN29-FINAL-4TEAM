[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 18000,
    [string]$RuntimeRoot,
    [switch]$CheckOnly
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
$migrationRunner = Join-Path (
    $repositoryRoot
) 'scripts\database\migrate_team_integration_allowlist.py'
$managedEnvironmentNames = @(
    'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_HOST',
    'POSTGRES_PORT', 'POSTGRES_CONNECT_TIMEOUT', 'POSTGRES_SSLMODE',
    'DJANGO_SETTINGS_MODULE', 'DJANGO_SECRET_KEY', 'DJANGO_DEBUG',
    'DJANGO_ALLOWED_HOSTS', 'DJANGO_CORS_ALLOWED_ORIGINS',
    'DJANGO_TIME_ZONE', 'DJANGO_LOG_LEVEL', 'AI_SERVICE_BASE_URL',
    'AI_SERVICE_MODE', 'NO_PROXY', 'no_proxy'
)
$previousEnvironment = @{}
foreach ($name in $managedEnvironmentNames) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable(
        $name,
        'Process'
    )
}

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'backend/.venv Python을 찾을 수 없습니다.'
}
if (-not (Test-Path -LiteralPath $environmentLoader -PathType Leaf)) {
    throw 'P1 격리 Runtime 환경 Loader를 찾을 수 없습니다.'
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
            $audit.preserve.consultant_users -ne 1 -or
            $audit.delete_candidates.customers -ne 0 -or
            @($audit.blockers).Count -ne 0
        ) {
            throw 'P1 격리 DB의 고객·상담사·문의 소유권 기준이 맞지 않습니다.'
        }

        . $environmentLoader -RuntimeRoot $RuntimeRoot -Role Migrator | Out-Null
        $migrationOutput = @(
            & $python -B $migrationRunner --profile p1-team-isolated 2>&1
        )
        if ($LASTEXITCODE -ne 0) {
            $migrationOutput | Write-Output
            throw 'P1 격리 DB Migration HOLD 점검에 실패했습니다.'
        }
        $migration = ($migrationOutput -join "`n") | ConvertFrom-Json
        if (
            $migration.status -ne 'ALREADY_APPLIED' -or
            $migration.expected_final.'visits.0005' -ne 'NOT_APPLIED_P1_HOLD' -or
            @($migration.remaining_plan).Count -ne 0
        ) {
            throw 'P1 격리 DB Migration 상태가 승인 Allowlist와 다릅니다.'
        }
        . $environmentLoader -RuntimeRoot $RuntimeRoot -Role Runtime | Out-Null

        Write-Output 'p1_isolated_database=READY'
        Write-Output "database_name=$targetDatabase"
        Write-Output 'customers=6'
        Write-Output "inquiries=$($audit.runtime.p1_owned_inquiries)"
        Write-Output 'visits_0005=NOT_APPLIED_P1_HOLD'

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
        Pop-Location
    }
}
finally {
    foreach ($name in $managedEnvironmentNames) {
        [Environment]::SetEnvironmentVariable(
            $name,
            $previousEnvironment[$name],
            'Process'
        )
    }
}
