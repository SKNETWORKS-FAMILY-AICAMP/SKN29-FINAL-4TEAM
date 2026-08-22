#requires -Version 7.2

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$InputRoot,

    [Parameter(Mandatory)]
    [string]$OutputRoot,

    [Parameter(Mandatory)]
    [string]$ExpectedSourceRef,

    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:RepoRoot = $null
$script:EvidenceRoot = $null
$script:InputFullPath = $null
$script:OutputFullPath = $null
$script:OutputLeaf = $null
$script:StageRoot = $null
$script:StageNonce = $null
$script:StageCreated = $false
$script:Mutex = $null
$script:MutexAcquired = $false
$script:Utf8Strict = [System.Text.UTF8Encoding]::new($false, $true)
$script:Utf8NoBom = [System.Text.UTF8Encoding]::new($false)

$script:ArchiveName = 'web-g4-db-r3-r4-full-sanitized-20260821.zip'
$script:ArchiveHashName = "$($script:ArchiveName).sha256"
$script:SummaryName = 'package-summary.json'
$script:PackageManifestRelativePath = 'package/PACKAGE_SHA256SUMS.txt'
$script:MaxTextFileBytes = 10MB
$script:MaxArchiveUncompressedBytes = 100MB

$script:ExpectedR3Files = @(
    '00-db-evidence-context.json',
    '01-showmigrations-visits-before.txt',
    '02-migrate-plan-before.txt',
    '03-migration-gate-before.json',
    '04-r3-final-snapshot.json',
    '10-schema-fingerprint-before.sha256',
    '10a-schema-summary-before.json',
    '13-backend-db-redaction-scan.json'
)

$script:ExpectedR4Files = @(
    '00-db-evidence-context.json',
    '01-showmigrations-visits-after.txt',
    '01-showmigrations-visits-before.txt',
    '02-migrate-plan-after.txt',
    '02-migrate-plan-before.txt',
    '03-migration-gate-after.json',
    '03-migration-gate-before.json',
    '04-r4-before-first-write.json',
    '05-r4-after-first-write.json',
    '06-r4-after-replay.json',
    '07-r4-before-conflict.json',
    '08-r4-after-conflict.json',
    '09-r4-diff-and-duplicates.json',
    '10-schema-fingerprint-before.sha256',
    '10a-schema-summary-before.json',
    '11-schema-fingerprint-after.sha256',
    '11a-schema-summary-after.json',
    '12-schema-diff.txt',
    '13-backend-db-redaction-scan.json',
    '14-http-replay-conflict-evidence.json'
)

$script:SafeFalseFields = @(
    'access_token_included',
    'db_accessed',
    'local_environment_metadata_included',
    'original_files_modified',
    'raw_business_text_included',
    'raw_idempotency_key_included',
    'secret_values_included',
    'secret_values_printed',
    'token_printed'
)

$script:RawBusinessFields = @(
    'additional_check',
    'ai_draft_summary',
    'answer',
    'confirmed_summary',
    'consultation_note',
    'customer_guidance',
    'raw_text',
    'summary'
)

function Stop-Package {
    param(
        [Parameter(Mandatory)]
        [string]$Code,

        [string]$RelativeFile = ''
    )

    $exception = [System.InvalidOperationException]::new('PACKAGE_OPERATION_FAILED')
    $exception.Data['PackageCode'] = $Code
    if ($RelativeFile) {
        $exception.Data['RelativeFile'] = $RelativeFile
    }
    throw $exception
}

function Get-SafePackageCode {
    param([System.Management.Automation.ErrorRecord]$ErrorRecord)

    if (
        $null -ne $ErrorRecord.Exception -and
        $ErrorRecord.Exception.Data.Contains('PackageCode')
    ) {
        $value = [string]$ErrorRecord.Exception.Data['PackageCode']
        if ($value -match '^E_[A-Z0-9_]+$') {
            return $value
        }
    }
    return 'E_UNEXPECTED'
}

function Get-SafeRelativeFile {
    param([System.Management.Automation.ErrorRecord]$ErrorRecord)

    if (
        $null -ne $ErrorRecord.Exception -and
        $ErrorRecord.Exception.Data.Contains('RelativeFile')
    ) {
        $value = [string]$ErrorRecord.Exception.Data['RelativeFile']
        if ($value -match '^(?:r3|r4|package)/[A-Za-z0-9._/-]+$') {
            return $value
        }
    }
    return ''
}

function Test-StringSetEqual {
    param(
        [Parameter(Mandatory)]
        [string[]]$Actual,

        [Parameter(Mandatory)]
        [string[]]$Expected
    )

    if ($Actual.Count -ne $Expected.Count) {
        return $false
    }
    $actualSet = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::Ordinal
    )
    $expectedSet = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::Ordinal
    )
    foreach ($value in $Actual) {
        if (-not $actualSet.Add($value)) {
            return $false
        }
    }
    foreach ($value in $Expected) {
        if (-not $expectedSet.Add($value)) {
            return $false
        }
    }
    return $actualSet.SetEquals($expectedSet)
}

function Assert-CaseInsensitiveUnique {
    param(
        [Parameter(Mandatory)]
        [string[]]$Values,

        [Parameter(Mandatory)]
        [string]$Code
    )

    $set = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::OrdinalIgnoreCase
    )
    foreach ($value in $Values) {
        if (-not $set.Add($value)) {
            Stop-Package -Code $Code
        }
    }
}

function Get-Sha256FromBytes {
    param([Parameter(Mandatory)][byte[]]$Bytes)

    return [System.Convert]::ToHexString(
        [System.Security.Cryptography.SHA256]::HashData($Bytes)
    ).ToLowerInvariant()
}

function Get-FileSha256 {
    param([Parameter(Mandatory)][string]$LiteralPath)

    $stream = [System.IO.File]::Open(
        $LiteralPath,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read
    )
    try {
        return [System.Convert]::ToHexString(
            [System.Security.Cryptography.SHA256]::HashData($stream)
        ).ToLowerInvariant()
    }
    finally {
        $stream.Dispose()
    }
}

function Read-StrictUtf8Text {
    param(
        [Parameter(Mandatory)][string]$LiteralPath,
        [Parameter(Mandatory)][string]$RelativeFile
    )

    $file = Get-Item -LiteralPath $LiteralPath -Force
    if ($file.Length -gt $script:MaxTextFileBytes) {
        Stop-Package -Code 'E_FILE_SIZE' -RelativeFile $RelativeFile
    }
    $bytes = [System.IO.File]::ReadAllBytes($LiteralPath)
    if (
        $bytes.Length -ge 3 -and
        $bytes[0] -eq 0xEF -and
        $bytes[1] -eq 0xBB -and
        $bytes[2] -eq 0xBF
    ) {
        Stop-Package -Code 'E_UTF8_BOM' -RelativeFile $RelativeFile
    }
    try {
        return $script:Utf8Strict.GetString($bytes)
    }
    catch {
        Stop-Package -Code 'E_UTF8_INVALID' -RelativeFile $RelativeFile
    }
}

function Write-Utf8NoBomText {
    param(
        [Parameter(Mandatory)][string]$LiteralPath,
        [Parameter(Mandatory)][string]$Text
    )

    if (Test-Path -LiteralPath $LiteralPath) {
        Stop-Package -Code 'E_OUTPUT_EXISTS'
    }
    [System.IO.File]::WriteAllText($LiteralPath, $Text, $script:Utf8NoBom)
}

function ConvertTo-SafeJsonText {
    param([Parameter(Mandatory)]$Value)

    $text = $Value | ConvertTo-Json -Depth 30
    $text = $text.Replace("`r`n", "`n").Replace("`r", "`n")
    return "$text`n"
}

function Assert-NoReparsePoint {
    param(
        [Parameter(Mandatory)][string]$LiteralPath,
        [string]$RelativeFile = ''
    )

    $item = Get-Item -LiteralPath $LiteralPath -Force
    if (
        ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
    ) {
        Stop-Package -Code 'E_REPARSE' -RelativeFile $RelativeFile
    }
}

function Assert-PathHasNoAlternateStreams {
    param(
        [Parameter(Mandatory)][string]$LiteralPath,
        [Parameter(Mandatory)][string]$RelativeFile
    )

    if ($IsWindows) {
        $streams = @(Get-Item -LiteralPath $LiteralPath -Stream * -ErrorAction Stop)
        foreach ($stream in $streams) {
            if ($stream.Stream -ne ':$DATA') {
                Stop-Package -Code 'E_ADS' -RelativeFile $RelativeFile
            }
        }
    }
}

