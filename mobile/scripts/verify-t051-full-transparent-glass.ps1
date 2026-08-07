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
$CustomerLoginPath = Join-Path $RepoPath (
    "mobile\customer-app\src\main\java\com\skn29\watercare\" +
    "customer\feature\auth\LoginScreen.kt"
)
$TechnicianPath = Join-Path $RepoPath (
    "mobile\technician-app\src\main\java\com\skn29\watercare\" +
    "technician\TechnicianReferenceDashboard.kt"
)
$CustomerBackground = Join-Path $RepoPath (
    "mobile\customer-app\src\main\res\drawable-nodpi\" +
    "water_background_customer.png"
)
$TechnicianBackground = Join-Path $RepoPath (
    "mobile\technician-app\src\main\res\drawable-nodpi\" +
    "water_background_technician.png"
)

$Component = Get-Content `
    -LiteralPath $ComponentPath `
    -Raw `
    -Encoding UTF8
$CustomerLogin = Get-Content `
    -LiteralPath $CustomerLoginPath `
    -Raw `
    -Encoding UTF8
$Technician = Get-Content `
    -LiteralPath $TechnicianPath `
    -Raw `
    -Encoding UTF8

foreach ($Marker in @(
    "val surfaceHighlight = if (strong) 0.045f else 0.018f"
    "val accentPrimaryAlpha = if (enabled) 0.76f else 0.20f"
    "accent -> Color.White"
    "accent = Color(0xFF248CFF)"
    "accent = Color(0xFF0FB9AA)"
    "elevation = if (danger) 4.dp else 0.dp"
)) {
    if (-not $Component.Contains($Marker)) {
        throw "T-051 component marker is missing: $Marker"
    }
}

if (-not $CustomerLogin.Contains("accent = true")) {
    throw "Customer primary button accent marker is missing."
}
if (-not $CustomerLogin.Contains("accent = false")) {
    throw "Customer secondary button transparent marker is missing."
}
if (-not $Technician.Contains("accent = true")) {
    throw "Technician primary button accent marker is missing."
}
if (-not $Technician.Contains("accent = false")) {
    throw "Technician secondary button transparent marker is missing."
}

foreach ($ImagePath in @(
    $CustomerBackground
    $TechnicianBackground
)) {
    if (-not (Test-Path -LiteralPath $ImagePath)) {
        throw "Water background is missing: $ImagePath"
    }

    $Length = (Get-Item -LiteralPath $ImagePath).Length
    if ($Length -lt 300000) {
        throw "Water background is too small: $ImagePath ($Length bytes)"
    }
}

Write-Host "Stopping existing Gradle daemons..."
& (Join-Path $MobilePath "gradlew.bat") --stop
if ($LASTEXITCODE -ne 0) {
    throw "gradlew --stop failed with exit code $LASTEXITCODE"
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
    throw "T-051 clean failed with exit code $($Clean.ExitCode)"
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
    throw "T-051 Gradle build failed with exit code $($Build.ExitCode)"
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
Write-Host "T051_FULL_TRANSPARENT_GLASS_BUILD_PASS" `
    -ForegroundColor Green
Write-Host "Customer APK: $CustomerApk"
Write-Host "Technician APK: $TechnicianApk"
