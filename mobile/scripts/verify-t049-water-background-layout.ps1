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
$LoginPath = Join-Path $RepoPath (
    "mobile\customer-app\src\main\java\com\skn29\watercare\" +
    "customer\feature\auth\LoginScreen.kt"
)
$CustomerHomePath = Join-Path $RepoPath (
    "mobile\customer-app\src\main\java\com\skn29\watercare\" +
    "customer\feature\customer\home\CustomerHomeScreen.kt"
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

foreach ($ImagePath in @(
    $CustomerBackground
    $TechnicianBackground
)) {
    if (-not (Test-Path -LiteralPath $ImagePath)) {
        throw "Background image is missing: $ImagePath"
    }

    $Length = (Get-Item -LiteralPath $ImagePath).Length
    if ($Length -lt 50000) {
        throw "Background image is too small: $ImagePath ($Length bytes)"
    }
}

$Component = Get-Content `
    -LiteralPath $ComponentPath `
    -Raw `
    -Encoding UTF8
$Login = Get-Content `
    -LiteralPath $LoginPath `
    -Raw `
    -Encoding UTF8
$CustomerHome = Get-Content `
    -LiteralPath $CustomerHomePath `
    -Raw `
    -Encoding UTF8
$Technician = Get-Content `
    -LiteralPath $TechnicianPath `
    -Raw `
    -Encoding UTF8

foreach ($Marker in @(
    "@DrawableRes backgroundRes: Int? = null"
    "BoxWithConstraints"
    "ReferenceBackendStatusCard"
    "minLines = 2"
    "maxLines = 2"
    "ContentScale.Crop"
    "brush = borderBrush"
)) {
    if (-not $Component.Contains($Marker)) {
        throw "Component marker is missing: $Marker"
    }
}

foreach ($Marker in @(
    "R.drawable.water_background_customer"
    "R.drawable.mascot_customer"
    "ReferenceBackendStatusCard"
)) {
    if (-not $Login.Contains($Marker)) {
        throw "Customer login marker is missing: $Marker"
    }
}

foreach ($Marker in @(
    "R.drawable.water_background_customer"
    "R.drawable.mascot_customer"
)) {
    if (-not $CustomerHome.Contains($Marker)) {
        throw "Customer home marker is missing: $Marker"
    }
}

if (-not $Technician.Contains(
    "R.drawable.water_background_technician"
)) {
    throw "Technician water background marker is missing."
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
    throw "T-049 Gradle verification failed with exit code $($Process.ExitCode)"
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
Write-Host "T049_WATER_BACKGROUND_LAYOUT_BUILD_PASS" `
    -ForegroundColor Green
Write-Host "Customer APK: $CustomerApk"
Write-Host "Technician APK: $TechnicianApk"
