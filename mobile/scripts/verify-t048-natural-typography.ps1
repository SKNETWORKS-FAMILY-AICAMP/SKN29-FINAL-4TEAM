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
$ThemePath = Join-Path $RepoPath (
    "mobile\core\src\main\java\com\skn29\watercare\core\ui\" +
    "theme\WaterCareTheme.kt"
)

$Component = Get-Content `
    -LiteralPath $ComponentPath `
    -Raw `
    -Encoding UTF8
$Theme = Get-Content `
    -LiteralPath $ThemePath `
    -Raw `
    -Encoding UTF8

foreach ($Forbidden in @(
    "FontWeight.Black"
    "FontWeight.ExtraBold"
    'text = "♙'
    'symbol = "♢"'
    'symbol = "⌕"'
)) {
    if ($Component.Contains($Forbidden)) {
        throw "Forbidden typography/glyph marker remains: $Forbidden"
    }
}

foreach ($Required in @(
    "FontFamily.SansSerif"
    "ReferenceRoleChip"
    "ReferenceHeaderIcon.Notification"
    "ReferenceHeaderIcon.Support"
    "Canvas(modifier = Modifier.size"
)) {
    if (-not $Component.Contains($Required)) {
        throw "Required component marker missing: $Required"
    }
}

if (-not $Theme.Contains("FontFamily.SansSerif")) {
    throw "Global SansSerif typography is missing."
}

$GradleCommand = @(
    "call"
    "gradlew.bat"
    ":core:test"
    ":customer-app:testDebugUnitTest"
    ":customer-app:assembleDebug"
    ":technician-app:testDebugUnitTest"
    ":technician-app:assembleDebug"
    "--no-daemon"
) -join " "

$Process = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList @(
        "/d"
        "/s"
        "/c"
        $GradleCommand
    ) `
    -WorkingDirectory $MobilePath `
    -NoNewWindow `
    -Wait `
    -PassThru

if ($Process.ExitCode -ne 0) {
    throw "T-048 Gradle verification failed with exit code $($Process.ExitCode)"
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
Write-Host "T048_NATURAL_TYPOGRAPHY_BUILD_PASS" `
    -ForegroundColor Green
Write-Host "Customer APK: $CustomerApk"
Write-Host "Technician APK: $TechnicianApk"
