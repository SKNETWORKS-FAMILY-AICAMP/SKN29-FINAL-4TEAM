[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$BackendPort = 18000,
    [string]$RuntimeRoot,
    [string]$BackendPython
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot '..\..')
)
if (-not $RuntimeRoot) {
    $RuntimeRoot = Join-Path $repositoryRoot '.runtime\ai-context-local'
}
$RuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)
$repositoryPrefix = $repositoryRoot.TrimEnd('\') + '\'
if (-not $RuntimeRoot.StartsWith(
    $repositoryPrefix,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw 'RuntimeRoot must stay inside the repository workspace.'
}

if (-not $BackendPython) {
    $BackendPython = Join-Path (
        $repositoryRoot
    ) 'backend\.venv\Scripts\python.exe'
}
$backendPython = [System.IO.Path]::GetFullPath($BackendPython)
$managePy = Join-Path $repositoryRoot 'backend\manage.py'
$loader = Join-Path (
    $repositoryRoot
) 'scripts\deployment\import_team_integration_env.ps1'
$handoffPath = Join-Path $RuntimeRoot 'env\ai-context-handoff.env'

foreach ($path in @($backendPython, $managePy, $loader, $handoffPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required local Runtime file is missing: $path"
    }
}

$handoff = @{}
foreach ($line in Get-Content -LiteralPath $handoffPath -Encoding UTF8) {
    if ($line -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        $handoff[$Matches[1]] = $Matches[2]
    }
}
if ([string]::IsNullOrWhiteSpace($handoff.AI_HANDOFF_INTERNAL_TOKEN)) {
    throw 'Protected Backend handoff token is missing.'
}

. $loader -RuntimeRoot $RuntimeRoot -Role Runtime | Out-Null
$localDemoLoginCodes = @(
    'DEMO-CUSTOMER-001',
    'DEMO-CONSULTANT-001',
    'DEMO-TECHNICIAN-001',
    'DEMO-OPERATOR-001',
    'SYN-CUSTOMER-001'
) -join ','
$runtimeVariables = @{
    DJANGO_SETTINGS_MODULE = 'config.settings.local'
    DJANGO_SECRET_KEY = $handoff.AI_HANDOFF_INTERNAL_TOKEN
    DJANGO_DEBUG = 'true'
    DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1,[::1]'
    DJANGO_CORS_ALLOWED_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173'
    DJANGO_TIME_ZONE = 'Asia/Seoul'
    DJANGO_LOG_LEVEL = 'INFO'
    DJANGO_DEMO_LOGIN_ENABLED = 'true'
    DJANGO_DEMO_LOGIN_CODES = $localDemoLoginCodes
    AI_HANDOFF_INTERNAL_TOKEN = $handoff.AI_HANDOFF_INTERNAL_TOKEN
    AI_SERVICE_BASE_URL = 'http://127.0.0.1:8001'
    AI_SERVICE_MODE = 'local'
    AI_MODEL_PROVIDER = 'openai'
    AI_MODEL_NAME = 'gpt-4.1-mini'
    AI_PROMPT_VERSION = 'customer_guidance/v4'
    NO_PROXY = 'localhost,127.0.0.1,::1'
}
foreach ($entry in $runtimeVariables.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable(
        $entry.Key,
        $entry.Value,
        'Process'
    )
}
[Environment]::SetEnvironmentVariable(
    'no_proxy',
    'localhost,127.0.0.1,::1',
    'Process'
)

& $backendPython $managePy check
if ($LASTEXITCODE -ne 0) {
    throw 'Django check failed.'
}
Write-Output "backend_context_url=http://127.0.0.1:$BackendPort"
Write-Output 'handoff_token=PRESENT_NOT_PRINTED'
Write-Output 'Press Ctrl+C to stop only this local Backend process.'
& $backendPython $managePy runserver "127.0.0.1:$BackendPort" --noreload
exit $LASTEXITCODE
