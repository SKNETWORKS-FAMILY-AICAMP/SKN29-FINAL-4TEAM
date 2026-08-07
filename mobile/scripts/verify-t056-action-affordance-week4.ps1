param(
    [string]$RepoPath = "C:\skn29\WaterCare"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoPath = [IO.Path]::GetFullPath($RepoPath)
$MobilePath = Join-Path $RepoPath "mobile"

function Read-Text([string]$Path) {
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8
}

function Assert-Contains(
    [string]$Content,
    [string]$Marker,
    [string]$Area
) {
    if (-not $Content.Contains($Marker)) {
        throw "$Area marker missing: $Marker"
    }
}

$ReferencePath = Join-Path $RepoPath (
    "mobile\core\src\main\java\com\skn29\watercare\core\ui\" +
    "components\ReferenceDashboardComponents.kt"
)
$LiquidPath = Join-Path $RepoPath (
    "mobile\core\src\main\java\com\skn29\watercare\core\ui\" +
    "components\LiquidGlassComponents.kt"
)
$HomePath = Join-Path $RepoPath (
    "mobile\customer-app\src\main\java\com\skn29\watercare\" +
    "customer\feature\customer\home\CustomerHomeScreen.kt"
)
$GuidancePath = Join-Path $RepoPath (
    "mobile\customer-app\src\main\java\com\skn29\watercare\" +
    "customer\feature\customer\guidance\GuidanceScreen.kt"
)
$CareRepoPath = Join-Path $RepoPath (
    "mobile\core\src\main\java\com\skn29\watercare\core\" +
    "repository\CustomerCareRepository.kt"
)
$TechnicianPath = Join-Path $RepoPath (
    "mobile\technician-app\src\main\java\com\skn29\watercare\" +
    "technician\TechnicianApp.kt"
)
$GradlewPath = Join-Path $MobilePath "gradlew.bat"
$VerifyBuildPath = Join-Path $MobilePath "verify-build.bat"
$SmokePath = Join-Path $MobilePath "scripts\week4-mobile-smoke-test.ps1"

$Reference = Read-Text $ReferencePath
$Liquid = Read-Text $LiquidPath
$HomeContent = Read-Text $HomePath
$Guidance = Read-Text $GuidancePath
$CareRepo = Read-Text $CareRepoPath
$Technician = Read-Text $TechnicianPath
$Gradlew = Read-Text $GradlewPath
$VerifyBuild = Read-Text $VerifyBuildPath
$Smoke = Read-Text $SmokePath

foreach ($Marker in @(
    "import androidx.compose.foundation.LocalIndication"
    "indication = LocalIndication.current"
    'text = if (enabled) "$text  ›" else text'
    "val enabled: Boolean = true"
    "primaryActionEnabled: Boolean = true"
    ".height(132.dp)"
    '"준비 중"'
)) {
    Assert-Contains $Reference $Marker "Reference dashboard"
}

foreach ($Marker in @(
    "import androidx.compose.foundation.LocalIndication"
    "indication = LocalIndication.current"
    'text = if (enabled) "$text  ›" else text'
    'text = if (enabled) "$title  ›" else title'
)) {
    Assert-Contains $Liquid $Marker "Liquid Glass"
}

foreach ($Marker in @(
    'label = "안내 미리보기"'
    'subtitle = "Fixture 안내"'
    'primaryActionEnabled = false'
    'secondaryActionEnabled = false'
    'text = "안내 미리보기"'
)) {
    Assert-Contains $HomeContent $Marker "Customer home"
}

$DisabledCount = (
    [regex]::Matches(
        $HomeContent,
        'enabled = false,'
    )
).Count
if ($DisabledCount -lt 9) {
    throw "Customer home disabled placeholder count is too low: $DisabledCount"
}

Assert-Contains `
    $Guidance `
    'text = "상담 요청 · API 준비 중"' `
    "Guidance"

if ([regex]::IsMatch(
    $Guidance,
    'WorkflowActionButton\(\s*action = consultationAction'
)) {
    throw "Guidance still exposes active unsupported consultation action."
}

Assert-Contains `
    $CareRepo `
    'safeActions = emptyList()' `
    "No-evidence fixture"

if ($CareRepo.Contains('safeActions = listOf("임의 추정 안내")')) {
    throw "No-evidence fixture still contains guessed guidance."
}

foreach ($Marker in @(
    'text = "방문 상세 보기"'
    'accent = true'
)) {
    Assert-Contains $Technician $Marker "Technician visit card"
}

if ($Technician.Contains('.clickable(onClick = onClick),')) {
    throw "Technician visit card is still an ambiguous whole-card click target."
}

foreach ($Marker in @(
    "set EXIT_CODE=%ERRORLEVEL%"
    "endlocal & exit /b %EXIT_CODE%"
)) {
    Assert-Contains $Gradlew $Marker "Gradle wrapper"
}

foreach ($Marker in @(
    ":core:test"
    ":customer-app:testDebugUnitTest"
    ":technician-app:testDebugUnitTest"
    ":customer-app:assembleDebug"
    ":technician-app:assembleDebug"
    "Customer APK not found"
    "Technician APK not found"
)) {
    Assert-Contains $VerifyBuild $Marker "verify-build.bat"
}

foreach ($Marker in @(
    '[string]$ExpectedBranch = "jeonghyun"'
    '[string]$ExpectedCommit = ""'
    '":technician-app:testDebugUnitTest"'
    '":technician-app:assembleDebug"'
    "방문기사 APK SHA-256"
)) {
    Assert-Contains $Smoke $Marker "Week4 smoke script"
}

Write-Host "T056_SOURCE_CONTRACT_PASS" -ForegroundColor Green

Write-Host ""
Write-Host "Stopping Gradle daemons..."
& (Join-Path $MobilePath "gradlew.bat") --stop
if ($LASTEXITCODE -ne 0) {
    throw "gradlew --stop failed."
}

Write-Host ""
Write-Host "Running T-056 build verification..."
$Build = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList @(
        "/d"
        "/s"
        "/c"
        "call verify-build.bat"
    ) `
    -WorkingDirectory $MobilePath `
    -NoNewWindow `
    -Wait `
    -PassThru

if ($Build.ExitCode -ne 0) {
    throw "T-056 verify-build.bat failed with exit code $($Build.ExitCode)"
}

$CustomerApk = Join-Path $MobilePath `
    "customer-app\build\outputs\apk\debug\customer-app-debug.apk"
$TechnicianApk = Join-Path $MobilePath `
    "technician-app\build\outputs\apk\debug\technician-app-debug.apk"

if (-not (Test-Path -LiteralPath $CustomerApk)) {
    throw "Customer APK not found after verification."
}
if (-not (Test-Path -LiteralPath $TechnicianApk)) {
    throw "Technician APK not found after verification."
}

Write-Host ""
Write-Host "T056_ACTION_AFFORDANCE_WEEK4_BUILD_PASS" `
    -ForegroundColor Green
Write-Host "Customer APK: $CustomerApk"
Write-Host "Technician APK: $TechnicianApk"