function Resolve-RepositoryRelativeRoot {
    param(
        [Parameter(Mandatory)][string]$Value,
        [Parameter(Mandatory)][string]$Kind
    )

    if (
        [string]::IsNullOrWhiteSpace($Value) -or
        [System.IO.Path]::IsPathRooted($Value) -or
        $Value.Contains([char]0) -or
        $Value.Contains(':')
    ) {
        Stop-Package -Code 'E_PATH_BOUNDARY'
    }
    $segments = $Value.Replace('\', '/').Split(
        '/',
        [System.StringSplitOptions]::RemoveEmptyEntries
    )
    if ($segments.Count -eq 0 -or $segments -contains '..') {
        Stop-Package -Code 'E_PATH_BOUNDARY'
    }
    $full = [System.IO.Path]::GetFullPath(
        [System.IO.Path]::Combine($script:RepoRoot, $Value)
    )
    $parent = [System.IO.Path]::GetDirectoryName($full)
    if (
        -not [string]::Equals(
            $parent,
            $script:EvidenceRoot,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    ) {
        Stop-Package -Code 'E_PATH_BOUNDARY'
    }
    $leaf = [System.IO.Path]::GetFileName($full)
    if ($leaf -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,126}$') {
        Stop-Package -Code 'E_PATH_BOUNDARY'
    }
    if ($leaf.EndsWith('.') -or $leaf.EndsWith(' ')) {
        Stop-Package -Code 'E_PATH_BOUNDARY'
    }
    if ($Kind -eq 'Input') {
        if (-not (Test-Path -LiteralPath $full -PathType Container)) {
            Stop-Package -Code 'E_INPUT_MISSING'
        }
    }
    elseif ($Kind -eq 'Output') {
        if (Test-Path -LiteralPath $full) {
            Stop-Package -Code 'E_OUTPUT_EXISTS'
        }
    }
    else {
        Stop-Package -Code 'E_PATH_BOUNDARY'
    }
    return $full
}

function ConvertTo-RepoRelativePath {
    param([Parameter(Mandatory)][string]$FullPath)

    $relative = [System.IO.Path]::GetRelativePath(
        $script:RepoRoot,
        $FullPath
    ).Replace('\', '/')
    if (
        [System.IO.Path]::IsPathRooted($relative) -or
        $relative -eq '.' -or
        $relative.StartsWith('../', [System.StringComparison]::Ordinal) -or
        $relative.Contains(':')
    ) {
        Stop-Package -Code 'E_PATH_BOUNDARY'
    }
    return $relative
}

function Read-JsonHashtable {
    param(
        [Parameter(Mandatory)][string]$LiteralPath,
        [Parameter(Mandatory)][string]$RelativeFile
    )

    $text = Read-StrictUtf8Text -LiteralPath $LiteralPath -RelativeFile $RelativeFile
    try {
        $value = $text | ConvertFrom-Json -AsHashtable -Depth 100
    }
    catch {
        Stop-Package -Code 'E_JSON_INVALID' -RelativeFile $RelativeFile
    }
    if ($value -isnot [System.Collections.IDictionary]) {
        Stop-Package -Code 'E_JSON_INVALID' -RelativeFile $RelativeFile
    }
    return $value
}

function Get-RequiredMapValue {
    param(
        [Parameter(Mandatory)][System.Collections.IDictionary]$Map,
        [Parameter(Mandatory)][string]$Key,
        [Parameter(Mandatory)][string]$RelativeFile
    )

    if (-not $Map.Contains($Key)) {
        Stop-Package -Code 'E_EVIDENCE_CONTRACT' -RelativeFile $RelativeFile
    }
    return ,$Map[$Key]
}

function Assert-MapValueEquals {
    param(
        [Parameter(Mandatory)][System.Collections.IDictionary]$Map,
        [Parameter(Mandatory)][string]$Key,
        [Parameter(Mandatory)]$Expected,
        [Parameter(Mandatory)][string]$RelativeFile
    )

    $actual = Get-RequiredMapValue -Map $Map -Key $Key -RelativeFile $RelativeFile
    if ($actual -ne $Expected) {
        Stop-Package -Code 'E_EVIDENCE_CONTRACT' -RelativeFile $RelativeFile
    }
}

function Assert-EmptyCollection {
    param(
        [Parameter(Mandatory)][System.Collections.IDictionary]$Map,
        [Parameter(Mandatory)][string]$Key,
        [Parameter(Mandatory)][string]$RelativeFile
    )

    if (-not $Map.Contains($Key)) {
        Stop-Package -Code 'E_EVIDENCE_CONTRACT' -RelativeFile $RelativeFile
    }
    $value = $Map[$Key]
    if (
        $null -eq $value -or
        $value -isnot [System.Array] -or
        $value.Count -ne 0
    ) {
        Stop-Package -Code 'E_EVIDENCE_CONTRACT' -RelativeFile $RelativeFile
    }
}

function Get-SensitiveFindingCodes {
    param(
        [Parameter(Mandatory)]
        [AllowEmptyString()]
        [AllowEmptyCollection()]
        [string]$Text,
        [Parameter(Mandatory)][string]$RelativeFile
    )

    $codes = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::Ordinal
    )

    $patterns = [ordered]@{
        AUTH_BEARER = '(?i)\bBearer\s+(?!\[REDACTED\])[^\s"'']{8,}'
        JWT = '\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b'
        PRIVATE_KEY = '-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'
        DATABASE_DSN = '(?i)\b(?:postgres(?:ql)?|mysql|mariadb)://[^\s"''<>]+'
        EMAIL = '(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b'
        MOBILE_PHONE = '(?<![A-Fa-f0-9])(?:\+?82[ -]?)?01[016789][ -]?\d{3,4}[ -]?\d{4}(?![A-Fa-f0-9])'
        LANDLINE_PHONE = '(?<![A-Fa-f0-9])0\d{1,2}[ -]?\d{3,4}[ -]?\d{4}(?![A-Fa-f0-9])'
        KOREAN_RRN = '(?<![A-Fa-f0-9])\d{6}-?[1-4]\d{6}(?![A-Fa-f0-9])'
        AWS_ACCESS_KEY = '\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'
        GITHUB_TOKEN = '\bgh[pousr]_[A-Za-z0-9]{20,}\b'
        OPENAI_KEY = '\bsk-[A-Za-z0-9_-]{20,}\b'
        IPV4 = '(?<![0-9A-Fa-f])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![0-9A-Fa-f])'
        IPV6 = '(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{1,4}:){4,7}[0-9A-Fa-f]{0,4}(?![0-9A-Fa-f])|(?<![0-9A-Fa-f])::1(?![0-9A-Fa-f])'
        WINDOWS_PATH = '(?i)(?<![A-Za-z0-9])[A-Z]:[\\/][^\r\n"'']+'
        UNC_PATH = '(?<![\\])\\\\[^\\\s"'']+\\[^\r\n"'']+'
        UNIX_LOCAL_PATH = '(?<![A-Za-z0-9])/(?:Users|home|tmp|var|etc|opt|root|mnt|Volumes)/[^\r\n"'']*'
    }

    foreach ($entry in $patterns.GetEnumerator()) {
        if ([System.Text.RegularExpressions.Regex]::IsMatch($Text, $entry.Value)) {
            $null = $codes.Add($entry.Key)
        }
    }

    $currentUser = [System.Environment]::UserName
    if (
        -not [string]::IsNullOrWhiteSpace($currentUser) -and
        $currentUser.Length -ge 4 -and
        $Text.IndexOf($currentUser, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    ) {
        $null = $codes.Add('LOCAL_USERNAME')
    }

    if ($RelativeFile.EndsWith('.json', [System.StringComparison]::OrdinalIgnoreCase)) {
        try {
            $json = $Text | ConvertFrom-Json -AsHashtable -Depth 100
        }
        catch {
            $null = $codes.Add('JSON_INVALID')
            return @($codes | Sort-Object)
        }
        Test-JsonValueForSensitiveData -Value $json -Codes $codes
    }

    return @($codes | Sort-Object)
}

function Test-JsonValueForSensitiveData {
    param(
        $Value,
        [Parameter(Mandatory)]
        [AllowEmptyCollection()]
        [System.Collections.Generic.HashSet[string]]$Codes
    )

    if ($Value -is [System.Collections.IDictionary]) {
        foreach ($keyObject in $Value.Keys) {
            $key = [string]$keyObject
            $child = $Value[$keyObject]
            $lowerKey = $key.ToLowerInvariant()

            if ($script:SafeFalseFields -contains $lowerKey) {
                if ($child -isnot [bool] -or $child -ne $false) {
                    $null = $Codes.Add('SAFE_FLAG_NOT_FALSE')
                }
            }
            elseif ($lowerKey -eq 'idempotency_key_sha256') {
                if ($child -isnot [string] -or $child -notmatch '^[0-9a-f]{64}$') {
                    $null = $Codes.Add('IDEMPOTENCY_HASH_INVALID')
                }
            }
            elseif ($lowerKey -eq 'idempotency_key') {
                $null = $Codes.Add('RAW_IDEMPOTENCY_KEY')
            }
            elseif (
                $lowerKey -match '(?:password|secret|token|api[_-]?key|dsn|authorization|cookie)'
            ) {
                if ($child -ne '[REDACTED]' -and $child -ne $null) {
                    $null = $Codes.Add('SENSITIVE_JSON_FIELD')
                }
            }

            if (
                $lowerKey -match '^(?:display_name|customer_name|customer_display_name_masked|phone|email|address|birth_date|username|resident_registration_number)$'
            ) {
                $null = $Codes.Add('PII_JSON_FIELD')
            }

            if ($script:RawBusinessFields -contains $lowerKey) {
                if ($child -isnot [bool] -and $child -ne $null) {
                    $null = $Codes.Add('RAW_BUSINESS_TEXT')
                }
            }

            Test-JsonValueForSensitiveData -Value $child -Codes $Codes
        }
        return
    }

    if (
        $Value -is [System.Collections.IEnumerable] -and
        $Value -isnot [string]
    ) {
        foreach ($item in $Value) {
            Test-JsonValueForSensitiveData -Value $item -Codes $Codes
        }
    }
}

function Assert-TextIsSanitized {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$RelativeFile
    )

    $codes = @(Get-SensitiveFindingCodes -Text $Text -RelativeFile $RelativeFile)
    if ($codes.Count -gt 0) {
        Stop-Package -Code 'E_SENSITIVE' -RelativeFile $RelativeFile
    }
}

