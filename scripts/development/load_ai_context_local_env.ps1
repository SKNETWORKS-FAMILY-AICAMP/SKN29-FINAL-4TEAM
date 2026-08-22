[CmdletBinding()]
param(
    [string]$RuntimeRoot,
    [switch]$RequireOpenAIKey
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($MyInvocation.InvocationName -ne '.') {
    throw 'Dot-source this script so the AI process inherits its environment.'
}

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

$loader = Join-Path (
    $repositoryRoot
) 'scripts\deployment\import_team_integration_env.ps1'
$handoffPath = Join-Path $RuntimeRoot 'env\ai-context-handoff.env'
$crosswalkPath = Join-Path $RuntimeRoot 'evidence\five-case-crosswalk.json'
foreach ($path in @($loader, $handoffPath, $crosswalkPath)) {
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
foreach ($requiredKey in @(
    'AI_BACKEND_BASE_URL',
    'AI_HANDOFF_INTERNAL_TOKEN',
    'AI_RETRIEVAL_TRANSPORT',
    'AI_RAG_RUNTIME_PROFILE'
)) {
    if (
        -not $handoff.ContainsKey($requiredKey) -or
        [string]::IsNullOrWhiteSpace($handoff[$requiredKey])
    ) {
        throw "Required protected handoff key is missing: $requiredKey"
    }
}

. $loader -RuntimeRoot $RuntimeRoot -Role AI `
    -RequireOpenAIKey:$RequireOpenAIKey | Out-Null
foreach ($key in @(
    'AI_BACKEND_BASE_URL',
    'AI_HANDOFF_INTERNAL_TOKEN',
    'AI_RETRIEVAL_TRANSPORT',
    'AI_RAG_RUNTIME_PROFILE',
    'AI_BACKEND_CONTEXT_TIMEOUT_SECONDS',
    'AI_MCP_CONTEXT_TIMEOUT_SECONDS',
    'NO_PROXY',
    'no_proxy'
)) {
    if ($handoff.ContainsKey($key)) {
        [Environment]::SetEnvironmentVariable(
            $key,
            $handoff[$key],
            'Process'
        )
    }
}

$health = Invoke-WebRequest -UseBasicParsing `
    -Uri "$($handoff.AI_BACKEND_BASE_URL)/health" `
    -TimeoutSec 5
if ($health.StatusCode -ne 200) {
    throw 'Local Backend health check failed.'
}

$crosswalk = Get-Content -LiteralPath $crosswalkPath -Raw -Encoding UTF8 |
    ConvertFrom-Json
$contextPass = 0
foreach ($case in $crosswalk.cases) {
    $headers = @{
        'X-AI-Handoff-Token' = $handoff.AI_HANDOFF_INTERNAL_TOKEN
        'X-Correlation-ID' = $case.correlation_id
    }
    $response = Invoke-RestMethod -Method Get `
        -Uri "$($handoff.AI_BACKEND_BASE_URL)/api/v1/internal/ai/inquiries/$($case.inquiry_id)/context" `
        -Headers $headers `
        -TimeoutSec 5
    if (
        $response.success -eq $true -and
        $response.data.inquiry_id -eq $case.inquiry_id -and
        $response.data.correlation_id -eq $case.correlation_id -and
        $response.data.state_version -eq 1
    ) {
        $contextPass++
    }
}
if ($contextPass -ne 5) {
    throw 'One or more local Backend Context cases failed.'
}

[pscustomobject]@{
    status = 'AI_CONTEXT_LOCAL_ENV_LOADED'
    backend_health = 'PASS'
    context_cases = '5/5_PASS'
    ai_backend_base_url = $handoff.AI_BACKEND_BASE_URL
    ai_handoff_token = 'PRESENT_NOT_PRINTED'
    retrieval_transport = $handoff.AI_RETRIEVAL_TRANSPORT
    runtime_profile = $handoff.AI_RAG_RUNTIME_PROFILE
    vector_dsn = if ($env:AI_VECTOR_DSN) { 'PRESENT_NOT_PRINTED' } else { 'MISSING' }
    openai_key = if ($env:OPENAI_API_KEY) { 'PRESENT_NOT_PRINTED' } else { 'MISSING' }
    secret_values_printed = $false
}
