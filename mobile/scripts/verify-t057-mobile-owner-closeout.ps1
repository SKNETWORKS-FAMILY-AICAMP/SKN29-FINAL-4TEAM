param(
    [string]$RepoPath = "C:\skn29\WaterCare"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoPath = [IO.Path]::GetFullPath($RepoPath)
$MobilePath = Join-Path $RepoPath "mobile"

$RepositoriesPath = Join-Path $RepoPath (
    "mobile\core\src\main\java\com\skn29\watercare\core\" +
    "repository\Repositories.kt"
)
$StorePath = Join-Path $RepoPath (
    "mobile\core\src\main\java\com\skn29\watercare\core\" +
    "repository\CancelIdempotencyKeyStore.kt"
)
$TestPath = Join-Path $RepoPath (
    "mobile\core\src\test\java\com\skn29\watercare\core\" +
    "repository\CancelIdempotencyKeyStoreTest.kt"
)

$Repositories = Get-Content $RepositoriesPath -Raw -Encoding UTF8
$Store = Get-Content $StorePath -Raw -Encoding UTF8
$Test = Get-Content $TestPath -Raw -Encoding UTF8

foreach ($Marker in @(
    "cancelIdempotencyKeys: CancelIdempotencyKeyStore"
    "val idempotencyKey = cancelIdempotencyKeys.keyFor(operation)"
    "idempotencyKey = idempotencyKey"
    "cancelIdempotencyKeys.complete(operation)"
)) {
    if (-not $Repositories.Contains($Marker)) {
        throw "Repositories marker missing: $Marker"
    }
}

if ($Repositories.Contains("UUID.randomUUID().toString()")) {
    throw "RemoteInquiryRepository still creates cancel key per call."
}

if ($Store.Contains("internal class CancelIdempotencyKeyStore")) {
    throw "CancelIdempotencyKeyStore must not be internal when exposed by the public repository constructor."
}
if ($Store.Contains("internal data class CancelOperationIdentity")) {
    throw "CancelOperationIdentity must not be internal when used by the public helper API."
}

foreach ($Marker in @(
    "data class CancelOperationIdentity"
    "class CancelIdempotencyKeyStore"
    "pending.getOrPut(operation, createKey)"
    "pending.remove(operation)"
)) {
    if (-not $Store.Contains($Marker)) {
        throw "CancelIdempotencyKeyStore marker missing: $Marker"
    }
}

foreach ($Marker in @(
    "import org.junit.Assert.assertEquals"
    "import org.junit.Assert.assertNotEquals"
    "import org.junit.Test"
    "samePendingCancelOperationReusesSameKey"
    "changedOperationGetsDifferentKey"
    "successfulCompletionAllowsNewOperationKey"
)) {
    if (-not $Test.Contains($Marker)) {
        throw "Idempotency test marker missing: $Marker"
    }
}

if ($Test.Contains("import kotlin.test")) {
    throw "T-057 tests must use the project's JUnit4 test framework, not kotlin.test."
}

Write-Host "T057_SOURCE_CONTRACT_PASS" -ForegroundColor Green

$CapabilityScript = Join-Path $MobilePath `
    "scripts\check-backend-runtime-capabilities-t057.ps1"

& powershell.exe `
    -NoProfile `
    -ExecutionPolicy Bypass `
    -File $CapabilityScript `
    -RepoPath $RepoPath

if ($LASTEXITCODE -ne 0) {
    throw "Backend capability matrix failed."
}

Write-Host ""
Write-Host "Running Core + Customer + Technician verification..."

& (Join-Path $MobilePath "gradlew.bat") --stop
if ($LASTEXITCODE -ne 0) {
    throw "gradlew --stop failed."
}

$Build = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList @(
        "/d",
        "/s",
        "/c",
        "call verify-build.bat"
    ) `
    -WorkingDirectory $MobilePath `
    -NoNewWindow `
    -Wait `
    -PassThru

if ($Build.ExitCode -ne 0) {
    throw "verify-build.bat failed with exit code $($Build.ExitCode)"
}

$CustomerApk = Join-Path $MobilePath `
    "customer-app\build\outputs\apk\debug\customer-app-debug.apk"
$TechnicianApk = Join-Path $MobilePath `
    "technician-app\build\outputs\apk\debug\technician-app-debug.apk"

if (-not (Test-Path $CustomerApk)) {
    throw "Customer APK missing."
}
if (-not (Test-Path $TechnicianApk)) {
    throw "Technician APK missing."
}

$CustomerHash = (
    Get-FileHash $CustomerApk -Algorithm SHA256
).Hash
$TechnicianHash = (
    Get-FileHash $TechnicianApk -Algorithm SHA256
).Hash

Write-Host ""
Write-Host "T057_MOBILE_OWNER_SCOPE_BUILD_PASS" -ForegroundColor Green
Write-Host "Customer APK SHA256: $CustomerHash"
Write-Host "Technician APK SHA256: $TechnicianHash"
