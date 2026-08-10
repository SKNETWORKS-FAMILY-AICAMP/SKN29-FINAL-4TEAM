param(
    [string]$RepoPath = "C:\skn29\WaterCare"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoPath = [IO.Path]::GetFullPath($RepoPath)
$MobilePath = Join-Path $RepoPath "mobile"

$LiquidPath = Join-Path $RepoPath (
    "mobile\core\src\main\java\com\skn29\watercare\core\ui\" +
    "components\LiquidGlassComponents.kt"
)
$SharedPath = Join-Path $RepoPath (
    "mobile\customer-app\src\main\java\com\skn29\watercare\" +
    "customer\feature\shared\ScreenComponents.kt"
)
$IntakePath = Join-Path $RepoPath (
    "mobile\customer-app\src\main\java\com\skn29\watercare\" +
    "customer\feature\customer\intake\SymptomIntakeScreen.kt"
)
$GuidancePath = Join-Path $RepoPath (
    "mobile\customer-app\src\main\java\com\skn29\watercare\" +
    "customer\feature\customer\guidance\GuidanceScreen.kt"
)
$TechnicianPath = Join-Path $RepoPath (
    "mobile\technician-app\src\main\java\com\skn29\watercare\" +
    "technician\TechnicianApp.kt"
)

$Files = @{
    "Liquid" = $LiquidPath
    "Customer shared" = $SharedPath
    "Intake" = $IntakePath
    "Guidance" = $GuidancePath
    "Technician" = $TechnicianPath
}

$Contents = @{}
foreach ($Entry in $Files.GetEnumerator()) {
    if (-not (Test-Path -LiteralPath $Entry.Value)) {
        throw "Required source file missing: $($Entry.Value)"
    }

    $Content = Get-Content `
        -LiteralPath $Entry.Value `
        -Raw `
        -Encoding UTF8

    if ([regex]::IsMatch(
        $Content,
        '(?<=[A-Za-z0-9_.])import\s+(?=[A-Za-z])'
    )) {
        throw "Joined import remains in $($Entry.Key)."
    }

    if ([regex]::IsMatch(
        $Content,
        '(?m)^import[^\r\n]*import\s+'
    )) {
        throw "Multiple imports remain on one line in $($Entry.Key)."
    }

    $Contents[$Entry.Key] = $Content
}

$Liquid = $Contents["Liquid"]
$Shared = $Contents["Customer shared"]
$Intake = $Contents["Intake"]
$Guidance = $Contents["Guidance"]
$Technician = $Contents["Technician"]

function Assert-Contains {
    param(
        [string]$Content,
        [string]$Marker,
        [string]$Area
    )

    if (-not $Content.Contains($Marker)) {
        throw "$Area marker missing: $Marker"
    }
}

function Assert-Regex {
    param(
        [string]$Content,
        [string]$Pattern,
        [string]$Area
    )

    if (-not [regex]::IsMatch(
        $Content,
        $Pattern,
        [Text.RegularExpressions.RegexOptions]::Singleline
    )) {
        throw "$Area regex marker missing: $Pattern"
    }
}

function Assert-ImportOnce {
    param(
        [string]$Content,
        [string]$Import,
        [string]$Area
    )

    $Count = (
        [regex]::Matches(
            $Content,
            "(?m)^" + [regex]::Escape($Import) + "\s*$"
        )
    ).Count

    if ($Count -ne 1) {
        throw "$Area import count must be 1: $Import. Actual: $Count"
    }
}

foreach ($Marker in @(
    "enum class LiquidGlassTone"
    "LiquidGlassToneProvider("
    "LiquidWaterDropPanelShape"
    "val primaryAlpha = if (enabled) 0.98f else 0.30f"
    "compact: Boolean = false"
    "LiquidWaterDropTileShape"
)) {
    Assert-Contains `
        -Content $Liquid `
        -Marker $Marker `
        -Area "Shared Liquid"
}

foreach ($Import in @(
    "import com.skn29.watercare.core.ui.components.LiquidGlassTone"
    "import com.skn29.watercare.core.ui.components.LiquidGlassToneProvider"
    "import com.skn29.watercare.core.ui.theme.WaterCaution"
)) {
    Assert-ImportOnce `
        -Content $Shared `
        -Import $Import `
        -Area "Customer shared"
}

foreach ($Marker in @(
    "private fun WaterCareScreenBody("
    "tone = LiquidGlassTone.CUSTOMER"
    'text = "뒤로"'
    'leadingIcon = "‹"'
    'text = "공식 문서 열기"'
)) {
    Assert-Contains `
        -Content $Shared `
        -Marker $Marker `
        -Area "Customer shared"
}

Assert-Regex `
    -Content $Shared `
    -Pattern (
        'text = "공식 문서 열기".*?' +
        'onClick = \{ uriHandler\.openUri\(officialUrl\) \}.*?' +
        'accent = true'
    ) `
    -Area "Official document primary action"

foreach ($Import in @(
    "import androidx.compose.ui.Modifier"
    "import androidx.compose.ui.graphics.Color"
    "import com.skn29.watercare.customer.BuildConfig"
    "import com.skn29.watercare.customer.R"
    "import com.skn29.watercare.customer.common.VmFactory"
)) {
    Assert-ImportOnce `
        -Content $Intake `
        -Import $Import `
        -Area "Intake"
}