function Assert-FileIsSanitized {
    param(
        [Parameter(Mandatory)][string]$LiteralPath,
        [Parameter(Mandatory)][string]$RelativeFile
    )

    $text = Read-StrictUtf8Text -LiteralPath $LiteralPath -RelativeFile $RelativeFile
    Assert-TextIsSanitized -Text $text -RelativeFile $RelativeFile
}

function Read-InnerManifest {
    param(
        [Parameter(Mandatory)][string]$Scope,
        [Parameter(Mandatory)][string]$Directory,
        [Parameter(Mandatory)][string[]]$ExpectedFiles
    )

    Assert-NoReparsePoint -LiteralPath $Directory
    $subdirectories = @(Get-ChildItem -LiteralPath $Directory -Directory -Force)
    if ($subdirectories.Count -ne 0) {
        Stop-Package -Code 'E_SET_MISMATCH'
    }

    $manifestPath = Join-Path $Directory 'SHA256SUMS.txt'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        Stop-Package -Code 'E_MANIFEST_MISSING' -RelativeFile "$Scope/SHA256SUMS.txt"
    }
    Assert-NoReparsePoint -LiteralPath $manifestPath -RelativeFile "$Scope/SHA256SUMS.txt"
    Assert-PathHasNoAlternateStreams -LiteralPath $manifestPath -RelativeFile "$Scope/SHA256SUMS.txt"
    $text = Read-StrictUtf8Text -LiteralPath $manifestPath -RelativeFile "$Scope/SHA256SUMS.txt"
    if (-not $text.EndsWith("`n", [System.StringComparison]::Ordinal)) {
        Stop-Package -Code 'E_MANIFEST_FORMAT' -RelativeFile "$Scope/SHA256SUMS.txt"
    }
    $normalized = $text.Replace("`r`n", "`n")
    if ($normalized.Contains("`r")) {
        Stop-Package -Code 'E_MANIFEST_FORMAT' -RelativeFile "$Scope/SHA256SUMS.txt"
    }
    $parts = $normalized.Split("`n")
    if ($parts[-1] -ne '') {
        Stop-Package -Code 'E_MANIFEST_FORMAT' -RelativeFile "$Scope/SHA256SUMS.txt"
    }
    $lines = @($parts[0..($parts.Count - 2)])
    if ($lines.Count -ne $ExpectedFiles.Count) {
        Stop-Package -Code 'E_MANIFEST_COUNT' -RelativeFile "$Scope/SHA256SUMS.txt"
    }

    $entries = @()
    $names = @()
    foreach ($line in $lines) {
        if ($line -notmatch '^(?<hash>[0-9a-f]{64})  (?<name>[A-Za-z0-9][A-Za-z0-9._-]*)$') {
            Stop-Package -Code 'E_MANIFEST_FORMAT' -RelativeFile "$Scope/SHA256SUMS.txt"
        }
        $name = $Matches['name']
        if (
            $name -eq '.' -or
            $name -eq '..' -or
            $name.EndsWith('.') -or
            $name.EndsWith(' ')
        ) {
            Stop-Package -Code 'E_MANIFEST_FORMAT' -RelativeFile "$Scope/SHA256SUMS.txt"
        }
        $names += $name
        $entries += [pscustomobject]@{
            Name = $name
            ExpectedHash = $Matches['hash']
            RelativePath = "$Scope/$name"
            SourcePath = Join-Path $Directory $name
        }
    }

    Assert-CaseInsensitiveUnique -Values $names -Code 'E_MANIFEST_DUPLICATE'
    if (-not (Test-StringSetEqual -Actual $names -Expected $ExpectedFiles)) {
        Stop-Package -Code 'E_SET_MISMATCH' -RelativeFile "$Scope/SHA256SUMS.txt"
    }

    $actualFiles = @(
        Get-ChildItem -LiteralPath $Directory -File -Force |
            ForEach-Object { $_.Name }
    )
    $expectedDirectoryFiles = @($ExpectedFiles + 'SHA256SUMS.txt')
    Assert-CaseInsensitiveUnique -Values $actualFiles -Code 'E_SET_MISMATCH'
    if (-not (Test-StringSetEqual -Actual $actualFiles -Expected $expectedDirectoryFiles)) {
        Stop-Package -Code 'E_SET_MISMATCH'
    }

    foreach ($entry in $entries) {
        if (-not (Test-Path -LiteralPath $entry.SourcePath -PathType Leaf)) {
            Stop-Package -Code 'E_FILE_MISSING' -RelativeFile $entry.RelativePath
        }
        Assert-NoReparsePoint -LiteralPath $entry.SourcePath -RelativeFile $entry.RelativePath
        Assert-PathHasNoAlternateStreams -LiteralPath $entry.SourcePath -RelativeFile $entry.RelativePath
        $actualHash = Get-FileSha256 -LiteralPath $entry.SourcePath
        if ($actualHash -ne $entry.ExpectedHash) {
            Stop-Package -Code 'E_HASH_MISMATCH' -RelativeFile $entry.RelativePath
        }
    }

    return [pscustomobject]@{
        Scope = $Scope
        Directory = $Directory
        ManifestPath = $manifestPath
        Entries = $entries
        ExpectedCount = $ExpectedFiles.Count
    }
}

function Get-SourceFileRecords {
    param(
        [Parameter(Mandatory)]$R3Manifest,
        [Parameter(Mandatory)]$R4Manifest
    )

    $records = @()
    foreach ($manifest in @($R3Manifest, $R4Manifest)) {
        foreach ($entry in $manifest.Entries) {
            $records += [pscustomobject]@{
                RelativePath = $entry.RelativePath
                SourcePath = $entry.SourcePath
            }
        }
        $records += [pscustomobject]@{
            RelativePath = "$($manifest.Scope)/SHA256SUMS.txt"
            SourcePath = $manifest.ManifestPath
        }
    }
    return $records
}

function Get-HashMap {
    param([Parameter(Mandatory)][object[]]$Records)

    $map = [ordered]@{}
    foreach ($record in $Records) {
        $map[$record.RelativePath] = Get-FileSha256 -LiteralPath $record.SourcePath
    }
    return $map
}

function Assert-HashMapsEqual {
    param(
        [Parameter(Mandatory)][System.Collections.IDictionary]$Expected,
        [Parameter(Mandatory)][System.Collections.IDictionary]$Actual,
        [Parameter(Mandatory)][string]$Code
    )

    if ($Expected.Count -ne $Actual.Count) {
        Stop-Package -Code $Code
    }
    foreach ($key in $Expected.Keys) {
        if (-not $Actual.Contains($key) -or $Actual[$key] -ne $Expected[$key]) {
            Stop-Package -Code $Code -RelativeFile $key
        }
    }
}

function Assert-MigrationGate {
    param(
        [Parameter(Mandatory)][System.Collections.IDictionary]$Gate,
        [Parameter(Mandatory)][string]$RelativeFile
    )

    Assert-MapValueEquals -Map $Gate -Key 'status' -Expected 'READY' -RelativeFile $RelativeFile
    Assert-MapValueEquals -Map $Gate -Key 'visits_0005' -Expected 'NOT_APPLIED_P1_HOLD' -RelativeFile $RelativeFile
    Assert-EmptyCollection -Map $Gate -Key 'unexpected_pending_migrations' -RelativeFile $RelativeFile
    Assert-EmptyCollection -Map $Gate -Key 'unknown_applied_migrations' -RelativeFile $RelativeFile
    Assert-EmptyCollection -Map $Gate -Key 'blockers' -RelativeFile $RelativeFile
}

function Assert-RedactionReport {
    param(
        [Parameter(Mandatory)][System.Collections.IDictionary]$Report,
        [Parameter(Mandatory)][int]$ExpectedScannedCount,
        [Parameter(Mandatory)][string]$RelativeFile
    )

    Assert-MapValueEquals -Map $Report -Key 'status' -Expected 'PASS' -RelativeFile $RelativeFile
    Assert-MapValueEquals -Map $Report -Key 'finding_count' -Expected 0 -RelativeFile $RelativeFile
    Assert-MapValueEquals -Map $Report -Key 'scanned_file_count' -Expected $ExpectedScannedCount -RelativeFile $RelativeFile
    Assert-EmptyCollection -Map $Report -Key 'findings' -RelativeFile $RelativeFile
}

