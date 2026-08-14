param(
    [ValidateSet('Admin', 'Migrator', 'Runtime', 'Readonly', 'AI', 'Matrix')]
    [string]$Role = 'Admin',
    [string]$RuntimeRoot,
    [switch]$LoadOfficialSource,
    [switch]$RequireOpenAIKey,
    [string[]]$OfficialSourceSearchRoots
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
if ($LoadOfficialSource -and $Role -ne 'Runtime') {
    throw 'Official source loading requires the Runtime role.'
}
if ($RequireOpenAIKey -and $Role -ne 'AI') {
    throw 'OpenAI key enforcement requires the AI role.'
}

function Read-EnvironmentFile {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw 'A required runtime environment file is missing.'
    }
    $result = @{}
    foreach ($line in Get-Content -LiteralPath $Path -Encoding utf8) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            $result[$Matches[1]] = $Matches[2]
        }
    }
    return $result
}

$admin = Read-EnvironmentFile (
    Join-Path $RuntimeRoot 'env\admin.env'
)
$roles = Read-EnvironmentFile (
    Join-Path $RuntimeRoot 'env\roles.env'
)

foreach ($entry in $roles.GetEnumerator()) {
    $roleSecretValue = if ($Role -in @('Admin', 'Matrix')) {
        $entry.Value
    }
    else {
        $null
    }
    [Environment]::SetEnvironmentVariable($entry.Key, $roleSecretValue, 'Process')
}

foreach ($variableName in @(
    'AI_VECTOR_DSN',
    'AI_VECTOR_TABLE_NAME',
    'AI_EMBEDDING_REVISION',
    'AI_LLM_MODEL',
    'OPENAI_API_KEY',
    'BACKEND_AI_OFFICIAL_SOURCE_PATH'
)) {
    [Environment]::SetEnvironmentVariable($variableName, $null, 'Process')
}

$roleMap = @{
    Admin = @('postgres', $admin.POSTGRES_USER, $admin.POSTGRES_PASSWORD)
    Migrator = @(
        'waterbridge_team_integration',
        'waterbridge_ti_migrator',
        $roles.TEAM_INTEGRATION_MIGRATOR_PASSWORD
    )
    Runtime = @(
        'waterbridge_team_integration',
        'waterbridge_ti_runtime',
        $roles.TEAM_INTEGRATION_RUNTIME_PASSWORD
    )
    Readonly = @(
        'waterbridge_team_integration',
        'waterbridge_ti_readonly',
        $roles.TEAM_INTEGRATION_READONLY_PASSWORD
    )
    AI = @(
        'waterbridge_team_integration',
        'waterbridge_ti_ai_readonly',
        $roles.TEAM_INTEGRATION_AI_PASSWORD
    )
    Matrix = @(
        'waterbridge_team_integration',
        'waterbridge_ti_readonly',
        $roles.TEAM_INTEGRATION_READONLY_PASSWORD
    )
}

$selected = $roleMap[$Role]
$common = @{
    POSTGRES_DB = $selected[0]
    POSTGRES_USER = $selected[1]
    POSTGRES_PASSWORD = $selected[2]
    POSTGRES_HOST = $admin.POSTGRES_HOST
    POSTGRES_PORT = $admin.POSTGRES_PORT
    POSTGRES_CONNECT_TIMEOUT = $admin.POSTGRES_CONNECT_TIMEOUT
    POSTGRES_SSLMODE = $admin.POSTGRES_SSLMODE
}
foreach ($entry in $common.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable(
        $entry.Key,
        $entry.Value,
        'Process'
    )
}

