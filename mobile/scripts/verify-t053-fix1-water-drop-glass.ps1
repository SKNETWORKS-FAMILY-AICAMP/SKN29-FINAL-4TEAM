param(
    [string]$RepoPath = "C:\skn29\WaterCare"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoPath = [IO.Path]::GetFullPath($RepoPath)
$MobilePath = Join-Path $RepoPath "mobile"

$ComponentPath = Join-Path $RepoPath (
    "mobile\core\src\main\java\com\skn29\watercare\core\ui\" +
    "components\ReferenceDashboardComponents.kt"
)

$Component = Get-Content `
    -LiteralPath $ComponentPath `
    -Raw `
    -Encoding UTF8

foreach ($Marker in @(
    "ReferenceWaterDropPanelShape"
    "topStart = 34.dp"
    "topEnd = 46.dp"
    "val accentPrimaryAlpha = if (enabled) 0.92f else 0.26f"
    "val shape = RoundedCornerShape(999.dp)"
    "private fun ReferenceProgressBar("
    "private fun ReferencePill("
    "ReferenceWaterDropTileShape"
    "elevation = if (item.enabled) 6.dp else 1.dp"
)) {
    if (-not $Component.Contains($Marker)) {
        throw "T-053 FIX1 marker is missing: $Marker"
    }
}

$ProgressCount = (
    [regex]::Matches(
        $Component,
        "private fun ReferenceProgressBar\("
    )
).Count

$PillCount = (
    [regex]::Matches(
        $Component,
        "private fun ReferencePill\("
    )
).Count

if ($ProgressCount -ne 1) {
    throw "ReferenceProgressBar definition count must be 1. Actual: $ProgressCount"
}
if ($PillCount -ne 1) {
    throw "ReferencePill definition count must be 1. Actual: $PillCount"
}

Write-Host "Stopping existing Gradle daemons..."
& (Join-Path $MobilePath "gradlew.bat") --stop
if ($LASTEXITCODE -ne 0) {
    throw "gradlew --stop failed."
}

Write-Host ""
Write-Host "Running clean separately..."
$Clean = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList @(
        "/d"
        "/s"
        "/c"
        "call gradlew.bat :customer-app:clean :technician-app:clean --no-daemon --max-workers=4"
    ) `
    -WorkingDirectory $MobilePath `
    -NoNewWindow `
    -Wait `
    -PassThru

if ($Clean.ExitCode -ne 0) {
    throw "T-053 FIX1 clean failed with exit code $($Clean.ExitCode)"
}

Write-Host ""
Write-Host "Running tests and APK builds..."
$BuildCommand = @(
    "call"
    "gradlew.bat"
    ":core:test"
    ":customer-app:testDebugUnitTest"
    ":customer-app:assembleDebug"
    ":technician-app:testDebugUnitTest"
    ":technician-app:assembleDebug"
    "--no-daemon"
    "--max-workers=4"
) -join " "

$Build = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList @(
        "/d"
        "/s"
        "/c"
        $BuildCommand
    ) `
    -WorkingDirectory $MobilePath `
    -NoNewWindow `
    -Wait `
    -PassThru

if ($Build.ExitCode -ne 0) {
    throw "T-053 FIX1 Gradle build failed with exit code $($Build.ExitCode)"
}

$CustomerApk = Join-Path $MobilePath `
    "customer-app\build\outputs\apk\debug\customer-app-debug.apk"
$TechnicianApk = Join-Path $MobilePath `
    "technician-app\build\outputs\apk\debug\technician-app-debug.apk"

if (-not (Test-Path -LiteralPath $CustomerApk)) {
    throw "Customer APK not found: $CustomerApk"
}
if (-not (Test-Path -LiteralPath $TechnicianApk)) {
    throw "Technician APK not found: $TechnicianApk"
}

Write-Host ""
Write-Host "T053_FIX1_WATER_DROP_GLASS_BUILD_PASS" `
    -ForegroundColor Green
Write-Host "Customer APK: $CustomerApk"
Write-Host "Technician APK: $TechnicianApk"