function Assert-ZeroDelta {
    param(
        [Parameter(Mandatory)][System.Collections.IDictionary]$Delta,
        [Parameter(Mandatory)][string]$RelativeFile
    )

    foreach ($key in @('consultation', 'history', 'idempotency', 'state_version')) {
        Assert-MapValueEquals -Map $Delta -Key $key -Expected 0 -RelativeFile $RelativeFile
    }
}

function Assert-EvidenceContract {
    param([Parameter(Mandatory)][string]$InputRootPath)

    $r3ContextPath = Join-Path $InputRootPath 'r3/00-db-evidence-context.json'
    $r3Context = Read-JsonHashtable -LiteralPath $r3ContextPath -RelativeFile 'r3/00-db-evidence-context.json'
    Assert-MapValueEquals -Map $r3Context -Key 'source_ref' -Expected $ExpectedSourceRef -RelativeFile 'r3/00-db-evidence-context.json'
    Assert-MapValueEquals -Map $r3Context -Key 'evidence_mode' -Expected 'R3_FINAL_ONLY' -RelativeFile 'r3/00-db-evidence-context.json'
    Assert-MapValueEquals -Map $r3Context -Key 'historical_replay_evidence' -Expected 'NOT_CAPTURED' -RelativeFile 'r3/00-db-evidence-context.json'
    Assert-MapValueEquals -Map $r3Context -Key 'historical_schema_delta' -Expected 'NOT_CAPTURED' -RelativeFile 'r3/00-db-evidence-context.json'

    $r3RunId = [string](Get-RequiredMapValue -Map $r3Context -Key 'run_id' -RelativeFile 'r3/00-db-evidence-context.json')
    $r3InquiryId = [string](Get-RequiredMapValue -Map $r3Context -Key 'inquiry_id' -RelativeFile 'r3/00-db-evidence-context.json')
    $r3Snapshot = Read-JsonHashtable -LiteralPath (Join-Path $InputRootPath 'r3/04-r3-final-snapshot.json') -RelativeFile 'r3/04-r3-final-snapshot.json'
    Assert-MapValueEquals -Map $r3Snapshot -Key 'source_ref' -Expected $ExpectedSourceRef -RelativeFile 'r3/04-r3-final-snapshot.json'
    Assert-MapValueEquals -Map $r3Snapshot -Key 'run_id' -Expected $r3RunId -RelativeFile 'r3/04-r3-final-snapshot.json'
    $r3Inquiry = Get-RequiredMapValue -Map $r3Snapshot -Key 'inquiry' -RelativeFile 'r3/04-r3-final-snapshot.json'
    if ($r3Inquiry -isnot [System.Collections.IDictionary]) {
        Stop-Package -Code 'E_EVIDENCE_CONTRACT' -RelativeFile 'r3/04-r3-final-snapshot.json'
    }
    Assert-MapValueEquals -Map $r3Inquiry -Key 'inquiry_id' -Expected $r3InquiryId -RelativeFile 'r3/04-r3-final-snapshot.json'

    $r4Context = Read-JsonHashtable -LiteralPath (Join-Path $InputRootPath 'r4/00-db-evidence-context.json') -RelativeFile 'r4/00-db-evidence-context.json'
    Assert-MapValueEquals -Map $r4Context -Key 'source_ref' -Expected $ExpectedSourceRef -RelativeFile 'r4/00-db-evidence-context.json'
    Assert-MapValueEquals -Map $r4Context -Key 'evidence_mode' -Expected 'R4' -RelativeFile 'r4/00-db-evidence-context.json'
    $r4RunId = [string](Get-RequiredMapValue -Map $r4Context -Key 'run_id' -RelativeFile 'r4/00-db-evidence-context.json')
    $r4InquiryId = [string](Get-RequiredMapValue -Map $r4Context -Key 'inquiry_id' -RelativeFile 'r4/00-db-evidence-context.json')

    $phaseFiles = [ordered]@{
        '04-r4-before-first-write.json' = 'r4-before-first-write'
        '05-r4-after-first-write.json' = 'r4-after-first-write'
        '06-r4-after-replay.json' = 'r4-after-replay'
        '07-r4-before-conflict.json' = 'r4-before-conflict'
        '08-r4-after-conflict.json' = 'r4-after-conflict'
    }
    foreach ($phaseEntry in $phaseFiles.GetEnumerator()) {
        $relative = "r4/$($phaseEntry.Key)"
        $snapshot = Read-JsonHashtable -LiteralPath (Join-Path $InputRootPath $relative) -RelativeFile $relative
        Assert-MapValueEquals -Map $snapshot -Key 'phase' -Expected $phaseEntry.Value -RelativeFile $relative
        Assert-MapValueEquals -Map $snapshot -Key 'source_ref' -Expected $ExpectedSourceRef -RelativeFile $relative
        Assert-MapValueEquals -Map $snapshot -Key 'run_id' -Expected $r4RunId -RelativeFile $relative
        $inquiry = Get-RequiredMapValue -Map $snapshot -Key 'inquiry' -RelativeFile $relative
        if ($inquiry -isnot [System.Collections.IDictionary]) {
            Stop-Package -Code 'E_EVIDENCE_CONTRACT' -RelativeFile $relative
        }
        Assert-MapValueEquals -Map $inquiry -Key 'inquiry_id' -Expected $r4InquiryId -RelativeFile $relative
    }

    $compareRelative = 'r4/09-r4-diff-and-duplicates.json'
    $compare = Read-JsonHashtable -LiteralPath (Join-Path $InputRootPath $compareRelative) -RelativeFile $compareRelative
    Assert-MapValueEquals -Map $compare -Key 'status' -Expected 'PASS' -RelativeFile $compareRelative
    Assert-MapValueEquals -Map $compare -Key 'source_ref' -Expected $ExpectedSourceRef -RelativeFile $compareRelative
    Assert-MapValueEquals -Map $compare -Key 'run_id' -Expected $r4RunId -RelativeFile $compareRelative
    Assert-MapValueEquals -Map $compare -Key 'inquiry_id' -Expected $r4InquiryId -RelativeFile $compareRelative
    Assert-MapValueEquals -Map $compare -Key 'duplicate_idempotency_scope_count' -Expected 0 -RelativeFile $compareRelative
    Assert-MapValueEquals -Map $compare -Key 'duplicate_consultation_count' -Expected 0 -RelativeFile $compareRelative
    Assert-MapValueEquals -Map $compare -Key 'schema_unchanged' -Expected $true -RelativeFile $compareRelative
    Assert-MapValueEquals -Map $compare -Key 'migration_state_unchanged' -Expected $true -RelativeFile $compareRelative
    Assert-EmptyCollection -Map $compare -Key 'blockers' -RelativeFile $compareRelative
    $replayDelta = Get-RequiredMapValue -Map $compare -Key 'replay_additional_rows' -RelativeFile $compareRelative
    $conflictDelta = Get-RequiredMapValue -Map $compare -Key 'stale_state_409_additional_rows' -RelativeFile $compareRelative
    if (
        $replayDelta -isnot [System.Collections.IDictionary] -or
        $conflictDelta -isnot [System.Collections.IDictionary]
    ) {
        Stop-Package -Code 'E_EVIDENCE_CONTRACT' -RelativeFile $compareRelative
    }
    Assert-ZeroDelta -Delta $replayDelta -RelativeFile $compareRelative
    Assert-ZeroDelta -Delta $conflictDelta -RelativeFile $compareRelative

    $httpRelative = 'r4/14-http-replay-conflict-evidence.json'
    $httpEvidence = Read-JsonHashtable -LiteralPath (Join-Path $InputRootPath $httpRelative) -RelativeFile $httpRelative
    Assert-MapValueEquals -Map $httpEvidence -Key 'source_ref' -Expected $ExpectedSourceRef -RelativeFile $httpRelative
    Assert-MapValueEquals -Map $httpEvidence -Key 'run_id' -Expected $r4RunId -RelativeFile $httpRelative
    Assert-MapValueEquals -Map $httpEvidence -Key 'inquiry_id' -Expected $r4InquiryId -RelativeFile $httpRelative
    $firstSave = Get-RequiredMapValue -Map $httpEvidence -Key 'first_save' -RelativeFile $httpRelative
    $replay = Get-RequiredMapValue -Map $httpEvidence -Key 'same_request_replay' -RelativeFile $httpRelative
    $stale = Get-RequiredMapValue -Map $httpEvidence -Key 'stale_state_version' -RelativeFile $httpRelative
    if (
        $firstSave -isnot [System.Collections.IDictionary] -or
        $replay -isnot [System.Collections.IDictionary] -or
        $stale -isnot [System.Collections.IDictionary]
    ) {
        Stop-Package -Code 'E_EVIDENCE_CONTRACT' -RelativeFile $httpRelative
    }
    Assert-MapValueEquals -Map $firstSave -Key 'http_status' -Expected 200 -RelativeFile $httpRelative
    Assert-MapValueEquals -Map $replay -Key 'http_status' -Expected 200 -RelativeFile $httpRelative
    Assert-MapValueEquals -Map $replay -Key 'same_key_and_payload_as_first_save' -Expected $true -RelativeFile $httpRelative
    Assert-MapValueEquals -Map $stale -Key 'http_status' -Expected 409 -RelativeFile $httpRelative
    Assert-MapValueEquals -Map $stale -Key 'error_code' -Expected 'STATE-CONFLICT-01' -RelativeFile $httpRelative
    if ($firstSave['idempotency_key_sha256'] -ne $replay['idempotency_key_sha256']) {
        Stop-Package -Code 'E_EVIDENCE_CONTRACT' -RelativeFile $httpRelative
    }

    $migrationFiles = @(
        'r3/03-migration-gate-before.json',
        'r4/03-migration-gate-before.json',
        'r4/03-migration-gate-after.json'
    )
    foreach ($relative in $migrationFiles) {
        $gate = Read-JsonHashtable -LiteralPath (Join-Path $InputRootPath $relative) -RelativeFile $relative
        Assert-MigrationGate -Gate $gate -RelativeFile $relative
    }

    $r3Redaction = Read-JsonHashtable -LiteralPath (Join-Path $InputRootPath 'r3/13-backend-db-redaction-scan.json') -RelativeFile 'r3/13-backend-db-redaction-scan.json'
    Assert-RedactionReport -Report $r3Redaction -ExpectedScannedCount 7 -RelativeFile 'r3/13-backend-db-redaction-scan.json'
    $r4Redaction = Read-JsonHashtable -LiteralPath (Join-Path $InputRootPath 'r4/13-backend-db-redaction-scan.json') -RelativeFile 'r4/13-backend-db-redaction-scan.json'
    Assert-RedactionReport -Report $r4Redaction -ExpectedScannedCount 19 -RelativeFile 'r4/13-backend-db-redaction-scan.json'

    $schemaBeforeText = Read-StrictUtf8Text -LiteralPath (Join-Path $InputRootPath 'r4/10-schema-fingerprint-before.sha256') -RelativeFile 'r4/10-schema-fingerprint-before.sha256'
    $schemaAfterText = Read-StrictUtf8Text -LiteralPath (Join-Path $InputRootPath 'r4/11-schema-fingerprint-after.sha256') -RelativeFile 'r4/11-schema-fingerprint-after.sha256'
    if (
        $schemaBeforeText -notmatch '^([0-9a-f]{64})  schema\r?\n$' -or
        $schemaAfterText -notmatch '^([0-9a-f]{64})  schema\r?\n$'
    ) {
        Stop-Package -Code 'E_EVIDENCE_CONTRACT' -RelativeFile 'r4/12-schema-diff.txt'
    }
    $beforeHash = ([regex]::Match($schemaBeforeText, '^([0-9a-f]{64})')).Groups[1].Value
    $afterHash = ([regex]::Match($schemaAfterText, '^([0-9a-f]{64})')).Groups[1].Value
    if ($beforeHash -ne $afterHash) {
        Stop-Package -Code 'E_EVIDENCE_CONTRACT' -RelativeFile 'r4/12-schema-diff.txt'
    }
    $schemaDiff = Read-StrictUtf8Text -LiteralPath (Join-Path $InputRootPath 'r4/12-schema-diff.txt') -RelativeFile 'r4/12-schema-diff.txt'
    if (
        $schemaDiff -notmatch '(?m)^schema_status=UNCHANGED\r?$' -or
        $schemaDiff -notmatch "(?m)^before_sha256=$beforeHash\r?$" -or
        $schemaDiff -notmatch "(?m)^after_sha256=$afterHash\r?$"
    ) {
        Stop-Package -Code 'E_EVIDENCE_CONTRACT' -RelativeFile 'r4/12-schema-diff.txt'
    }

    return [pscustomobject]@{
        R3RunId = $r3RunId
        R3InquiryId = $r3InquiryId
        R4RunId = $r4RunId
        R4InquiryId = $r4InquiryId
        SchemaHash = $beforeHash
    }
}

