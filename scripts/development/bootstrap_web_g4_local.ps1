[CmdletBinding()]
param(
    [switch]$Apply,
    [string]$RunIdPrefix,
    [ValidateRange(1024, 65535)]
    [int]$PostgresPort = 55444,
    [string]$RuntimeRoot,
    [string]$BackendPython,
    [switch]$ReuseLocalRuntime
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot '..\..')
)
if (-not $RuntimeRoot) {
    $RuntimeRoot = Join-Path $repositoryRoot '.runtime\web-g4-local'
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
$environmentLoader = Join-Path (
    $repositoryRoot
) 'scripts\deployment\import_team_integration_env.ps1'
$runtimeInitializer = Join-Path (
    $repositoryRoot
) 'scripts\deployment\initialize_team_integration_runtime.ps1'
$provisioner = Join-Path (
    $repositoryRoot
) 'scripts\database\provision_team_integration.py'
$migrationRunner = Join-Path (
    $repositoryRoot
) 'scripts\database\migrate_team_integration_allowlist.py'
$composeFile = Join-Path (
    $repositoryRoot
) 'infra\docker\compose\team-integration\compose.yaml'
$environmentRoot = Join-Path $RuntimeRoot 'env'
$adminEnvironment = Join-Path $environmentRoot 'admin.env'
$rolesEnvironment = Join-Path $environmentRoot 'roles.env'
$evidenceRoot = Join-Path $RuntimeRoot 'evidence'
$fixturePath = Join-Path $evidenceRoot 'web-g4-concealed-fixture.json'
$statusPath = Join-Path $evidenceRoot 'web-g4-bootstrap-status.json'
$sourceShaPath = Join-Path $RuntimeRoot 'source-sha.txt'
$composeOverride = Join-Path $RuntimeRoot 'compose.override.yaml'
$composeProject = 'waterbridge-web-g4-local'
$containerName = 'waterbridge-web-g4-local-postgres'
$volumeName = 'waterbridge-web-g4-local-postgres-data'
$localDemoLoginCodes = @(
    'DEMO-CUSTOMER-001',
    'DEMO-CONSULTANT-001',
    'DEMO-TECHNICIAN-001',
    'DEMO-OPERATOR-001',
    'SYN-CUSTOMER-001'
) -join ','

function Assert-File {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file is missing: $Path"
    }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory)][string]$Command,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed without exposing protected values: $Command"
    }
}

function Invoke-JsonManagementCommand {
    param([Parameter(Mandatory)][string[]]$Arguments)

    $output = @(& $backendPython $managePy @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        $output | Write-Output
        throw 'Fixture command failed.'
    }
    $lastLine = @(
        $output | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )[-1]
    try {
        return $lastLine | ConvertFrom-Json
    }
    catch {
        throw 'Fixture command did not return the expected JSON contract.'
    }
}

