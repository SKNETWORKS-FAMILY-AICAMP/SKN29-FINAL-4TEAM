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

$postgresPortWasSpecified = $PSBoundParameters.ContainsKey('PostgresPort')

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

if ([string]::IsNullOrWhiteSpace($ApprovedCustomerInput)) {
    $ApprovedCustomerInput = Join-Path (
        $repositoryRoot
    ) 'backend\.runtime\p1-approved-customers.json'
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
$expectedPostgresImage = 'pgvector/pgvector:0.8.6-pg16-bookworm'

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

function Get-EnvironmentEntry {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Name
    )

    $pattern = '^' + [regex]::Escape($Name) + '=(.*)$'
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ($line -match $pattern) {
            return $Matches[1]
        }
    }
    throw "Required Runtime entry is missing: $Name"
}

function Test-LoopbackPortAvailable {
    param([Parameter(Mandatory)][int]$Port)

    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        $Port
    )
    try {
        $listener.Start()
        return $true
    }
    catch [System.Net.Sockets.SocketException] {
        return $false
    }
    finally {
        $listener.Stop()
    }
}

function Find-AvailablePostgresPort {
    param([Parameter(Mandatory)][int]$PreferredPort)

    if (Test-LoopbackPortAvailable -Port $PreferredPort) {
        return $PreferredPort
    }
    if ($postgresPortWasSpecified) {
        throw "The requested PostgreSQL port is already in use: $PreferredPort"
    }
    foreach ($candidate in (($PreferredPort + 1)..55545)) {
        if (Test-LoopbackPortAvailable -Port $candidate) {
            return $candidate
        }
    }
    throw 'No free loopback PostgreSQL port was found in 55445..55545.'
}

function Protect-ApprovedCustomerInput {
    param([Parameter(Mandatory)][string]$Path)

    $identity = "${env:USERDOMAIN}\${env:USERNAME}"
    & icacls.exe $Path '/inheritance:r' '/grant:r' "${identity}:F" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to restrict approved customer input file permissions.'
    }
}

function Get-PostgresContainerContract {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][int]$ExpectedPort
    )

    $output = @(& docker inspect $Name 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw 'The isolated PostgreSQL container could not be inspected.'
    }
    try {
        $inspect = @(($output -join "`n") | ConvertFrom-Json)[0]
    }
    catch {
        throw 'Docker inspect did not return the expected JSON contract.'
    }
    $bindings = @($inspect.HostConfig.PortBindings.'5432/tcp')
    $binding = if ($bindings.Count -eq 1) { $bindings[0] } else { $null }
    $volumeMounts = @(
        $inspect.Mounts |
            Where-Object { $_.Destination -eq '/var/lib/postgresql/data' }
    )
    $labels = $inspect.Config.Labels
    if (
        $inspect.Name.TrimStart('/') -ne $Name -or
        $inspect.Config.Image -ne $expectedPostgresImage -or
        $labels.'com.docker.compose.project' -ne $composeProject -or
        $labels.'waterbridge.environment' -ne 'p1-team-isolated' -or
        $labels.'waterbridge.data-classification' -ne (
            'approved-test-synthetic-only'
        ) -or
        $null -eq $binding -or
        $binding.HostIp -ne '127.0.0.1' -or
        [int]$binding.HostPort -ne $ExpectedPort -or
        $volumeMounts.Count -ne 1 -or
        $volumeMounts[0].Name -ne $volumeName
    ) {
        throw 'The isolated PostgreSQL container contract does not match.'
    }
    return [pscustomobject]@{
        container_name = $Name
        image = $inspect.Config.Image
        image_id = $inspect.Image
        host_binding = "127.0.0.1:$ExpectedPort"
        volume = $volumeName
        compose_project = $composeProject
    }
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
$approvedInputPlanPath = 'backend/.runtime/p1-approved-customers.json'
$approvedInputPlanPresent = Test-Path -LiteralPath (
    [System.IO.Path]::GetFullPath($ApprovedCustomerInput)
) -PathType Leaf
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
    postgres_port = if ($postgresPortWasSpecified) {
        $PostgresPort
    }
    else {
        'AUTO_START_55445'
    }
    compose_project = $composeProject
    container = $containerName
    image = $expectedPostgresImage
    volume = $volumeName
    approved_customer_input = $approvedInputPlanPath
    approved_customer_input_present = $approvedInputPlanPresent
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
$initializeRuntime = -not (Test-Path -LiteralPath $RuntimeRoot)
$bootstrapPending = $initializeRuntime
$approvedInput = $null
$effectivePostgresPort = $PostgresPort