function Invoke-SourceValidation {
    $r3Directory = Join-Path $script:InputFullPath 'r3'
    $r4Directory = Join-Path $script:InputFullPath 'r4'
    if (
        -not (Test-Path -LiteralPath $r3Directory -PathType Container) -or
        -not (Test-Path -LiteralPath $r4Directory -PathType Container)
    ) {
        Stop-Package -Code 'E_INPUT_MISSING'
    }
    Assert-NoReparsePoint -LiteralPath $script:InputFullPath
    Assert-NoReparsePoint -LiteralPath $r3Directory
    Assert-NoReparsePoint -LiteralPath $r4Directory

    $r3Manifest = Read-InnerManifest -Scope 'r3' -Directory $r3Directory -ExpectedFiles $script:ExpectedR3Files
    $r4Manifest = Read-InnerManifest -Scope 'r4' -Directory $r4Directory -ExpectedFiles $script:ExpectedR4Files
    $records = @(Get-SourceFileRecords -R3Manifest $r3Manifest -R4Manifest $r4Manifest)
    if ($records.Count -ne 30) {
        Stop-Package -Code 'E_SET_MISMATCH'
    }
    Assert-CaseInsensitiveUnique -Values @($records.RelativePath) -Code 'E_SET_MISMATCH'

    foreach ($record in $records) {
        Assert-FileIsSanitized -LiteralPath $record.SourcePath -RelativeFile $record.RelativePath
    }

    $contract = Assert-EvidenceContract -InputRootPath $script:InputFullPath
    $hashMap = Get-HashMap -Records $records
    return [pscustomobject]@{
        R3Manifest = $r3Manifest
        R4Manifest = $r4Manifest
        Records = $records
        SourceHashMap = $hashMap
        Contract = $contract
    }
}

function New-StageRoot {
    $script:StageNonce = [System.Guid]::NewGuid().ToString('N').Substring(0, 8)
    $stageLeaf = ".$($script:OutputLeaf).partial-$PID-$($script:StageNonce)"
    $stage = [System.IO.Path]::Combine($script:EvidenceRoot, $stageLeaf)
    if (Test-Path -LiteralPath $stage) {
        Stop-Package -Code 'E_PARTIAL_EXISTS'
    }
    [System.IO.Directory]::CreateDirectory($stage) | Out-Null
    $script:StageRoot = $stage
    $script:StageCreated = $true
    $marker = Join-Path $stage '.package-owner'
    Write-Utf8NoBomText -LiteralPath $marker -Text "$($script:StageNonce)`n"
    return $stage
}

function Test-OwnedStageRoot {
    if (-not $script:StageCreated -or -not $script:StageRoot) {
        return $false
    }
    if (-not (Test-Path -LiteralPath $script:StageRoot -PathType Container)) {
        return $false
    }
    try {
        $parent = [System.IO.Path]::GetDirectoryName($script:StageRoot)
        if (
            -not [string]::Equals(
                $parent,
                $script:EvidenceRoot,
                [System.StringComparison]::OrdinalIgnoreCase
            )
        ) {
            return $false
        }
        Assert-NoReparsePoint -LiteralPath $script:StageRoot
        $expectedPattern = '^\.' + [regex]::Escape($script:OutputLeaf) + '\.partial-\d+-[0-9a-f]{8}$'
        $isOwnedPartial = [System.IO.Path]::GetFileName($script:StageRoot) -match $expectedPattern
        $isOwnedPromotedOutput = [string]::Equals(
            $script:StageRoot,
            $script:OutputFullPath,
            [System.StringComparison]::OrdinalIgnoreCase
        )
        if (-not $isOwnedPartial -and -not $isOwnedPromotedOutput) {
            return $false
        }
        $marker = Join-Path $script:StageRoot '.package-owner'
        if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
            return $false
        }
        $markerText = [System.IO.File]::ReadAllText($marker, $script:Utf8Strict)
        return $markerText -eq "$($script:StageNonce)`n"
    }
    catch {
        return $false
    }
}

function Copy-VerifiedSourceFiles {
    param(
        [Parameter(Mandatory)][object[]]$Records,
        [Parameter(Mandatory)][string]$SanitizedRoot
    )

    foreach ($directoryName in @('r3', 'r4', 'package')) {
        [System.IO.Directory]::CreateDirectory(
            (Join-Path $SanitizedRoot $directoryName)
        ) | Out-Null
    }
    foreach ($record in $Records) {
        $destination = Join-Path $SanitizedRoot $record.RelativePath
        if (Test-Path -LiteralPath $destination) {
            Stop-Package -Code 'E_OUTPUT_EXISTS'
        }
        [System.IO.File]::Copy($record.SourcePath, $destination, $false)
    }
}

function Get-StagedSourceHashMap {
    param(
        [Parameter(Mandatory)][object[]]$Records,
        [Parameter(Mandatory)][string]$SanitizedRoot
    )

    $map = [ordered]@{}
    foreach ($record in $Records) {
        $path = Join-Path $SanitizedRoot $record.RelativePath
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            Stop-Package -Code 'E_COPY_HASH_MISMATCH' -RelativeFile $record.RelativePath
        }
        Assert-NoReparsePoint -LiteralPath $path -RelativeFile $record.RelativePath
        $map[$record.RelativePath] = Get-FileSha256 -LiteralPath $path
    }
    return $map
}

