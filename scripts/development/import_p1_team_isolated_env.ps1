[CmdletBinding()]
param(
    [ValidateSet('Admin', 'Migrator', 'Runtime')]
    [string]$Role = 'Runtime',
    [string]$RuntimeRoot
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot '..\..')
)
if (-not $RuntimeRoot) {
    $RuntimeRoot = Join-Path $repositoryRoot '.runtime\p1-team-isolated'
}
$RuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)
$repositoryPrefix = $repositoryRoot.TrimEnd('\') + '\'
if (-not $RuntimeRoot.StartsWith(
    $repositoryPrefix,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw 'RuntimeRoot must stay inside the repository workspace.'
}

function Read-P1EnvironmentFile {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw 'A required P1 runtime environment file is missing.'
    }
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            if ($Matches[2].Contains("`r") -or $Matches[2].Contains("`n")) {
                throw 'A P1 runtime environment value is invalid.'
            }
            $values[$Matches[1]] = $Matches[2]
        }
    }
    return $values
}

$admin = Read-P1EnvironmentFile (
    Join-Path $RuntimeRoot 'env\admin.env'
)
$roles = Read-P1EnvironmentFile (
    Join-Path $RuntimeRoot 'env\roles.env'
)
$runtime = Read-P1EnvironmentFile (
    Join-Path $RuntimeRoot 'env\runtime.env'
)

$requiredAdmin = @(
    'POSTGRES_USER',
    'POSTGRES_PASSWORD',
    'POSTGRES_HOST',
    'POSTGRES_PORT',
    'POSTGRES_CONNECT_TIMEOUT',
    'POSTGRES_SSLMODE'
)
$requiredRoles = @(
    'TEAM_INTEGRATION_MIGRATOR_PASSWORD',
    'TEAM_INTEGRATION_RUNTIME_PASSWORD'
)
$requiredRuntime = @(
    'DJANGO_SETTINGS_MODULE',
    'DJANGO_SECRET_KEY',
    'DJANGO_DEBUG',
    'DJANGO_ALLOWED_HOSTS',
    'DJANGO_CORS_ALLOWED_ORIGINS',
    'DJANGO_TIME_ZONE',
    'AI_SERVICE_BASE_URL',
    'AI_SERVICE_MODE',
    'NO_PROXY'
)
foreach ($requiredName in $requiredAdmin) {
    if ([string]::IsNullOrWhiteSpace($admin[$requiredName])) {
        throw 'P1 admin runtime environment is incomplete.'
    }
}
foreach ($requiredName in $requiredRoles) {
    if ([string]::IsNullOrWhiteSpace($roles[$requiredName])) {
        throw 'P1 role runtime environment is incomplete.'
    }
}
foreach ($requiredName in $requiredRuntime) {
    if ([string]::IsNullOrWhiteSpace($runtime[$requiredName])) {
        throw 'P1 Django runtime environment is incomplete.'
    }
}

foreach ($entry in $roles.GetEnumerator()) {
    $roleSecret = if ($Role -eq 'Admin') {
        [string]$entry.Value
    }
    else {
        $null
    }
    [Environment]::SetEnvironmentVariable(
        [string]$entry.Key,
        $roleSecret,
        'Process'
    )
}

$roleMap = @{
    Admin = @('postgres', $admin.POSTGRES_USER, $admin.POSTGRES_PASSWORD)
    Migrator = @(
        'waterbridge_p1_team_isolated',
        'waterbridge_p1_migrator',
        $roles.TEAM_INTEGRATION_MIGRATOR_PASSWORD
    )
    Runtime = @(
        'waterbridge_p1_team_isolated',
        'waterbridge_p1_runtime',
        $roles.TEAM_INTEGRATION_RUNTIME_PASSWORD
    )
}
$selected = $roleMap[$Role]
$databaseValues = @{
    POSTGRES_DB = $selected[0]
    POSTGRES_USER = $selected[1]
    POSTGRES_PASSWORD = $selected[2]
    POSTGRES_HOST = $admin.POSTGRES_HOST
    POSTGRES_PORT = $admin.POSTGRES_PORT
    POSTGRES_CONNECT_TIMEOUT = $admin.POSTGRES_CONNECT_TIMEOUT
    POSTGRES_SSLMODE = $admin.POSTGRES_SSLMODE
}
foreach ($entry in $databaseValues.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable(
        $entry.Key,
        [string]$entry.Value,
        'Process'
    )
}
foreach ($entry in $runtime.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable(
        $entry.Key,
        [string]$entry.Value,
        'Process'
    )
}
[Environment]::SetEnvironmentVariable(
    'no_proxy',
    [string]$runtime.NO_PROXY,
    'Process'
)

[pscustomobject]@{
    status = 'P1_RUNTIME_ENV_LOADED'
    role = $Role
    database = $selected[0]
    runtime_root = '.runtime/p1-team-isolated'
    secret_values_printed = $false
}
