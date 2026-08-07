param(
    [string]$RepoPath = "C:\skn29\WaterCare"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Normalize-Lf([string]$Text) {
    return $Text.Replace("`r`n", "`n").Replace("`r", "`n")
}

function Read-Utf8Lf([string]$Path) {
    return Normalize-Lf (
        [IO.File]::ReadAllText(
            $Path,
            [Text.UTF8Encoding]::new($false)
        )
    )
}

function Write-Utf8Lf(
    [string]$Path,
    [string]$Content
) {
    $Directory = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $Directory)) {
        New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    }

    [IO.File]::WriteAllText(
        $Path,
        (Normalize-Lf $Content),
        [Text.UTF8Encoding]::new($false)
    )
}

function Replace-RegexOnce(
    [string]$Content,
    [string]$Pattern,
    [string]$Replacement,
    [string]$Label
) {
    $Regex = [regex]::new(
        $Pattern,
        [Text.RegularExpressions.RegexOptions]::Singleline
    )
    $Matches = $Regex.Matches($Content)

    if ($Matches.Count -ne 1) {
        throw "$Label regex match count must be 1. Actual: $($Matches.Count)"
    }

    return $Regex.Replace(
        $Content,
        (Normalize-Lf $Replacement),
        1
    )
}

$RepoPath = [IO.Path]::GetFullPath($RepoPath)

$RepositoriesPath = Join-Path $RepoPath (
    "mobile\core\src\main\java\com\skn29\watercare\core\" +
    "repository\Repositories.kt"
)
$StorePath = Join-Path $RepoPath (
    "mobile\core\src\main\java\com\skn29\watercare\core\" +
    "repository\CancelIdempotencyKeyStore.kt"
)

$Repositories = Read-Utf8Lf $RepositoriesPath

# Remove now-unused UUID import from Repositories.kt.
$Repositories = $Repositories.Replace(
    "import java.util.UUID`n",
    ""
)

# Add retry-safe store to RemoteInquiryRepository.
$Repositories = Replace-RegexOnce `
    -Content $Repositories `
    -Pattern (
        'class RemoteInquiryRepository\(\s*' +
        'private val api: WaterCareApi,\s*' +
        'private val json: Json,\s*' +
        '\) : InquiryRepository \{'
    ) `
    -Replacement @'
class RemoteInquiryRepository(
    private val api: WaterCareApi,
    private val json: Json,
    private val cancelIdempotencyKeys: CancelIdempotencyKeyStore =
        CancelIdempotencyKeyStore(),
) : InquiryRepository {
'@ `
    -Label "RemoteInquiryRepository idempotency store"

# Replace cancel implementation without changing public repository interface.
$Repositories = Replace-RegexOnce `
    -Content $Repositories `
    -Pattern (
        'override suspend fun cancel\(\s*' +
        'inquiryId: String,\s*' +
        'stateVersion: Int,\s*' +
        'reasonCode: String,\s*' +
        'reasonDetail: String\?,\s*' +
        '\): ApiResult<CancelInquiryResponse> = safeApiCall\(json\) \{\s*' +
        'api\.cancelInquiry\(\s*' +
        'inquiryId = inquiryId,\s*' +
        'idempotencyKey = UUID\.randomUUID\(\)\.toString\(\),\s*' +
        'body = CancelInquiryRequest\(stateVersion, reasonCode, reasonDetail\),\s*' +
        '\)\s*' +
        '\}'
    ) `
    -Replacement @'
override suspend fun cancel(
        inquiryId: String,
        stateVersion: Int,
        reasonCode: String,
        reasonDetail: String?,
    ): ApiResult<CancelInquiryResponse> {
        val operation = CancelOperationIdentity(
            inquiryId = inquiryId,
            stateVersion = stateVersion,
            reasonCode = reasonCode,
            reasonDetail = reasonDetail,
        )
        val idempotencyKey = cancelIdempotencyKeys.keyFor(operation)

        val result = safeApiCall(json) {
            api.cancelInquiry(
                inquiryId = inquiryId,
                idempotencyKey = idempotencyKey,
                body = CancelInquiryRequest(
                    stateVersion,
                    reasonCode,
                    reasonDetail,
                ),
            )
        }

        if (result is ApiResult.Success) {
            cancelIdempotencyKeys.complete(operation)
        }

        return result
    }
'@ `
    -Label "Retry-safe cancel implementation"

Write-Utf8Lf -Path $RepositoriesPath -Content $Repositories

$Store = @'
package com.skn29.watercare.core.repository

import java.util.UUID

data class CancelOperationIdentity(
    val inquiryId: String,
    val stateVersion: Int,
    val reasonCode: String,
    val reasonDetail: String?,
)

class CancelIdempotencyKeyStore(
    private val createKey: () -> String = {
        UUID.randomUUID().toString()
    },
) {
    private val lock = Any()
    private val pending = mutableMapOf<CancelOperationIdentity, String>()

    fun keyFor(operation: CancelOperationIdentity): String =
        synchronized(lock) {
            pending.getOrPut(operation, createKey)
        }

    fun complete(operation: CancelOperationIdentity) {
        synchronized(lock) {
            pending.remove(operation)
        }
    }
}
'@

Write-Utf8Lf -Path $StorePath -Content $Store

Write-Host "T057_TRANSFORM_PASS" -ForegroundColor Green
