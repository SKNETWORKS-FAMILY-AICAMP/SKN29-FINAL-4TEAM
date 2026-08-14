param(
    [string]$RuntimeRoot,
    [switch]$Rotate
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot '..\..')
)
if (-not $RuntimeRoot) {
    $RuntimeRoot = Join-Path $repositoryRoot '.runtime\team-integration'
}
$RuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)
$repositoryPrefix = $repositoryRoot.TrimEnd('\') + '\'
if (-not $RuntimeRoot.StartsWith(
    $repositoryPrefix,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw 'RuntimeRoot must stay inside the repository workspace.'
}

$environmentRoot = Join-Path $RuntimeRoot 'env'
$adminPath = Join-Path $environmentRoot 'admin.env'
$rolesPath = Join-Path $environmentRoot 'roles.env'

if (-not $Rotate -and (
    (Test-Path -LiteralPath $adminPath) -or
    (Test-Path -LiteralPath $rolesPath)
)) {
    throw 'TEAM_INTEGRATION runtime files already exist. Use -Rotate explicitly.'
}

New-Item -ItemType Directory -Path $environmentRoot -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $RuntimeRoot 'certs') -Force |
    Out-Null
New-Item -ItemType Directory -Path (Join-Path $RuntimeRoot 'logs') -Force |
    Out-Null

function New-RandomSecret {
    $bytes = [byte[]]::new(32)
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    return [Convert]::ToBase64String($bytes).TrimEnd('=').
        Replace('+', '-').Replace('/', '_')
}

function Write-SecretEnvironmentFile {
    param(
        [Parameter(Mandatory)]
        [string]$Path,
        [Parameter(Mandatory)]
        [string[]]$Lines
    )

    $temporaryPath = "$Path.tmp"
    [System.IO.File]::WriteAllLines(
        $temporaryPath,
        $Lines,
        [System.Text.UTF8Encoding]::new($false)
    )
    Move-Item -LiteralPath $temporaryPath -Destination $Path -Force
}

$adminPassword = New-RandomSecret
$rolePasswords = [ordered]@{
    TEAM_INTEGRATION_MIGRATOR_PASSWORD = New-RandomSecret
    TEAM_INTEGRATION_RUNTIME_PASSWORD = New-RandomSecret
    TEAM_INTEGRATION_READONLY_PASSWORD = New-RandomSecret
    TEAM_INTEGRATION_AI_PASSWORD = New-RandomSecret
}

Write-SecretEnvironmentFile -Path $adminPath -Lines @(
    'POSTGRES_DB=postgres'
    'POSTGRES_USER=waterbridge_ti_admin'
    "POSTGRES_PASSWORD=$adminPassword"
    'POSTGRES_HOST=127.0.0.1'
    'POSTGRES_PORT=55433'
    'POSTGRES_BIND_ADDRESS=127.0.0.1'
    'POSTGRES_CONNECT_TIMEOUT=5'
    'POSTGRES_SSLMODE=disable'
)

Write-SecretEnvironmentFile -Path $rolesPath -Lines @(
    $rolePasswords.GetEnumerator() |
        ForEach-Object { "$($_.Key)=$($_.Value)" }
)

$identity = "${env:USERDOMAIN}\${env:USERNAME}"
& icacls.exe $environmentRoot '/inheritance:r' '/grant:r' `
    "${identity}:(OI)(CI)F" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to restrict TEAM_INTEGRATION runtime file permissions.'
}

[pscustomobject]@{
    status = 'CREATED'
    runtime_root = '.runtime/team-integration'
    admin_environment = '.runtime/team-integration/env/admin.env'
    role_environment = '.runtime/team-integration/env/roles.env'
    secret_values_printed = $false
}
