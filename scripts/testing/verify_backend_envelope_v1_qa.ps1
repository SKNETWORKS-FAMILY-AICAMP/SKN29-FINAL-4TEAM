[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$ExpectedSha,

    [ValidateSet('Focused', 'Full')]
    [string]$Profile = 'Full',

    [string]$BackendPython = '',
    [string]$AiPython = '',
    [string]$OutputDir = '',
    [switch]$AllowDirty
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $BackendPython) {
    $BackendPython = Join-Path $repoRoot 'backend\.venv\Scripts\python.exe'
}
if (-not $AiPython) {
    $AiPython = Join-Path $repoRoot 'ai\.venv\Scripts\python.exe'
}
if (-not $OutputDir) {
    $tempRoot = [System.IO.Path]::GetTempPath()
    $runName = 'waterbridge-envelope-v1-qa-{0}-{1}' -f (
        Get-Date -Format 'yyyyMMdd-HHmmss'
    ), $PID
    $OutputDir = Join-Path $tempRoot $runName
}

$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$resultPath = Join-Path $OutputDir 'qa-result.json'
$script:StepResults = @()
$actualSha = $null

function Invoke-NativeStep {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    $index = $script:StepResults.Count + 1
    $safeName = $Name -replace '[^A-Za-z0-9_-]', '-'
    $logPath = Join-Path $OutputDir ('{0:D2}-{1}.log' -f $index, $safeName)
    $startedAt = Get-Date
    Write-Host ('[QA] {0}' -f $Name)
    Push-Location -LiteralPath $WorkingDirectory
    try {
        & $FilePath @Arguments *> $logPath
        $exitCode = $LASTEXITCODE
        Get-Content -LiteralPath $logPath | ForEach-Object {
            Write-Host $_
        }
    }
    finally {
        Pop-Location
    }
    if ($null -eq $exitCode) {
        $exitCode = 0
    }
    $script:StepResults += [ordered]@{
        name = $Name
        exit_code = $exitCode
        duration_seconds = [Math]::Round(((Get-Date) - $startedAt).TotalSeconds, 2)
        log = $logPath
    }
    if ($exitCode -ne 0) {
        throw ('QA step failed: {0} (exit {1})' -f $Name, $exitCode)
    }
}

function New-PytestTempPath {
    param([Parameter(Mandatory = $true)][string]$Name)
    return Join-Path $OutputDir ('pytest-{0}' -f $Name)
}