function Set-EnvironmentEntry {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Value
    )

    $lines = @(Get-Content -LiteralPath $Path -Encoding UTF8)
    $pattern = '^' + [regex]::Escape($Name) + '='
    $updated = $false
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match $pattern) {
            $lines[$index] = "$Name=$Value"
            $updated = $true
        }
    }
    if (-not $updated) {
        $lines += "$Name=$Value"
    }
    [System.IO.File]::WriteAllLines(
        $Path,
        $lines,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function New-ProcessSecret {
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

function Set-DjangoRuntimeEnvironment {
    $values = @{
        DJANGO_SETTINGS_MODULE = 'config.settings.local'
        DJANGO_SECRET_KEY = (New-ProcessSecret)
        DJANGO_DEBUG = 'true'
        DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1,[::1]'
        DJANGO_CORS_ALLOWED_ORIGINS = (
            'http://localhost:4173,http://127.0.0.1:4173'
        )
        DJANGO_TIME_ZONE = 'Asia/Seoul'
        DJANGO_LOG_LEVEL = 'INFO'
        DJANGO_DEMO_LOGIN_ENABLED = 'true'
        DJANGO_DEMO_LOGIN_CODES = $localDemoLoginCodes
        AI_SERVICE_BASE_URL = 'http://127.0.0.1:8001'
        AI_SERVICE_MODE = 'local'
        NO_PROXY = 'localhost,127.0.0.1,::1'
    }
    foreach ($entry in $values.GetEnumerator()) {
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
}

foreach ($requiredFile in @(
    $backendPython,
    $managePy,
    $environmentLoader,
    $runtimeInitializer,
    $provisioner,
    $migrationRunner,
    $composeFile
)) {
    Assert-File $requiredFile
}

$sourceSha = (& git -C $repositoryRoot rev-parse HEAD).Trim()
$branch = (& git -C $repositoryRoot branch --show-current).Trim()
$originMain = (& git -C $repositoryRoot rev-parse origin/main).Trim()
$sourceDirty = @(
    & git -C $repositoryRoot status --porcelain --untracked-files=normal 2>$null
)
if ($LASTEXITCODE -ne 0) {
    throw 'Git source state could not be inspected safely.'
}
$dockerReady = [bool](Get-Command docker -ErrorAction SilentlyContinue)
$preflight = [ordered]@{
    status = if ($Apply) { 'APPLY_REQUESTED' } else { 'PLAN_READY' }
    mutates_local_environment = [bool]$Apply
    branch = $branch
    source_sha = $sourceSha
    origin_main_sha = $originMain
    exact_origin_main = $sourceSha -eq $originMain
    worktree_clean = $sourceDirty.Count -eq 0
    docker_cli = if ($dockerReady) { 'READY' } else { 'BLOCKED' }
    runtime_root = '.runtime/web-g4-local'
    target_database = 'waterbridge_team_integration'
    postgres_port = $PostgresPort
    compose_project = $composeProject
    volume = $volumeName
    g2_g3 = 'NOT_APPLICABLE_FOR_WEB_G4'
    visits_0005 = 'P1_HOLD_EXCLUDED'
    secrets_printed = $false
}
if (-not $Apply) {
    $preflight | ConvertTo-Json -Depth 4
    return
}

if (-not $dockerReady) {
    throw (
        'Docker Desktop CLI is required. Install/start Docker Desktop, ' +
        'open a new PowerShell, and rerun Plan before Apply.'
    )
}
Invoke-Checked -Command 'docker' -Arguments @('version')
Invoke-Checked -Command 'docker' -Arguments @('compose', 'version')
if ($branch -ne 'main' -or $sourceSha -ne $originMain) {
    throw 'Apply requires a clean local main that exactly matches origin/main.'
}
if ($sourceDirty.Count -ne 0) {
    throw 'Apply requires a clean worktree, including untracked source files.'
}
if ($RunIdPrefix -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$') {
    throw 'RunIdPrefix must use 1-40 safe ASCII characters.'
}

try {
    $rawVolumeNames = @(& docker volume ls --quiet 2>$null)
    $volumeListExitCode = $LASTEXITCODE
}
catch {
    throw 'Docker Volume 목록을 확인할 수 없습니다.'
}
if ($volumeListExitCode -ne 0) {
    throw 'Docker Volume 목록을 확인할 수 없습니다.'
}
$volumeNames = @(
    foreach ($rawVolumeName in $rawVolumeNames) {
        $normalizedVolumeName = ([string]$rawVolumeName).Trim()
        if (-not [string]::IsNullOrWhiteSpace($normalizedVolumeName)) {
            $normalizedVolumeName
        }
    }
)
$volumeExists = $volumeNames -contains $volumeName

if (Test-Path -LiteralPath $RuntimeRoot) {
    if (-not $ReuseLocalRuntime) {
        throw 'Local Runtime already exists. Use -ReuseLocalRuntime explicitly.'
    }
    foreach ($path in @(
        $adminEnvironment,
        $rolesEnvironment,
        $composeOverride,
        $sourceShaPath
    )) {
        Assert-File $path
    }
    if (-not $volumeExists) {
        throw 'Runtime files exist but the matching isolated Volume is missing.'
    }
    $recordedSourceSha = (
        Get-Content -LiteralPath $sourceShaPath -Raw -Encoding UTF8
    ).Trim()
    if ($recordedSourceSha -ne $sourceSha) {
        throw 'Existing Runtime source SHA differs. Use a new RuntimeRoot.'
    }
}
else {
    if ($volumeExists) {
        throw (
            'Isolated Volume exists without matching Runtime files. ' +
            'Do not delete or reuse it automatically.'
        )
    }
    & $runtimeInitializer -RuntimeRoot $RuntimeRoot | Out-Null
    New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
    Set-EnvironmentEntry -Path $adminEnvironment -Name 'POSTGRES_PORT' `
        -Value ([string]$PostgresPort)
    $overrideContent = @"
name: $composeProject
services:
  postgres:
    container_name: $containerName
volumes:
  team-integration-postgres-data:
    name: $volumeName
"@
    [System.IO.File]::WriteAllText(
        $composeOverride,
        $overrideContent,
        [System.Text.UTF8Encoding]::new($false)
    )
    [System.IO.File]::WriteAllText(
        $sourceShaPath,
        $sourceSha,
        [System.Text.UTF8Encoding]::new($false)
    )
}
New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null

$composeArguments = @(
    'compose',
    '--project-name', $composeProject,
    '--env-file', $adminEnvironment,
    '-f', $composeFile,
    '-f', $composeOverride
)
Invoke-Checked -Command 'docker' -Arguments @(
    $composeArguments + @('up', '-d', 'postgres')
)

$deadline = [DateTime]::UtcNow.AddSeconds(90)
$databaseHealthy = $false
while ([DateTime]::UtcNow -lt $deadline) {
    $health = (& docker inspect --format '{{.State.Health.Status}}' `
        $containerName 2>$null)
    if ($LASTEXITCODE -eq 0 -and $health -eq 'healthy') {
        $databaseHealthy = $true
        break
    }
    Start-Sleep -Seconds 2
}
if (-not $databaseHealthy) {
    throw 'The isolated PostgreSQL container did not become healthy.'
}

. $environmentLoader -RuntimeRoot $RuntimeRoot -Role Admin | Out-Null
Invoke-Checked -Command $backendPython -Arguments @(
    '-B', $provisioner,
    '--apply',
    '--confirm-database', 'waterbridge_team_integration'
)

. $environmentLoader -RuntimeRoot $RuntimeRoot -Role Migrator | Out-Null
Set-DjangoRuntimeEnvironment
Invoke-Checked -Command $backendPython -Arguments @(
    '-B', $migrationRunner
)
Invoke-Checked -Command $backendPython -Arguments @(
    '-B', $migrationRunner,
    '--apply',
    '--confirm-database', 'waterbridge_team_integration',
    '--confirm-source-sha', $sourceSha,
    '--confirm-hold', 'visits.0005=P1_HOLD_EXCLUDED'
)

. $environmentLoader -RuntimeRoot $RuntimeRoot -Role Admin | Out-Null
Invoke-Checked -Command $backendPython -Arguments @(
    '-B', $provisioner,
    '--apply',
    '--confirm-database', 'waterbridge_team_integration'
)

. $environmentLoader -RuntimeRoot $RuntimeRoot -Role Runtime | Out-Null
Set-DjangoRuntimeEnvironment
Invoke-Checked -Command $backendPython -Arguments @(
    $managePy, 'check'
)
foreach ($seedCommand in @(
    'seed_common_codes',
    'seed_demo_accounts',
    'seed_demo_products',
    'seed_demo_subscriptions'
)) {
    Invoke-Checked -Command $backendPython -Arguments @(
        $managePy, $seedCommand
    )
}
Invoke-Checked -Command $backendPython -Arguments @(
    $managePy, 'seed_consultant_dashboard', '--dry-run'
)
Invoke-Checked -Command $backendPython -Arguments @(
    $managePy, 'seed_consultant_dashboard'
)

$concealedFixture = Invoke-JsonManagementCommand -Arguments @(
    'create_web_concealed_e2e_fixture',
    '--run-id', "$RunIdPrefix-concealed",
    '--json'
)
if (
    $concealedFixture.fixture_readiness -ne 'READY' -or
    $concealedFixture.expected_http_status -ne 404 -or
    [string]::IsNullOrWhiteSpace($concealedFixture.inquiry_id)
) {
    throw 'Concealed Web G4 fixture did not satisfy its public contract.'
}
[System.IO.File]::WriteAllText(
    $fixturePath,
    ($concealedFixture | ConvertTo-Json -Depth 5),
    [System.Text.UTF8Encoding]::new($false)
)

. $environmentLoader -RuntimeRoot $RuntimeRoot -Role Migrator | Out-Null
Set-DjangoRuntimeEnvironment
Invoke-Checked -Command $backendPython -Arguments @(
    '-B', $migrationRunner
)

$status = [ordered]@{
    status = 'WEB_G4_LOCAL_RUNTIME_BOOTSTRAPPED'
    source_sha = $sourceSha
    database = 'waterbridge_team_integration'
    postgres_health = 'PASS'
    migration_gate = 'READY'
    visits_0005 = 'NOT_APPLIED_P1_HOLD'
    demo_seed = 'READY'
    g2_g3 = 'NOT_APPLICABLE_FOR_WEB_G4'
    concealed_fixture = 'READY'
    concealed_inquiry_id = $concealedFixture.inquiry_id
    fixture_path = '.runtime/web-g4-local/evidence/web-g4-concealed-fixture.json'
    postgres_port = $PostgresPort
    volume = $volumeName
    backend_health = 'START_REQUIRED'
    backend_base_url = 'http://127.0.0.1:8000'
    secret_values_printed = $false
}
[System.IO.File]::WriteAllText(
    $statusPath,
    ($status | ConvertTo-Json -Depth 4),
    [System.Text.UTF8Encoding]::new($false)
)
$status | ConvertTo-Json -Depth 4
