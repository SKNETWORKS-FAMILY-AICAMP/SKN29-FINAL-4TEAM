[CmdletBinding()]
param(
    [switch]$Apply,
    [string]$RunIdPrefix,
    [ValidateRange(1024, 65535)]
    [int]$PostgresPort = 55439,
    [ValidateRange(1024, 65535)]
    [int]$BackendPort = 18000,
    [string]$RuntimeRoot,
    [string]$BackendPython,
    [string]$AiPython,
    [string[]]$OfficialSourceSearchRoots,
    [switch]$ReuseLocalRuntime
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
if (-not $AiPython) {
    $AiPython = Join-Path $repositoryRoot 'ai\.venv\Scripts\python.exe'
}
$backendPython = [System.IO.Path]::GetFullPath($BackendPython)
$aiPython = [System.IO.Path]::GetFullPath($AiPython)
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
$readinessAuditor = Join-Path (
    $repositoryRoot
) 'scripts\database\audit_backend_ai_g1b_readiness.py'
$composeFile = Join-Path (
    $repositoryRoot
) 'infra\docker\compose\team-integration\compose.yaml'
$environmentRoot = Join-Path $RuntimeRoot 'env'
$adminEnvironment = Join-Path $environmentRoot 'admin.env'
$handoffEnvironment = Join-Path $environmentRoot 'ai-context-handoff.env'
$evidenceRoot = Join-Path $RuntimeRoot 'evidence'
$embeddingFixture = Join-Path (
    $evidenceRoot
) 'canonical_embedding_fixture_v1.json'
$crosswalkPath = Join-Path $evidenceRoot 'five-case-crosswalk.json'
$composeOverride = Join-Path $RuntimeRoot 'compose.override.yaml'
$composeProject = 'waterbridge-ai-context-local'
$containerName = 'waterbridge-ai-context-local-postgres'
$volumeName = 'waterbridge-ai-context-local-postgres-data'

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
    $lastLine = @($output | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })[-1]
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

function Set-DjangoRuntimeEnvironment {
    param([Parameter(Mandatory)][string]$HandoffToken)

    $values = @{
        DJANGO_SETTINGS_MODULE = 'config.settings.local'
        DJANGO_SECRET_KEY = $HandoffToken
        DJANGO_DEBUG = 'true'
        DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1,[::1]'
        DJANGO_CORS_ALLOWED_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173'
        DJANGO_TIME_ZONE = 'Asia/Seoul'
        DJANGO_LOG_LEVEL = 'INFO'
        DJANGO_DEMO_LOGIN_ENABLED = 'true'
        AI_HANDOFF_INTERNAL_TOKEN = $HandoffToken
        AI_SERVICE_BASE_URL = 'http://127.0.0.1:8001'
        AI_SERVICE_MODE = 'local'
        AI_MODEL_PROVIDER = 'openai'
        AI_MODEL_NAME = 'gpt-4.1-mini'
        AI_PROMPT_VERSION = 'customer_guidance/v3'
    }
    foreach ($entry in $values.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable(
            $entry.Key,
            $entry.Value,
            'Process'
        )
    }
}