try {
    foreach ($pythonPath in @($BackendPython, $AiPython)) {
        if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
            throw ('Python executable not found: {0}' -f $pythonPath)
        }
    }

    $actualSha = (& git -C $repoRoot rev-parse HEAD).Trim().ToLowerInvariant()
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to resolve repository HEAD.'
    }
    if ($actualSha -ne $ExpectedSha.ToLowerInvariant()) {
        throw ('SHA mismatch: expected {0}, actual {1}' -f $ExpectedSha, $actualSha)
    }
    $dirty = @(& git -C $repoRoot status --porcelain=v1 --untracked-files=all)
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to inspect repository status.'
    }
    if ($dirty.Count -gt 0 -and -not $AllowDirty) {
        throw 'Worktree is not clean. QA must run against one immutable commit.'
    }

    Invoke-NativeStep 'backend-pip-check' $BackendPython @('-m', 'pip', 'check') $repoRoot
    Invoke-NativeStep 'ai-pip-check' $AiPython @('-m', 'pip', 'check') $repoRoot
    Invoke-NativeStep 'django-migration-drift' $BackendPython @(
        'manage.py', 'makemigrations', '--check', '--dry-run',
        '--settings=config.settings.test'
    ) (Join-Path $repoRoot 'backend')
    Invoke-NativeStep 'django-system-check' $BackendPython @(
        'manage.py', 'check', '--settings=config.settings.test'
    ) (Join-Path $repoRoot 'backend')
    Invoke-NativeStep 'git-diff-check' 'git' @('-C', $repoRoot, 'diff', '--check') $repoRoot

    $contractScripts = @(
        'scripts/contracts/validate_state_machine.py',
        'scripts/contracts/validate_codes.py',
        'scripts/contracts/validate_openapi.py',
        'scripts/contracts/validate_examples.py',
        'scripts/contracts/validate_contract_crosswalk.py'
    )
    foreach ($contractScript in $contractScripts) {
        $stepName = [System.IO.Path]::GetFileNameWithoutExtension($contractScript)
        Invoke-NativeStep $stepName $BackendPython @('-B', $contractScript) $repoRoot
    }
    Invoke-NativeStep 'state-machine-mermaid-drift' $BackendPython @(
        '-B', 'scripts/contracts/render_state_machine.py', '--check'
    ) $repoRoot
    Invoke-NativeStep 'root-contract-tests' $BackendPython @(
        '-B', '-m', 'pytest', 'tests/contract', '-q', '-p', 'no:cacheprovider',
        '--basetemp', (New-PytestTempPath 'root-contract')
    ) $repoRoot
    Invoke-NativeStep 'ai-envelope-contract-tests' $AiPython @(
        '-m', 'pytest', 'ai/tests/contract/test_analysis_consultation_envelope_v1.py',
        '-q', '-p', 'no:cacheprovider', '--basetemp',
        (New-PytestTempPath 'ai-envelope-contract')
    ) $repoRoot

    if ($Profile -eq 'Focused') {
        Invoke-NativeStep 'backend-envelope-focused' $BackendPython @(
            '-m', 'pytest',
            'tests/unit/ai_integration/test_ai_adapter.py',
            'tests/unit/ai_integration/test_inquiry_ai_service.py',
            'tests/unit/evidence/test_ai_chunk_crosswalk.py',
            'tests/api/test_human_review_runtime.py',
            '-q', '-p', 'no:cacheprovider', '--basetemp',
            (New-PytestTempPath 'backend-focused')
        ) (Join-Path $repoRoot 'backend')
    }
    else {
        $aiTestTempRoot = Join-Path $repoRoot 'ai\tests\.tmp'
        New-Item -ItemType Directory -Path $aiTestTempRoot -Force | Out-Null
        $mcpStepName = 'ai-mcp-stdio-unit'
        $mcpStepIndex = $script:StepResults.Count + 1
        $mcpLogPath = Join-Path $OutputDir (
            '{0:D2}-{1}.log' -f $mcpStepIndex, $mcpStepName
        )
        $mcpStartedAt = Get-Date
        Write-Host ('[QA] {0}' -f $mcpStepName)
        Push-Location -LiteralPath $repoRoot
        try {
            # This actual stdio subprocess test must stay in script scope.
            # A PowerShell function scope changes inherited stdin semantics.
            & $AiPython -m pytest `
                ai/tests/unit/harness/test_mcp_pipeline_stdio_integration.py `
                -q -p no:cacheprovider --basetemp `
                (Join-Path $aiTestTempRoot 'qa-envelope-v1-mcp-stdio')
            $mcpExitCode = $LASTEXITCODE
        }
        finally {
            Pop-Location
        }
        @(
            'Native output streamed directly for stdio compatibility.',
            ('exit_code={0}' -f $mcpExitCode)
        ) | Set-Content -LiteralPath $mcpLogPath -Encoding utf8
        $script:StepResults += [ordered]@{
            name = $mcpStepName
            exit_code = $mcpExitCode
            duration_seconds = [Math]::Round(
                ((Get-Date) - $mcpStartedAt).TotalSeconds,
                2
            )
            log = $mcpLogPath
        }
        if ($mcpExitCode -ne 0) {
            throw ('QA step failed: {0} (exit {1})' -f $mcpStepName, $mcpExitCode)
        }
        Invoke-NativeStep 'ai-unit-tests' $AiPython @(
            '-m', 'pytest', 'ai/tests/unit', '-q', '-p', 'no:cacheprovider',
            '--ignore=ai/tests/unit/harness/test_mcp_pipeline_stdio_integration.py',
            '--basetemp', (Join-Path $aiTestTempRoot 'qa-envelope-v1-unit')
        ) $repoRoot
        $backendGroups = [ordered]@{
            domain = @(
                'tests/unit/accounts', 'tests/unit/care', 'tests/unit/consultations',
                'tests/unit/inquiries', 'tests/unit/products',
                'tests/unit/questionnaires', 'tests/unit/reference_cases',
                'tests/unit/subscriptions', 'tests/unit/visits', 'tests/unit/workflow'
            )
            platform = @(
                'tests/unit/ai_integration', 'tests/unit/audit', 'tests/unit/common',
                'tests/unit/common_codes', 'tests/unit/database',
                'tests/unit/evidence', 'tests/unit/settings'
            )
            'api-integration' = @('tests/api', 'tests/integration')
        }
        foreach ($group in $backendGroups.GetEnumerator()) {
            $arguments = @('-m', 'pytest') + $group.Value + @(
                '-q', '-p', 'no:cacheprovider', '--durations=20', '--basetemp',
                (New-PytestTempPath ('backend-{0}' -f $group.Key))
            )
            Invoke-NativeStep ('backend-{0}' -f $group.Key) $BackendPython (
                [string[]]$arguments
            ) (Join-Path $repoRoot 'backend')
        }
    }

    $postRunDirty = @(& git -C $repoRoot status --porcelain=v1 --untracked-files=all)
    if ($postRunDirty.Count -gt 0 -and -not $AllowDirty) {
        throw 'QA execution changed the worktree.'
    }
    $result = [ordered]@{
        verdict = 'BACKEND_ENVELOPE_V1_QA_PASS'
        target_sha = $actualSha
        profile = $Profile
        completed_at = (Get-Date).ToString('o')
        steps = $script:StepResults
        safety_scope = [ordered]@{
            rds_write = $false
            public_runtime_change = $false
            provider_call = $false
            handoff_activation = $false
        }
    }
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resultPath -Encoding utf8
    Write-Host ('[QA] PASS: {0}' -f $resultPath)
}
catch {
    $failure = [ordered]@{
        verdict = 'BACKEND_ENVELOPE_V1_QA_FAILED'
        target_sha = $actualSha
        profile = $Profile
        completed_at = (Get-Date).ToString('o')
        error = $_.Exception.Message
        steps = $script:StepResults
    }
    $failure | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resultPath -Encoding utf8
    Write-Error ('[QA] FAILED: {0}; result={1}' -f $_.Exception.Message, $resultPath)
    exit 1
}
