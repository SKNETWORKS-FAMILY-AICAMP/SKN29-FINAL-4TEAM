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
    "val fillAlpha = if (strong) 0.24f else 0.14f"
    "alpha = 1.00f"
    "palette.accent.copy(alpha = 0.34f)"
    "Color.White.copy(alpha = 0.14f)"
    "elevation = if (danger) 4.dp else 2.dp"
)) {
    if (-not $Component.Contains($Marker)) {
        throw "Transparent Glass marker is missing: $Marker"
    }
}

Write-Host "Stopping existing Gradle daemons..."
& (Join-Path $MobilePath "gradlew.bat") --stop
if ($LASTEXITCODE -ne 0) {
    throw "gradlew --stop failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Running clean in a separate Gradle invocation..."
$CleanProcess = Start-Process `
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

if ($CleanProcess.ExitCode -ne 0) {
    throw "T-050 clean failed with exit code $($CleanProcess.ExitCode)"
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

$BuildProcess = Start-Process `
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

if ($BuildProcess.ExitCode -ne 0) {
    throw "T-050 Gradle verification failed with exit code $($BuildProcess.ExitCode)"
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
Write-Host "T050_TRANSPARENT_GLASS_BUILD_PASS" `
    -ForegroundColor Green
Write-Host "Customer APK: $CustomerApk"
Write-Host "Technician APK: $TechnicianApk"