if (-not $initializeRuntime) {
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
    $recordedPostgresPort = Get-EnvironmentEntry `
        -Path $adminEnvironment -Name 'POSTGRES_PORT'
    if ($recordedPostgresPort -notmatch '^\d{4,5}$') {
        throw 'Existing P1 Runtime has an invalid recorded PostgreSQL port.'
    }
    $effectivePostgresPort = [int]$recordedPostgresPort
    if (
        $postgresPortWasSpecified -and
        $PostgresPort -ne $effectivePostgresPort
    ) {
        throw 'Requested PostgreSQL port differs from the existing Runtime.'
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
    $bootstrapPending = -not (Test-Path -LiteralPath $statusPath -PathType Leaf)
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
    $effectivePostgresPort = Find-AvailablePostgresPort `
        -PreferredPort $PostgresPort
    & $runtimeInitializer -RuntimeRoot $RuntimeRoot | Out-Null
    New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
    Set-EnvironmentEntry -Path $adminEnvironment -Name 'POSTGRES_PORT' `
        -Value ([string]$effectivePostgresPort)
    [System.IO.File]::WriteAllLines(
        $djangoEnvironment,
        @(
            'DJANGO_SETTINGS_MODULE=config.settings.local',
            "DJANGO_SECRET_KEY=$(New-RuntimeSecret)",
            'DJANGO_DEBUG=true',
            'DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,[::1]',
            'DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174',
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

if ($bootstrapPending) {
    if (-not (Test-Path -LiteralPath $ApprovedCustomerInput -PathType Leaf)) {
        throw (
            'Approved customer input is missing: ' +
            'backend/.runtime/p1-approved-customers.json. ' +
            'Receive it through the approved protected channel; never Git.'
        )
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
    Protect-ApprovedCustomerInput -Path $approvedInput
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
    $containerContract = Get-PostgresContainerContract `
        -Name $containerName -ExpectedPort $effectivePostgresPort

    if ($bootstrapPending) {
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
    if (-not $bootstrapPending) {
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
    if ($bootstrapPending -and $audit.delete_candidates.inquiries -ne 0) {
        throw 'A new P1 isolated DB must start with zero inquiries.'
    }

    $contractE2E = $null
    if ($bootstrapPending) {
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
        auth_login_inquiry_contract = if ($bootstrapPending) {
            'PASS_ROLLBACK_PRESERVED'
        }
        else {
            'NOT_RERUN_ON_REUSE'
        }
        inquiry_creation_without_ai = if ($bootstrapPending) {
            'PASS'
        }
        else {
            'PRESERVED'
        }
        ai_runtime_8001 = 'OUT_OF_SCOPE'
        postgres_port = $effectivePostgresPort
        container = $containerContract.container_name
        postgres_image = $containerContract.image
        postgres_image_id = $containerContract.image_id
        postgres_host_binding = $containerContract.host_binding
        volume = $volumeName
        compose_project = $containerContract.compose_project
        approved_customer_input_acl = if ($bootstrapPending) {
            'CURRENT_USER_ONLY'
        }
        else {
            'NOT_RECHECKED_ON_REUSE'
        }
        reuse = -not $bootstrapPending
        resumed_incomplete_runtime = (-not $initializeRuntime -and $bootstrapPending)
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