$openAIKeyLoaded = $false
$aiReadonlyDsnLoaded = $false
if ($Role -eq 'AI') {
    $encodedUser = [System.Uri]::EscapeDataString($selected[1])
    $encodedPassword = [System.Uri]::EscapeDataString($selected[2])
    $dsn = (
        'postgresql://{0}:{1}@{2}:{3}/{4}?sslmode={5}' -f
        $encodedUser,
        $encodedPassword,
        $admin.POSTGRES_HOST,
        $admin.POSTGRES_PORT,
        $selected[0],
        $admin.POSTGRES_SSLMODE
    )
    $aiReadonlyDsnLoaded = $true
    [Environment]::SetEnvironmentVariable('AI_VECTOR_DSN', $dsn, 'Process')
    [Environment]::SetEnvironmentVariable(
        'AI_VECTOR_TABLE_NAME',
        'backend_ai_rag_chunks_v1',
        'Process'
    )
    [Environment]::SetEnvironmentVariable(
        'AI_EMBEDDING_REVISION',
        '5617a9f61b028005a4858fdac845db406aefb181',
        'Process'
    )
    [Environment]::SetEnvironmentVariable(
        'AI_LLM_MODEL',
        'gpt-4.1-mini',
        'Process'
    )

    $aiEnvironmentPath = Join-Path $RuntimeRoot 'env\ai.env'
    if (Test-Path -LiteralPath $aiEnvironmentPath) {
        $aiEnvironment = Read-EnvironmentFile $aiEnvironmentPath
        $openAIKey = $aiEnvironment.OPENAI_API_KEY
        if (
            [string]::IsNullOrWhiteSpace($openAIKey) -or
            $openAIKey.Contains("`r") -or
            $openAIKey.Contains("`n")
        ) {
            throw 'The protected OpenAI key is invalid.'
        }
        [Environment]::SetEnvironmentVariable(
            'OPENAI_API_KEY',
            $openAIKey,
            'Process'
        )
        $openAIKeyLoaded = $true
    }
    if ($RequireOpenAIKey -and -not $openAIKeyLoaded) {
        throw 'The AI process requires a protected OpenAI key.'
    }
}

$officialSourceStatus = 'NOT_REQUESTED'
if ($LoadOfficialSource) {
    $expectedSourceSize = 5131906
    $expectedSourceHash = (
        '0c6b94af53f23211f5fe542cb7712109e4a769a6f42ed758da7792fc62e44b2c'
    )
    if (-not $OfficialSourceSearchRoots) {
        if ([string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
            throw 'The user profile root is unavailable.'
        }
        $OfficialSourceSearchRoots = @(
            (Join-Path $env:USERPROFILE 'Downloads'),
            (Join-Path $env:USERPROFILE 'Documents'),
            (Join-Path $env:USERPROFILE 'Desktop')
        )
    }

    $matches = @{}
    foreach ($searchRoot in $OfficialSourceSearchRoots) {
        if (-not (Test-Path -LiteralPath $searchRoot)) {
            continue
        }
        foreach (
            $candidate in Get-ChildItem -LiteralPath $searchRoot -Filter '*.pdf' `
                -File -Recurse -ErrorAction SilentlyContinue
        ) {
            if ($candidate.Length -ne $expectedSourceSize) {
                continue
            }
            $candidateHash = (
                Get-FileHash -LiteralPath $candidate.FullName -Algorithm SHA256
            ).Hash.ToLowerInvariant()
            if ($candidateHash -eq $expectedSourceHash) {
                $matches[$candidate.FullName] = $candidate.FullName
            }
        }
    }
    if ($matches.Count -ne 1) {
        throw 'The official source must have exactly one size and SHA-256 match.'
    }
    $officialSourcePath = @($matches.Values)[0]
    [Environment]::SetEnvironmentVariable(
        'BACKEND_AI_OFFICIAL_SOURCE_PATH',
        $officialSourcePath,
        'Process'
    )
    $officialSourceStatus = 'PASS'
}

[pscustomobject]@{
    status = 'LOADED'
    role = $Role
    target_database = $selected[0]
    official_source_size_hash = $officialSourceStatus
    openai_key = if ($openAIKeyLoaded) { 'YES' } else { 'NO' }
    ai_readonly_dsn = if ($aiReadonlyDsnLoaded) { 'YES' } else { 'NO' }
    secret_values_printed = $false
}
