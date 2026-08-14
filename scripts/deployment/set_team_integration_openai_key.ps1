param(
    [string]$RuntimeRoot,
    [SecureString]$OpenAIKey,
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
if (-not (Test-Path -LiteralPath $environmentRoot)) {
    throw 'The TEAM_INTEGRATION protected environment is not initialized.'
}
$keyPath = Join-Path $environmentRoot 'ai.env'
if ((Test-Path -LiteralPath $keyPath) -and -not $Rotate) {
    throw 'The protected OpenAI key already exists. Use -Rotate explicitly.'
}

$identity = "${env:USERDOMAIN}\${env:USERNAME}"
& icacls.exe $environmentRoot '/inheritance:r' '/grant:r' `
    "${identity}:(OI)(CI)F" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to restrict TEAM_INTEGRATION runtime file permissions.'
}

if (-not $OpenAIKey) {
    $OpenAIKey = Read-Host 'Enter the OpenAI API key' -AsSecureString
}
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($OpenAIKey)
$plainText = $null
$temporaryPath = "$keyPath.tmp"
try {
    $plainText = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if (
        [string]::IsNullOrWhiteSpace($plainText) -or
        $plainText.Contains("`r") -or
        $plainText.Contains("`n")
    ) {
        throw 'The OpenAI API key must be a non-empty single-line value.'
    }

    [System.IO.File]::WriteAllLines(
        $temporaryPath,
        @("OPENAI_API_KEY=$plainText"),
        [System.Text.UTF8Encoding]::new($false)
    )
    Move-Item -LiteralPath $temporaryPath -Destination $keyPath -Force
}
finally {
    $plainText = $null
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    if (Test-Path -LiteralPath $temporaryPath) {
        Remove-Item -LiteralPath $temporaryPath -Force
    }
}

[pscustomobject]@{
    status = if ($Rotate) { 'ROTATED' } else { 'CREATED' }
    secret_storage = 'ACL_RUNTIME_FILE'
    openai_key = 'YES'
    secret_values_printed = $false
}