function New-ProtectedToken {
    $bytes = [byte[]]::new(32)
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    return [System.BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
}

function Write-ProtectedEnvironment {
    param(
        [Parameter(Mandatory)][string]$Token,
        [Parameter(Mandatory)][string]$SourceSha
    )

    $lines = @(
        "AI_BACKEND_BASE_URL=http://127.0.0.1:$BackendPort"
        "AI_HANDOFF_INTERNAL_TOKEN=$Token"
        'AI_RETRIEVAL_TRANSPORT=mcp'
        'AI_RAG_RUNTIME_PROFILE=mvp'
        'AI_BACKEND_CONTEXT_TIMEOUT_SECONDS=5'
        'AI_MCP_CONTEXT_TIMEOUT_SECONDS=8'
        'NO_PROXY=localhost,127.0.0.1,::1'
        'no_proxy=localhost,127.0.0.1,::1'
        "BACKEND_MAIN_SHA=$SourceSha"
        'BACKEND_CONTEXT_DATABASE=waterbridge_team_integration'
        'AI_CONTEXT_CASE_FILE=.runtime/ai-context-local/evidence/five-case-crosswalk.json'
    )
    [System.IO.File]::WriteAllLines(
        $handoffEnvironment,
        $lines,
        [System.Text.UTF8Encoding]::new($false)
    )
}

foreach ($requiredFile in @(
    $backendPython,
    $aiPython,
    $managePy,
    $environmentLoader,
    $runtimeInitializer,
    $provisioner,
    $migrationRunner,
    $readinessAuditor,
    $composeFile
)) {
    Assert-File $requiredFile
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker Desktop CLI is required.'
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
$preflight = [ordered]@{
    status = if ($Apply) { 'APPLY_REQUESTED' } else { 'PLAN_READY' }
    mutates_local_environment = [bool]$Apply
    branch = $branch
    source_sha = $sourceSha
    origin_main_sha = $originMain
    exact_origin_main = $sourceSha -eq $originMain
    worktree_clean = $sourceDirty.Count -eq 0
    runtime_root = '.runtime/ai-context-local'
    target_database = 'waterbridge_team_integration'
    postgres_port = $PostgresPort
    backend_base_url = "http://127.0.0.1:$BackendPort"
    public_runtime = 'mvp'
    visits_0005 = 'P1_HOLD_EXCLUDED'
    secrets_printed = $false
}
if (-not $Apply) {
    $preflight | ConvertTo-Json -Depth 4
    return
}

if ($branch -ne 'main' -or $sourceSha -ne $originMain) {
    throw 'Apply requires a clean local main that exactly matches origin/main.'
}
if ($sourceDirty.Count -ne 0) {
    throw 'Apply requires a clean worktree, including untracked source files.'
}
if ($RunIdPrefix -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$') {
    throw 'RunIdPrefix must use 1-40 safe ASCII characters.'
}
if (-not $OfficialSourceSearchRoots -or $OfficialSourceSearchRoots.Count -eq 0) {
    throw 'OfficialSourceSearchRoots is required for the canonical JAC104 import.'
}
foreach ($searchRoot in $OfficialSourceSearchRoots) {
    if (-not (Test-Path -LiteralPath $searchRoot -PathType Container)) {
        throw 'An official source search root does not exist.'
    }
}
$canonicalSourceSearchRoots = @($OfficialSourceSearchRoots)

if (Test-Path -LiteralPath $RuntimeRoot) {
    if (-not $ReuseLocalRuntime) {
        throw 'Local Runtime already exists. Use -ReuseLocalRuntime explicitly.'
    }
    Assert-File $adminEnvironment
    Assert-File (Join-Path $environmentRoot 'roles.env')
}
else {
    & $runtimeInitializer -RuntimeRoot $RuntimeRoot | Out-Null
}
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
    $health = (& docker inspect --format '{{.State.Health.Status}}' $containerName 2>$null)
    if ($LASTEXITCODE -eq 0 -and $health -eq 'healthy') {
        $databaseHealthy = $true
        break
    }
    Start-Sleep -Seconds 2
}
if (-not $databaseHealthy) {
    throw 'The isolated PostgreSQL container did not become healthy.'
}

$handoffToken = New-ProtectedToken
. $environmentLoader -RuntimeRoot $RuntimeRoot -Role Admin | Out-Null
Invoke-Checked -Command $backendPython -Arguments @(
    '-B', $provisioner,
    '--apply',
    '--confirm-database', 'waterbridge_team_integration'
)

. $environmentLoader -RuntimeRoot $RuntimeRoot -Role Migrator | Out-Null
Set-DjangoRuntimeEnvironment -HandoffToken $handoffToken
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

. $environmentLoader -RuntimeRoot $RuntimeRoot -Role Runtime `
    -LoadOfficialSource `
    -OfficialSourceSearchRoots $canonicalSourceSearchRoots | Out-Null
Set-DjangoRuntimeEnvironment -HandoffToken $handoffToken

Invoke-Checked -Command $backendPython -Arguments @(
    $managePy, 'seed_demo_accounts'
)
Invoke-Checked -Command $backendPython -Arguments @(
    $managePy, 'import_synthetic_handoff', '--profile', 'db-smoke'
)
Invoke-Checked -Command $backendPython -Arguments @(
    $managePy, 'import_synthetic_handoff', '--profile', 'db-product-expansion'
)

Invoke-Checked -Command $aiPython -Arguments @(
    '-m', 'ai.scripts.export_canonical_embedding_fixture',
    '--output', $embeddingFixture
)
$fixtureSha = (
    Get-FileHash -LiteralPath $embeddingFixture -Algorithm SHA256
).Hash
Invoke-Checked -Command $backendPython -Arguments @(
    $managePy,
    'import_ai_canonical_evidence',
    '--embedding-fixture', $embeddingFixture,
    '--embedding-fixture-sha256', $fixtureSha,
    '--verified-by', 'DEMO-OPERATOR-001',
    '--apply',
    '--confirm-database', 'waterbridge_team_integration'
)
Invoke-Checked -Command $backendPython -Arguments @(
    $managePy,
    'sync_ai_canonical_crosswalk'
)
Invoke-Checked -Command $backendPython -Arguments @(
    $managePy,
    'sync_ai_canonical_crosswalk',
    '--apply',
    '--verified-by', 'DEMO-OPERATOR-001'
)

$jac104 = Invoke-JsonManagementCommand -Arguments @(
    'create_ai_context_e2e_fixture',
    '--run-id', "$RunIdPrefix-jac104",
    '--apply',
    '--confirm-database', 'waterbridge_team_integration',
    '--json'
)
$iac425General = Invoke-JsonManagementCommand -Arguments @(
    'create_product_expansion_e2e_fixture',
    '--model-code', 'WPUIAC425SNW',
    '--scenario-id', 'SYN-IAC425-101',
    '--run-id', "$RunIdPrefix-iac425-general",
    '--apply',
    '--enable-candidate-product',
    '--confirm-database', 'waterbridge_team_integration',
    '--json'
)
$iac425Leak = Invoke-JsonManagementCommand -Arguments @(
    'create_product_expansion_e2e_fixture',
    '--model-code', 'WPUIAC425SNW',
    '--scenario-id', 'SYN-IAC425-108',
    '--run-id', "$RunIdPrefix-iac425-leak",
    '--apply',
    '--confirm-database', 'waterbridge_team_integration',
    '--json'
)
$iac606General = Invoke-JsonManagementCommand -Arguments @(
    'create_product_expansion_e2e_fixture',
    '--model-code', 'WPUIAC606SNW',
    '--scenario-id', 'SYN-IAC606-101',
    '--run-id', "$RunIdPrefix-iac606-general",
    '--apply',
    '--enable-candidate-product',
    '--confirm-database', 'waterbridge_team_integration',
    '--json'
)
$iac606Leak = Invoke-JsonManagementCommand -Arguments @(
    'create_product_expansion_e2e_fixture',
    '--model-code', 'WPUIAC606SNW',
    '--scenario-id', 'SYN-IAC606-107',
    '--run-id', "$RunIdPrefix-iac606-leak",
    '--apply',
    '--confirm-database', 'waterbridge_team_integration',
    '--json'
)

$caseDefinitions = @(
    @('JAC104_NORMAL', $jac104),
    @('IAC425_GENERAL', $iac425General),
    @('IAC425_LEAK', $iac425Leak),
    @('IAC606_GENERAL', $iac606General),
    @('IAC606_LEAK', $iac606Leak)
)
$cases = @(
    foreach ($definition in $caseDefinitions) {
        $payload = $definition[1]
        [ordered]@{
            case_name = $definition[0]
            model_code = $payload.model_code
            inquiry_id = $payload.inquiry_id
            correlation_id = $payload.request_correlation_id
            status = $payload.status
            state_version = $payload.state_version
            symptom_type = if (
                $payload.PSObject.Properties['topic_code'] -and
                $payload.topic_code
            ) {
                $payload.topic_code
            }
            else {
                'LOW_FLOW'
            }
        }
    }
)
$crosswalk = [ordered]@{
    schema_version = '1.0.0'
    status = 'READY_FOR_LOCAL_CONTEXT_MCP_E2E'
    source_sha = $sourceSha
    database = 'waterbridge_team_integration'
    public_runtime = 'mvp'
    run_id_prefix = $RunIdPrefix
    cases = $cases
}
[System.IO.File]::WriteAllText(
    $crosswalkPath,
    ($crosswalk | ConvertTo-Json -Depth 6),
    [System.Text.UTF8Encoding]::new($false)
)
Write-ProtectedEnvironment -Token $handoffToken -SourceSha $sourceSha

. $environmentLoader -RuntimeRoot $RuntimeRoot -Role Readonly | Out-Null
Invoke-Checked -Command $backendPython -Arguments @(
    '-B', $readinessAuditor,
    '--require-ready',
    '--require-team-database',
    '--evidence-profile', 'baseline'
)

[ordered]@{
    status = 'LOCAL_RUNTIME_BOOTSTRAPPED'
    source_sha = $sourceSha
    target_database = 'waterbridge_team_integration'
    postgres_health = 'PASS'
    canonical_evidence = '7_ROWS_READY'
    context_cases = '5_READY'
    crosswalk = '.runtime/ai-context-local/evidence/five-case-crosswalk.json'
    handoff_environment = '.runtime/ai-context-local/env/ai-context-handoff.env'
    backend_base_url = "http://127.0.0.1:$BackendPort"
    public_runtime = 'mvp'
    next = 'Run start_ai_context_backend_local.ps1 in Backend terminal.'
    secret_values_printed = $false
} | ConvertTo-Json -Depth 4
