[CmdletBinding()]
param(
    [string]$RuntimeRoot,
    [ValidateRange(1, 500)]
    [int]$BatchSize = 100,
    [ValidateRange(0.2, 30.0)]
    [double]$PollSeconds = 1.0,
    [switch]$Once
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot '..\..')
)
$backendRoot = Join-Path $repositoryRoot 'backend'
$python = Join-Path $backendRoot '.venv\Scripts\python.exe'
$environmentLoader = Join-Path (
    $repositoryRoot
) 'scripts\development\import_p1_team_isolated_env.ps1'
$managedEnvironmentNames = @(
    'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_HOST',
    'POSTGRES_PORT', 'POSTGRES_CONNECT_TIMEOUT', 'POSTGRES_SSLMODE',
    'DJANGO_SETTINGS_MODULE', 'DJANGO_SECRET_KEY', 'DJANGO_DEBUG',
    'DJANGO_ALLOWED_HOSTS', 'DJANGO_CORS_ALLOWED_ORIGINS',
    'DJANGO_TIME_ZONE', 'DJANGO_LOG_LEVEL', 'AI_SERVICE_BASE_URL',
    'AI_SERVICE_MODE', 'NO_PROXY', 'no_proxy',
    'TEAM_INTEGRATION_MIGRATOR_PASSWORD',
    'TEAM_INTEGRATION_RUNTIME_PASSWORD',
    'TEAM_INTEGRATION_READONLY_PASSWORD',
    'TEAM_INTEGRATION_AI_PASSWORD'
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
    if ($env:POSTGRES_DB -ne 'waterbridge_p1_team_isolated') {
        throw 'OTP Worker 대상 DB가 P1 격리 DB가 아닙니다.'
    }
    $arguments = @(
        'manage.py',
        'process_p1_auth_email_outbox',
        '--batch-size', [string]$BatchSize,
        '--poll-seconds', [string]$PollSeconds,
        '--json'
    )
    if ($Once) {
        $arguments += '--once'
    }
    Push-Location $backendRoot
    try {
        Write-Output 'p1_auth_email_worker=STARTING'
        Write-Output 'database_name=waterbridge_p1_team_isolated'
        Write-Output 'secret_values_printed=false'
        & $python @arguments
        if ($LASTEXITCODE -ne 0) {
            throw 'P1 OTP Email Worker가 비정상 종료했습니다.'
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