function Get-RelativeFilesUnderRoot {
    param([Parameter(Mandatory)][string]$Root)

    $files = @()
    foreach ($file in Get-ChildItem -LiteralPath $Root -Recurse -File -Force) {
        Assert-NoReparsePoint -LiteralPath $file.FullName
        $relative = [System.IO.Path]::GetRelativePath($Root, $file.FullName).Replace('\', '/')
        if (
            [System.IO.Path]::IsPathRooted($relative) -or
            $relative.StartsWith('../', [System.StringComparison]::Ordinal) -or
            $relative.Contains(':') -or
            $relative.Contains('\')
        ) {
            Stop-Package -Code 'E_PATH_BOUNDARY'
        }
        $files += $relative
    }
    return @($files | Sort-Object)
}

function Get-PackageManifestTargets {
    param([Parameter(Mandatory)][object[]]$SourceRecords)

    $targets = @($SourceRecords.RelativePath)
    $targets += 'package/inner-checksum-verification.json'
    $targets += 'package/package-redaction-scan.json'
    return @($targets | Sort-Object)
}

function Write-PackageManifest {
    param(
        [Parameter(Mandatory)][string]$SanitizedRoot,
        [Parameter(Mandatory)][string[]]$Targets
    )

    if ($Targets.Count -ne 32) {
        Stop-Package -Code 'E_PACKAGE_MANIFEST_COUNT'
    }
    Assert-CaseInsensitiveUnique -Values $Targets -Code 'E_PACKAGE_MANIFEST_FORMAT'
    if ($Targets -contains $script:PackageManifestRelativePath) {
        Stop-Package -Code 'E_PACKAGE_MANIFEST_SELF'
    }
    $lines = @()
    foreach ($relative in $Targets) {
        if ($relative -notmatch '^(?:r3|r4|package)/[A-Za-z0-9][A-Za-z0-9._-]*$') {
            Stop-Package -Code 'E_PACKAGE_MANIFEST_FORMAT'
        }
        $path = Join-Path $SanitizedRoot $relative
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            Stop-Package -Code 'E_FILE_MISSING' -RelativeFile $relative
        }
        $lines += "$(Get-FileSha256 -LiteralPath $path)  $relative"
    }
    $manifestPath = Join-Path $SanitizedRoot $script:PackageManifestRelativePath
    Write-Utf8NoBomText -LiteralPath $manifestPath -Text (($lines -join "`n") + "`n")
}

function Read-And-VerifyPackageManifest {
    param(
        [Parameter(Mandatory)][string]$SanitizedRoot,
        [Parameter(Mandatory)][string[]]$ExpectedTargets
    )

    $manifestPath = Join-Path $SanitizedRoot $script:PackageManifestRelativePath
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        Stop-Package -Code 'E_PACKAGE_MANIFEST_MISSING'
    }
    $bytes = [System.IO.File]::ReadAllBytes($manifestPath)
    if (
        $bytes.Length -ge 3 -and
        $bytes[0] -eq 0xEF -and
        $bytes[1] -eq 0xBB -and
        $bytes[2] -eq 0xBF
    ) {
        Stop-Package -Code 'E_PACKAGE_MANIFEST_FORMAT'
    }
    $text = $script:Utf8Strict.GetString($bytes)
    if ($text.Contains("`r") -or -not $text.EndsWith("`n")) {
        Stop-Package -Code 'E_PACKAGE_MANIFEST_FORMAT'
    }
    $parts = $text.Split("`n")
    if ($parts[-1] -ne '') {
        Stop-Package -Code 'E_PACKAGE_MANIFEST_FORMAT'
    }
    $lines = @($parts[0..($parts.Count - 2)])
    if ($lines.Count -ne 32) {
        Stop-Package -Code 'E_PACKAGE_MANIFEST_COUNT'
    }
    $names = @()
    $hashes = [ordered]@{}
    foreach ($line in $lines) {
        if ($line -notmatch '^(?<hash>[0-9a-f]{64})  (?<name>(?:r3|r4|package)/[A-Za-z0-9][A-Za-z0-9._-]*)$') {
            Stop-Package -Code 'E_PACKAGE_MANIFEST_FORMAT'
        }
        $name = $Matches['name']
        if ($name -eq $script:PackageManifestRelativePath) {
            Stop-Package -Code 'E_PACKAGE_MANIFEST_SELF'
        }
        $names += $name
        $hashes[$name] = $Matches['hash']
    }
    Assert-CaseInsensitiveUnique -Values $names -Code 'E_PACKAGE_MANIFEST_FORMAT'
    if (-not (Test-StringSetEqual -Actual $names -Expected $ExpectedTargets)) {
        Stop-Package -Code 'E_PACKAGE_MANIFEST_SET'
    }
    foreach ($name in $names) {
        $path = Join-Path $SanitizedRoot $name
        if ((Get-FileSha256 -LiteralPath $path) -ne $hashes[$name]) {
            Stop-Package -Code 'E_PACKAGE_HASH_MISMATCH' -RelativeFile $name
        }
    }
    return $hashes
}

function New-DeterministicZip {
    param(
        [Parameter(Mandatory)][string]$SanitizedRoot,
        [Parameter(Mandatory)][string]$ZipPath,
        [Parameter(Mandatory)][string[]]$ExpectedEntries
    )

    $temporaryZip = "$ZipPath.tmp-$($script:StageNonce)"
    if (Test-Path -LiteralPath $temporaryZip) {
        Stop-Package -Code 'E_OUTPUT_EXISTS'
    }
    $fileStream = [System.IO.File]::Open(
        $temporaryZip,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
    )
    try {
        $archive = [System.IO.Compression.ZipArchive]::new(
            $fileStream,
            [System.IO.Compression.ZipArchiveMode]::Create,
            $false
        )
        try {
            $fixedTimestamp = [System.DateTimeOffset]::new(
                2026,
                8,
                21,
                0,
                0,
                0,
                [System.TimeSpan]::Zero
            )
            foreach ($relative in @($ExpectedEntries | Sort-Object)) {
                $source = Join-Path $SanitizedRoot $relative
                $entry = $archive.CreateEntry(
                    $relative,
                    [System.IO.Compression.CompressionLevel]::Optimal
                )
                $entry.LastWriteTime = $fixedTimestamp
                $input = [System.IO.File]::Open(
                    $source,
                    [System.IO.FileMode]::Open,
                    [System.IO.FileAccess]::Read,
                    [System.IO.FileShare]::Read
                )
                try {
                    $output = $entry.Open()
                    try {
                        $input.CopyTo($output)
                    }
                    finally {
                        $output.Dispose()
                    }
                }
                finally {
                    $input.Dispose()
                }
            }
        }
        finally {
            $archive.Dispose()
        }
    }
    finally {
        $fileStream.Dispose()
    }
    [System.IO.File]::Move($temporaryZip, $ZipPath)
}

function Read-ZipEntryBytes {
    param([Parameter(Mandatory)][System.IO.Compression.ZipArchiveEntry]$Entry)

    $memory = [System.IO.MemoryStream]::new()
    try {
        $stream = $Entry.Open()
        try {
            $stream.CopyTo($memory)
        }
        finally {
            $stream.Dispose()
        }
        return $memory.ToArray()
    }
    finally {
        $memory.Dispose()
    }
}