foreach ($Marker in @(
    "if (BuildConfig.SHOW_DEVELOPER_TOOLS)"
    "selectedContainerColor = Water700.copy(alpha = 0.94f)"
    "selectedLabelColor = Color.White"
    "focusedBorderColor = Water700"
    'else -> "안내 결과 확인"'
    'testTag("submitIntake")'
)) {
    Assert-Contains `
        -Content $Intake `
        -Marker $Marker `
        -Area "Intake"
}

Assert-Regex `
    -Content $Intake `
    -Pattern (
        'text = when \{.*?' +
        'else -> "안내 결과 확인".*?' +
        'accent = true.*?' +
        'testTag\("submitIntake"\)'
    ) `
    -Area "Intake primary submit action"

Assert-Contains `
    -Content $Guidance `
    -Marker 'text = "근거 다시 확인"' `
    -Area "Guidance"

Assert-Regex `
    -Content $Guidance `
    -Pattern (
        'text = "근거 다시 확인".*?' +
        'onClick = onRetry.*?' +
        'accent = true'
    ) `
    -Area "Guidance retry primary action"

foreach ($Import in @(
    "import com.skn29.watercare.core.ui.components.LiquidGlassTone"
    "import com.skn29.watercare.core.ui.components.LiquidGlassToneProvider"
    "import com.skn29.watercare.core.ui.components.LoadingBlock"
)) {
    Assert-ImportOnce `
        -Content $Technician `
        -Import $Import `
        -Area "Technician"
}

foreach ($Marker in @(
    "private fun TechnicianAppContent()"
    "tone = LiquidGlassTone.TECHNICIAN"
    'text = "새로고침"'
    'leadingIcon = "↻"'
    'text = "방문 목록으로"'
)) {
    Assert-Contains `
        -Content $Technician `
        -Marker $Marker `
        -Area "Technician"
}

Assert-Regex `
    -Content $Technician `
    -Pattern (
        'text = "다시 확인".*?' +
        'onClick = onRetryBackend.*?' +
        'accent = true'
    ) `
    -Area "Technician backend retry"

Assert-Regex `
    -Content $Technician `
    -Pattern (
        'text = "방문 목록으로".*?' +
        'onClick = onBack.*?' +
        'accent = true'
    ) `
    -Area "Technician report back action"

Write-Host "T055_FIX3_SOURCE_AND_IMPORTS_PASS" `
    -ForegroundColor Green

Write-Host ""
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
    throw "T-055 FIX3 clean failed with exit code $($Clean.ExitCode)"
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
    throw "T-055 FIX3 Gradle build failed with exit code $($Build.ExitCode)"
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
Write-Host "T055_FIX3_ALL_SCREENS_TONE_USABILITY_BUILD_PASS" `
    -ForegroundColor Green
Write-Host "Customer APK: $CustomerApk"
Write-Host "Technician APK: $TechnicianApk"
