[CmdletBinding()]
param(
    [switch]$Apply,
    [string]$ApprovedCustomerInput,
    [ValidateRange(1024, 65535)]
    [int]$PostgresPort = 55445,
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

if (-not $BackendPython) {
    $BackendPython = Join-Path (
        $repositoryRoot
    ) 'backend\.venv\Scripts\python.exe'
}
$backendPython = [System.IO.Path]::GetFullPath($BackendPython)
$managePy = Join-Path $repositoryRoot 'backend\manage.py'
$runtimeInitializer = Join-Path (
    $repositoryRoot
) 'scripts\deployment\initialize_team_integration_runtime.ps1'
$environmentLoader = Join-Path (
    $repositoryRoot
) 'scripts\development\import_p1_team_isolated_env.ps1'
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
$djangoEnvironment = Join-Path $environmentRoot 'runtime.env'
$evidenceRoot = Join-Path $RuntimeRoot 'evidence'
$statusPath = Join-Path $evidenceRoot 'p1-team-bootstrap-status.json'
$sourceShaPath = Join-Path $RuntimeRoot 'source-sha.txt'
$sourceBranchPath = Join-Path $RuntimeRoot 'source-branch.txt'
$composeOverride = Join-Path $RuntimeRoot 'compose.override.yaml'
$composeProject = 'waterbridge-p1-team-isolated'
$containerName = 'waterbridge-p1-team-isolated-postgres'
$volumeName = 'waterbridge-p1-team-isolated-postgres-data'
$targetDatabase = 'waterbridge_p1_team_isolated'
$profileName = 'p1-team-isolated'
$holdConfirmation = 'visits.0005=P1_HOLD_EXCLUDED'

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

function Invoke-JsonCommand {
    param(
        [Parameter(Mandatory)][string]$Command,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    $output = @(& $Command @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        $output | Write-Output
        throw "JSON command failed without exposing protected values: $Command"
    }
    try {
        return (($output -join "`n") | ConvertFrom-Json)
    }
    catch {
        throw 'Command did not return the expected JSON contract.'
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

function New-RuntimeSecret {
    $bytes = [byte[]]::new(48)
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    return [Convert]::ToBase64String($bytes)
}

function Restore-ProcessEnvironment {
    foreach ($name in $managedEnvironmentNames) {
        [Environment]::SetEnvironmentVariable(
            $name,
            $previousEnvironment[$name],
            'Process'
        )
    }
}

foreach ($requiredFile in @(
    $backendPython,
    $managePy,
    $runtimeInitializer,
    $environmentLoader,
    $provisioner,
    $migrationRunner,
    $composeFile
)) {
    Assert-File $requiredFile
}

$sourceSha = (& git -C $repositoryRoot rev-parse HEAD).Trim()
$branch = (& git -C $repositoryRoot branch --show-current).Trim()
$sourceDirty = @(
    & git -C $repositoryRoot status --porcelain --untracked-files=normal 2>$null
)
if ($LASTEXITCODE -ne 0) {
    throw 'Git source state could not be inspected safely.'
}
$remoteRef = switch ($branch) {
    'main' { 'origin/main' }
    'jiyong' { 'origin/jiyong' }
    default { $null }
}
$remoteSha = if ($remoteRef) {
    (& git -C $repositoryRoot rev-parse $remoteRef 2>$null).Trim()
}
else {
    ''
}
$dockerReady = [bool](Get-Command docker -ErrorAction SilentlyContinue)
$preflight = [ordered]@{
    status = if ($Apply) { 'APPLY_REQUESTED' } else { 'PLAN_READY' }
    mutates_local_environment = [bool]$Apply
    branch = $branch
    source_sha = $sourceSha
    tracking_ref = $remoteRef
    exact_tracking_ref = [bool]($remoteRef -and $sourceSha -eq $remoteSha)
    worktree_clean = $sourceDirty.Count -eq 0
    docker_cli = if ($dockerReady) { 'READY' } else { 'BLOCKED' }
    runtime_root = '.runtime/p1-team-isolated'
    target_database = $targetDatabase
    postgres_port = $PostgresPort
    compose_project = $composeProject
    volume = $volumeName
    approved_customer_input_required = -not $ReuseLocalRuntime
    visits_0005 = 'P1_HOLD_EXCLUDED'
    ai_runtime_8001 = 'OUT_OF_SCOPE'
    secrets_printed = $false
}
if (-not $Apply) {
    $preflight | ConvertTo-Json -Depth 4
    return
}

if (-not $dockerReady) {
    throw 'Docker Desktop CLI is required for the isolated P1 runtime.'
}
Invoke-Checked -Command 'docker' -Arguments @('version')
Invoke-Checked -Command 'docker' -Arguments @('compose', 'version')
if ($branch -notin @('main', 'jiyong') -or -not $remoteRef) {
    throw 'Apply is allowed only on main or the jiyong validation branch.'
}
if ($sourceSha -ne $remoteSha) {
    throw 'Apply requires HEAD to exactly match its origin tracking branch.'
}
if ($sourceDirty.Count -ne 0) {
    throw 'Apply requires a clean worktree, including untracked source files.'
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
        $normalized = ([string]$rawVolumeName).Trim()
        if (-not [string]::IsNullOrWhiteSpace($normalized)) {
            $normalized
        }
    }
)
$volumeExists = $volumeNames -contains $volumeName
$newRuntime = -not (Test-Path -LiteralPath $RuntimeRoot)

if (-not $newRuntime) {
    if (-not $ReuseLocalRuntime) {
        throw 'P1 Runtime already exists. Use -ReuseLocalRuntime explicitly.'
    }
    foreach ($path in @(
        $adminEnvironment,
        $rolesEnvironment,
        $djangoEnvironment,
        $composeOverride,
        $sourceShaPath,
        $sourceBranchPath
    )) {
        Assert-File $path
    }
    if (-not $volumeExists) {
        throw 'Runtime files exist but the matching isolated Volume is missing.'
    }
    $recordedSourceSha = (
        Get-Content -LiteralPath $sourceShaPath -Raw -Encoding UTF8
    ).Trim()
    $recordedBranch = (
        Get-Content -LiteralPath $sourceBranchPath -Raw -Encoding UTF8
    ).Trim()
    if ($recordedSourceSha -ne $sourceSha -or $recordedBranch -ne $branch) {
        throw 'Existing P1 Runtime source identity differs. Use a new RuntimeRoot.'
    }
}
else {
    if ($ReuseLocalRuntime) {
        throw 'Reuse was requested, but the P1 Runtime does not exist.'
    }
    if ($volumeExists) {
        throw (
            'P1 Volume exists without matching Runtime files. ' +
            'Do not delete or reuse it automatically.'
        )
    }
    if ([string]::IsNullOrWhiteSpace($ApprovedCustomerInput)) {
        throw 'ApprovedCustomerInput is required for the first Apply.'
    }
    $approvedInput = [System.IO.Path]::GetFullPath($ApprovedCustomerInput)
    Assert-File $approvedInput
    $approvedInputPrefix = (
        [System.IO.Path]::GetFullPath(
            (Join-Path $repositoryRoot 'backend\.runtime')
        ).TrimEnd('\') + '\'
    )
    if (-not $approvedInput.StartsWith(
        $approvedInputPrefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw 'ApprovedCustomerInput must stay under backend/.runtime.'
    }

    & $runtimeInitializer -RuntimeRoot $RuntimeRoot | Out-Null
    New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
    Set-EnvironmentEntry -Path $adminEnvironment -Name 'POSTGRES_PORT' `
        -Value ([string]$PostgresPort)
    [System.IO.File]::WriteAllLines(
        $djangoEnvironment,
        @(
            'DJANGO_SETTINGS_MODULE=config.settings.local',
            "DJANGO_SECRET_KEY=$(New-RuntimeSecret)",
            'DJANGO_DEBUG=true',
            'DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,[::1]',
            'DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173',
            'DJANGO_TIME_ZONE=Asia/Seoul',
            'DJANGO_LOG_LEVEL=INFO',
            'AI_SERVICE_BASE_URL=http://127.0.0.1:8001',
            'AI_SERVICE_MODE=local',
            'NO_PROXY=localhost,127.0.0.1,::1'
        ),
        [System.Text.UTF8Encoding]::new($false)
    )
    $overrideContent = @"
name: $composeProject
services:
  postgres:
    container_name: $containerName
    labels:
      waterbridge.environment: p1-team-isolated
      waterbridge.data-classification: approved-test-synthetic-only
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
    [System.IO.File]::WriteAllText(
        $sourceBranchPath,
        $branch,
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

try {
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
        throw 'The isolated P1 PostgreSQL container did not become healthy.'
    }

    if ($newRuntime) {
        . $environmentLoader -RuntimeRoot $RuntimeRoot -Role Admin | Out-Null
        Invoke-Checked -Command $backendPython -Arguments @(
            '-B', $provisioner,
            '--profile', $profileName,
            '--apply',
            '--confirm-database', $targetDatabase
        )

        . $environmentLoader -RuntimeRoot $RuntimeRoot -Role Migrator | Out-Null
        Invoke-Checked -Command $backendPython -Arguments @(
            '-B', $migrationRunner,
            '--profile', $profileName
        )
        Invoke-Checked -Command $backendPython -Arguments @(
            '-B', $migrationRunner,
            '--profile', $profileName,
            '--apply',
            '--confirm-database', $targetDatabase,
            '--confirm-source-sha', $sourceSha,
            '--confirm-hold', $holdConfirmation
        )

        . $environmentLoader -RuntimeRoot $RuntimeRoot -Role Admin | Out-Null
        Invoke-Checked -Command $backendPython -Arguments @(
            '-B', $provisioner,
            '--profile', $profileName,
            '--apply',
            '--confirm-database', $targetDatabase
        )

        . $environmentLoader -RuntimeRoot $RuntimeRoot -Role Runtime | Out-Null
        Invoke-Checked -Command $backendPython -Arguments @(
            $managePy, 'check'
        )
        Invoke-Checked -Command $backendPython -Arguments @(
            $managePy, 'seed_common_codes'
        )
        $consultantDryRun = Invoke-JsonCommand -Command $backendPython `
            -Arguments @(
                $managePy, 'seed_p1_team_consultant',
                '--confirm-isolated', '--dry-run', '--json'
            )
        $consultantApply = Invoke-JsonCommand -Command $backendPython `
            -Arguments @(
                $managePy, 'seed_p1_team_consultant',
                '--confirm-isolated', '--json'
            )
        $customerDryRun = Invoke-JsonCommand -Command $backendPython `
            -Arguments @(
                $managePy, 'seed_p1_approved_test_customers',
                '--input-file', $approvedInput,
                '--pm-approved-local-e2e', '--dry-run', '--json'
            )
        $customerApply = Invoke-JsonCommand -Command $backendPython `
            -Arguments @(
                $managePy, 'seed_p1_approved_test_customers',
                '--input-file', $approvedInput,
                '--pm-approved-local-e2e', '--json'
            )
        $customerReplay = Invoke-JsonCommand -Command $backendPython `
            -Arguments @(
                $managePy, 'seed_p1_approved_test_customers',
                '--input-file', $approvedInput,
                '--pm-approved-local-e2e', '--json'
            )
        if (
            $consultantDryRun.status -ne 'DRY_RUN_READY' -or
            $consultantApply.status -ne 'APPLIED' -or
            $customerDryRun.status -ne 'DRY_RUN_READY' -or
            $customerApply.status -ne 'APPLIED' -or
            $customerReplay.customers_created -ne 0 -or
            $customerReplay.contacts_created -ne 0 -or
            $customerReplay.subscriptions_created -ne 0
        ) {
            throw 'P1 consultant or approved customer seed verification failed.'
        }
    }
    else {
        . $environmentLoader -RuntimeRoot $RuntimeRoot -Role Runtime | Out-Null
        Invoke-Checked -Command $backendPython -Arguments @(
            $managePy, 'check'
        )
    }

    $auditArguments = @($managePy, 'audit_p1_team_runtime_scope', '--json')
    if (-not $newRuntime) {
        $auditArguments += '--operational'
    }
    $audit = Invoke-JsonCommand -Command $backendPython `
        -Arguments $auditArguments
    if (
        $audit.database_name -ne $targetDatabase -or
        $audit.preserve.customers -ne 6 -or
        $audit.preserve.active_primary_contacts -ne 6 -or
        $audit.preserve.active_subscriptions -ne 6 -or
        $audit.preserve.consultant_users -ne 1 -or
        $audit.delete_candidates.customers -ne 0 -or
        @($audit.blockers).Count -ne 0
    ) {
        throw 'P1 isolated DB scope audit did not satisfy the baseline.'
    }
    if ($newRuntime -and $audit.delete_candidates.inquiries -ne 0) {
        throw 'A new P1 isolated DB must start with zero inquiries.'
    }

    $contractE2E = $null
    if ($newRuntime) {
        $contractE2E = Invoke-JsonCommand -Command $backendPython `
            -Arguments @(
                $managePy, 'verify_p1_team_isolated_e2e'
            )
        if (
            -not $contractE2E.signup -or
            -not $contractE2E.login -or
            -not $contractE2E.inquiry_created -or
            $contractE2E.inquiry_status -ne 'DRAFT' -or
            $contractE2E.inquiry_state_version -ne 1 -or
            -not $contractE2E.consultant_login -or
            -not $contractE2E.rollback_preserved -or
            $contractE2E.ai_called
        ) {
            throw 'P1 auth/login/inquiry rollback verification failed.'
        }
    }

    . $environmentLoader -RuntimeRoot $RuntimeRoot -Role Migrator | Out-Null
    $migrationGate = Invoke-JsonCommand -Command $backendPython `
        -Arguments @('-B', $migrationRunner, '--profile', $profileName)
    if (
        $migrationGate.status -ne 'ALREADY_APPLIED' -or
        $migrationGate.expected_final.'visits.0005' -ne 'NOT_APPLIED_P1_HOLD' -or
        @($migrationGate.remaining_plan).Count -ne 0
    ) {
        throw 'P1 Migration HOLD gate did not reach the approved final state.'
    }

    $status = [ordered]@{
        status = 'P1_TEAM_ISOLATED_RUNTIME_READY'
        source_sha = $sourceSha
        source_branch = $branch
        database = $targetDatabase
        postgres_health = 'PASS'
        migration_gate = 'READY'
        visits_0005 = 'NOT_APPLIED_P1_HOLD'
        approved_customers = 6
        active_primary_contacts = 6
        active_subscriptions = 6
        consultant_users = 1
        inquiries = $audit.runtime.p1_owned_inquiries
        auth_login_inquiry_contract = if ($newRuntime) {
            'PASS_ROLLBACK_PRESERVED'
        }
        else {
            'NOT_RERUN_ON_REUSE'
        }
        inquiry_creation_without_ai = if ($newRuntime) { 'PASS' } else { 'PRESERVED' }
        ai_runtime_8001 = 'OUT_OF_SCOPE'
        postgres_port = $PostgresPort
        volume = $volumeName
        reuse = -not $newRuntime
        otp_worker = 'START_SEPARATELY'
        backend = 'START_SEPARATELY'
        secret_values_printed = $false
    }
    [System.IO.File]::WriteAllText(
        $statusPath,
        ($status | ConvertTo-Json -Depth 4),
        [System.Text.UTF8Encoding]::new($false)
    )
    $status | ConvertTo-Json -Depth 4
}
finally {
    Restore-ProcessEnvironment
}