function Assert-ZipPackage {
    param(
        [Parameter(Mandatory)][string]$ZipPath,
        [Parameter(Mandatory)][string]$SanitizedRoot,
        [Parameter(Mandatory)][string[]]$ExpectedEntries,
        [Parameter(Mandatory)][System.Collections.IDictionary]$PackageManifestHashes
    )

    $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        $fileEntries = @($archive.Entries | Where-Object { $_.Name -ne '' })
        $directoryEntries = @($archive.Entries | Where-Object { $_.Name -eq '' })
        if ($directoryEntries.Count -ne 0 -or $fileEntries.Count -ne 33) {
            Stop-Package -Code 'E_ZIP_ENTRY_COUNT'
        }
        $entryNames = @($fileEntries | ForEach-Object { $_.FullName })
        Assert-CaseInsensitiveUnique -Values $entryNames -Code 'E_ZIP_ENTRY_SET'
        if (-not (Test-StringSetEqual -Actual $entryNames -Expected $ExpectedEntries)) {
            Stop-Package -Code 'E_ZIP_ENTRY_SET'
        }
        if (@($entryNames | Where-Object { $_ -eq $script:PackageManifestRelativePath }).Count -ne 1) {
            Stop-Package -Code 'E_PACKAGE_MANIFEST_MISSING'
        }

        [long]$totalUncompressed = 0
        foreach ($entry in $fileEntries) {
            $name = $entry.FullName
            if (
                $name.Contains('\') -or
                $name.Contains(':') -or
                $name.StartsWith('/', [System.StringComparison]::Ordinal) -or
                $name.Split('/') -contains '..' -or
                $name.EndsWith('.') -or
                $name.EndsWith(' ')
            ) {
                Stop-Package -Code 'E_ZIP_PATH'
            }
            $unixType = (($entry.ExternalAttributes -shr 16) -band 0xF000)
            if ($unixType -eq 0xA000) {
                Stop-Package -Code 'E_ZIP_PATH'
            }
            if ($entry.Length -gt $script:MaxTextFileBytes) {
                Stop-Package -Code 'E_ZIP_BOMB'
            }
            $totalUncompressed += $entry.Length
            if ($totalUncompressed -gt $script:MaxArchiveUncompressedBytes) {
                Stop-Package -Code 'E_ZIP_BOMB'
            }
            if (
                $entry.Length -gt 0 -and
                $entry.CompressedLength -eq 0
            ) {
                Stop-Package -Code 'E_ZIP_BOMB'
            }
            if (
                $entry.CompressedLength -gt 0 -and
                ($entry.Length / $entry.CompressedLength) -gt 100
            ) {
                Stop-Package -Code 'E_ZIP_BOMB'
            }

            $bytes = Read-ZipEntryBytes -Entry $entry
            $stageHash = Get-FileSha256 -LiteralPath (Join-Path $SanitizedRoot $name)
            if ((Get-Sha256FromBytes -Bytes $bytes) -ne $stageHash) {
                Stop-Package -Code 'E_ZIP_HASH_MISMATCH' -RelativeFile $name
            }
            try {
                $text = $script:Utf8Strict.GetString($bytes)
            }
            catch {
                Stop-Package -Code 'E_UTF8_INVALID' -RelativeFile $name
            }
            Assert-TextIsSanitized -Text $text -RelativeFile $name
        }

        foreach ($name in $PackageManifestHashes.Keys) {
            $entry = $fileEntries | Where-Object { $_.FullName -eq $name } | Select-Object -First 1
            if ($null -eq $entry) {
                Stop-Package -Code 'E_ZIP_ENTRY_SET'
            }
            $bytes = Read-ZipEntryBytes -Entry $entry
            if ((Get-Sha256FromBytes -Bytes $bytes) -ne $PackageManifestHashes[$name]) {
                Stop-Package -Code 'E_ZIP_HASH_MISMATCH' -RelativeFile $name
            }
        }
    }
    finally {
        $archive.Dispose()
    }
}

function Assert-SidecarTextSafe {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$RelativeFile
    )

    Assert-TextIsSanitized -Text $Text -RelativeFile $RelativeFile
    if (
        $Text -match '(?i)[A-Z]:[\\/]' -or
        $Text -match '(?i)\\\\[^\\\s]+\\' -or
        $Text -match '(?<![A-Za-z0-9])/(?:Users|home|tmp|var|etc|opt|root|mnt|Volumes)/'
    ) {
        Stop-Package -Code 'E_SIDECAR_UNSAFE' -RelativeFile $RelativeFile
    }
}

function Invoke-PackageBuild {
    param([Parameter(Mandatory)]$Validation)

    $stage = New-StageRoot
    $sanitizedRoot = Join-Path $stage 'sanitized'
    [System.IO.Directory]::CreateDirectory($sanitizedRoot) | Out-Null

    Copy-VerifiedSourceFiles -Records $Validation.Records -SanitizedRoot $sanitizedRoot
    $stagedHashMap = Get-StagedSourceHashMap -Records $Validation.Records -SanitizedRoot $sanitizedRoot
    Assert-HashMapsEqual -Expected $Validation.SourceHashMap -Actual $stagedHashMap -Code 'E_COPY_HASH_MISMATCH'

    $sourceHashAfterCopy = Get-HashMap -Records $Validation.Records
    Assert-HashMapsEqual -Expected $Validation.SourceHashMap -Actual $sourceHashAfterCopy -Code 'E_TOCTOU'

    $innerVerification = [ordered]@{
        status = 'PASS'
        source_ref = $ExpectedSourceRef
        r3 = [ordered]@{
            expected_target_count = 8
            verified_target_count = 8
        }
        r4 = [ordered]@{
            expected_target_count = 20
            verified_target_count = 20
        }
        missing_count = 0
        hash_mismatch_count = 0
        unexpected_file_count = 0
        source_unchanged = $true
        original_files_modified = $false
        db_accessed = $false
        secret_values_printed = $false
    }
    $innerRelative = 'package/inner-checksum-verification.json'
    $innerText = ConvertTo-SafeJsonText -Value $innerVerification
    Assert-SidecarTextSafe -Text $innerText -RelativeFile $innerRelative
    Write-Utf8NoBomText -LiteralPath (Join-Path $sanitizedRoot $innerRelative) -Text $innerText

    $preScanFiles = @(Get-RelativeFilesUnderRoot -Root $sanitizedRoot)
    if ($preScanFiles.Count -ne 31) {
        Stop-Package -Code 'E_SET_MISMATCH'
    }
    foreach ($relative in $preScanFiles) {
        Assert-FileIsSanitized -LiteralPath (Join-Path $sanitizedRoot $relative) -RelativeFile $relative
    }

    $redactionReport = [ordered]@{
        status = 'PASS'
        scanned_file_count = 31
        finding_count = 0
        findings = @()
        source_file_count = 30
        secret_values_printed = $false
        local_environment_metadata_included = $false
    }
    $redactionRelative = 'package/package-redaction-scan.json'
    $redactionText = ConvertTo-SafeJsonText -Value $redactionReport
    Assert-SidecarTextSafe -Text $redactionText -RelativeFile $redactionRelative
    Write-Utf8NoBomText -LiteralPath (Join-Path $sanitizedRoot $redactionRelative) -Text $redactionText
    Assert-FileIsSanitized -LiteralPath (Join-Path $sanitizedRoot $redactionRelative) -RelativeFile $redactionRelative

    $manifestTargets = @(Get-PackageManifestTargets -SourceRecords $Validation.Records)
    $filesBeforeManifest = @(Get-RelativeFilesUnderRoot -Root $sanitizedRoot)
    if (-not (Test-StringSetEqual -Actual $filesBeforeManifest -Expected $manifestTargets)) {
        Stop-Package -Code 'E_PACKAGE_MANIFEST_SET'
    }
    Write-PackageManifest -SanitizedRoot $sanitizedRoot -Targets $manifestTargets
    $packageManifestHashes = Read-And-VerifyPackageManifest -SanitizedRoot $sanitizedRoot -ExpectedTargets $manifestTargets

    $expectedZipEntries = @($manifestTargets + $script:PackageManifestRelativePath | Sort-Object)
    $stageFiles = @(Get-RelativeFilesUnderRoot -Root $sanitizedRoot)
    if ($stageFiles.Count -ne 33 -or -not (Test-StringSetEqual -Actual $stageFiles -Expected $expectedZipEntries)) {
        Stop-Package -Code 'E_SET_MISMATCH'
    }
    foreach ($relative in $stageFiles) {
        Assert-FileIsSanitized -LiteralPath (Join-Path $sanitizedRoot $relative) -RelativeFile $relative
    }

    $zipPath = Join-Path $stage $script:ArchiveName
    New-DeterministicZip -SanitizedRoot $sanitizedRoot -ZipPath $zipPath -ExpectedEntries $expectedZipEntries
    Assert-ZipPackage -ZipPath $zipPath -SanitizedRoot $sanitizedRoot -ExpectedEntries $expectedZipEntries -PackageManifestHashes $packageManifestHashes
    $zipSha256 = Get-FileSha256 -LiteralPath $zipPath

    $finalZipFullPath = Join-Path $script:OutputFullPath $script:ArchiveName
    $summary = [ordered]@{
        status = 'PASS'
        source_ref = $ExpectedSourceRef
        input_root = ConvertTo-RepoRelativePath -FullPath $script:InputFullPath
        output_root = ConvertTo-RepoRelativePath -FullPath $script:OutputFullPath
        zip_path = ConvertTo-RepoRelativePath -FullPath $finalZipFullPath
        archive_name = $script:ArchiveName
        archive_size_bytes = (Get-Item -LiteralPath $zipPath).Length
        zip_sha256 = $zipSha256
        zip_entry_count = 33
        package_manifest_record_count = 32
        package_sha_present = $true
        package_sha_self_excluded = $true
        exact_entry_set_match = $true
        r3_expected_count = 8
        r3_verified_count = 8
        r4_expected_count = 20
        r4_verified_count = 20
        source_file_count = 30
        missing_count = 0
        hash_mismatch_count = 0
        unexpected_file_count = 0
        sensitive_finding_count = 0
        migration_status = 'UNCHANGED'
        schema_status = 'UNCHANGED'
        visits_0005 = 'NOT_APPLIED_P1_HOLD'
        r4_compare_status = 'PASS'
        source_unchanged = $true
        zip_verification = 'PASS'
        original_files_modified = $false
        db_accessed = $false
        secret_values_printed = $false
        generated_at_utc = [System.DateTimeOffset]::UtcNow.ToString('o')
    }
    $summaryText = ConvertTo-SafeJsonText -Value $summary
    Assert-SidecarTextSafe -Text $summaryText -RelativeFile $script:SummaryName

    $hashText = "$zipSha256  $($script:ArchiveName)`n"
    Assert-SidecarTextSafe -Text $hashText -RelativeFile $script:ArchiveHashName
    if ($hashText -notmatch "^[0-9a-f]{64}  $([regex]::Escape($script:ArchiveName))`n$") {
        Stop-Package -Code 'E_SIDECAR_UNSAFE'
    }

    $summaryPath = Join-Path $stage $script:SummaryName
    $hashPath = Join-Path $stage $script:ArchiveHashName
    Write-Utf8NoBomText -LiteralPath $summaryPath -Text $summaryText
    Write-Utf8NoBomText -LiteralPath $hashPath -Text $hashText
    Assert-FileIsSanitized -LiteralPath $summaryPath -RelativeFile $script:SummaryName
    Assert-FileIsSanitized -LiteralPath $hashPath -RelativeFile $script:ArchiveHashName

    $summaryRoundTrip = Read-JsonHashtable -LiteralPath $summaryPath -RelativeFile $script:SummaryName
    Assert-MapValueEquals -Map $summaryRoundTrip -Key 'zip_sha256' -Expected $zipSha256 -RelativeFile $script:SummaryName
    Assert-MapValueEquals -Map $summaryRoundTrip -Key 'zip_entry_count' -Expected 33 -RelativeFile $script:SummaryName
    Assert-MapValueEquals -Map $summaryRoundTrip -Key 'package_manifest_record_count' -Expected 32 -RelativeFile $script:SummaryName
    $hashRoundTrip = Read-StrictUtf8Text -LiteralPath $hashPath -RelativeFile $script:ArchiveHashName
    if ($hashRoundTrip -ne $hashText -or (Get-FileSha256 -LiteralPath $zipPath) -ne $zipSha256) {
        Stop-Package -Code 'E_ZIP_HASH_MISMATCH'
    }

    $sourceHashBeforePromotion = Get-HashMap -Records $Validation.Records
    Assert-HashMapsEqual -Expected $Validation.SourceHashMap -Actual $sourceHashBeforePromotion -Code 'E_TOCTOU'
    Assert-ZipPackage -ZipPath $zipPath -SanitizedRoot $sanitizedRoot -ExpectedEntries $expectedZipEntries -PackageManifestHashes $packageManifestHashes

    if (Test-Path -LiteralPath $script:OutputFullPath) {
        Stop-Package -Code 'E_OUTPUT_EXISTS'
    }
    if (-not (Test-OwnedStageRoot)) {
        Stop-Package -Code 'E_PARTIAL_OWNERSHIP'
    }
    [System.IO.Directory]::Move($stage, $script:OutputFullPath)
    $script:StageRoot = $script:OutputFullPath
    if (-not (Test-OwnedStageRoot)) {
        Stop-Package -Code 'E_PARTIAL_OWNERSHIP'
    }
    [System.IO.File]::Delete((Join-Path $script:StageRoot '.package-owner'))
    $script:StageCreated = $false
    $script:StageRoot = $null

    return [pscustomobject]@{
        ZipSha256 = $zipSha256
        ZipEntryCount = 33
        PackageManifestRecordCount = 32
    }
}

function Initialize-PackageContext {
    $script:RepoRoot = [System.IO.Path]::GetFullPath(
        (Join-Path $PSScriptRoot '..\..')
    )
    $script:EvidenceRoot = [System.IO.Path]::GetFullPath(
        (Join-Path $script:RepoRoot 'web\.runtime\qa-evidence')
    )
    if (-not (Test-Path -LiteralPath $script:EvidenceRoot -PathType Container)) {
        Stop-Package -Code 'E_EVIDENCE_ROOT_MISSING'
    }
    Assert-NoReparsePoint -LiteralPath $script:RepoRoot
    Assert-NoReparsePoint -LiteralPath (Join-Path $script:RepoRoot 'web')
    Assert-NoReparsePoint -LiteralPath (Join-Path $script:RepoRoot 'web/.runtime')
    Assert-NoReparsePoint -LiteralPath $script:EvidenceRoot

    if ($ExpectedSourceRef -notmatch '^[0-9a-f]{40}$') {
        Stop-Package -Code 'E_SOURCE_REF'
    }
    $script:InputFullPath = Resolve-RepositoryRelativeRoot -Value $InputRoot -Kind 'Input'
    $script:OutputFullPath = Resolve-RepositoryRelativeRoot -Value $OutputRoot -Kind 'Output'
    if (
        [string]::Equals(
            $script:InputFullPath,
            $script:OutputFullPath,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    ) {
        Stop-Package -Code 'E_PATH_BOUNDARY'
    }
    $script:OutputLeaf = [System.IO.Path]::GetFileName($script:OutputFullPath)

    $mutexMaterial = $script:EvidenceRoot.ToLowerInvariant()
    $mutexHash = Get-Sha256FromBytes -Bytes $script:Utf8NoBom.GetBytes($mutexMaterial)
    $script:Mutex = [System.Threading.Mutex]::new(
        $false,
        "WaterBridge.WebG4Evidence.$($mutexHash.Substring(0, 16))"
    )
    try {
        $script:MutexAcquired = $script:Mutex.WaitOne(0)
    }
    catch [System.Threading.AbandonedMutexException] {
        $script:MutexAcquired = $true
    }
    if (-not $script:MutexAcquired) {
        Stop-Package -Code 'E_LOCKED'
    }
}

function Remove-OwnedPartialOnFailure {
    if (-not (Test-OwnedStageRoot)) {
        return $false
    }
    try {
        [System.IO.Directory]::Delete($script:StageRoot, $true)
        $script:StageCreated = $false
        $script:StageRoot = $null
        return $true
    }
    catch {
        return $false
    }
}

$exitCode = 0
try {
    Initialize-PackageContext
    $validation = Invoke-SourceValidation

    if ($ValidateOnly) {
        [Console]::Out.WriteLine('PACKAGE_STATUS=VALIDATE_ONLY_PASS')
        [Console]::Out.WriteLine('R3_MANIFEST=8/8')
        [Console]::Out.WriteLine('R4_MANIFEST=20/20')
        [Console]::Out.WriteLine('MISSING_COUNT=0')
        [Console]::Out.WriteLine('HASH_MISMATCH_COUNT=0')
        [Console]::Out.WriteLine('UNEXPECTED_FILE_COUNT=0')
        [Console]::Out.WriteLine('SENSITIVE_FINDING_COUNT=0')
    }
    else {
        $result = Invoke-PackageBuild -Validation $validation
        [Console]::Out.WriteLine('PACKAGE_STATUS=PASS')
        [Console]::Out.WriteLine('R3_MANIFEST=8/8')
        [Console]::Out.WriteLine('R4_MANIFEST=20/20')
        [Console]::Out.WriteLine('MISSING_COUNT=0')
        [Console]::Out.WriteLine('HASH_MISMATCH_COUNT=0')
        [Console]::Out.WriteLine('UNEXPECTED_FILE_COUNT=0')
        [Console]::Out.WriteLine('SENSITIVE_FINDING_COUNT=0')
        [Console]::Out.WriteLine("ZIP_ENTRY_COUNT=$($result.ZipEntryCount)")
        [Console]::Out.WriteLine('ZIP_VERIFY=PASS')
        [Console]::Out.WriteLine("ZIP_SHA256=$($result.ZipSha256)")
    }
}
catch {
    $code = Get-SafePackageCode -ErrorRecord $_
    $relativeFile = Get-SafeRelativeFile -ErrorRecord $_
    $partialRemoved = Remove-OwnedPartialOnFailure
    [Console]::Error.WriteLine('PACKAGE_STATUS=FAIL')
    [Console]::Error.WriteLine("ERROR_CODE=$code")
    if ($code -eq 'E_UNEXPECTED') {
        [Console]::Error.WriteLine(
            "ERROR_LINE=$($_.InvocationInfo.ScriptLineNumber)"
        )
        $errorType = $_.Exception.GetType().Name
        if ($errorType -match '^[A-Za-z0-9_]+$') {
            [Console]::Error.WriteLine("ERROR_TYPE=$errorType")
        }
        $errorId = [string]$_.FullyQualifiedErrorId
        if ($errorId -match '^[A-Za-z0-9_,.-]+$') {
            [Console]::Error.WriteLine("ERROR_ID=$errorId")
        }
    }
    if ($relativeFile) {
        [Console]::Error.WriteLine("RELATIVE_FILE=$relativeFile")
    }
    if ($script:StageCreated -and -not $partialRemoved) {
        [Console]::Error.WriteLine('PARTIAL_RETAINED=true')
    }
    $exitCode = 1
}
finally {
    if ($script:MutexAcquired -and $null -ne $script:Mutex) {
        try {
            $script:Mutex.ReleaseMutex()
        }
        catch {
            # The fixed final status above remains authoritative.
        }
    }
    if ($null -ne $script:Mutex) {
        $script:Mutex.Dispose()
    }
}

exit $exitCode
