param(
    [string]$RepoPath = "C:\skn29\WaterCare"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Normalize-Lf {
    param([string]$Text)
    return $Text.Replace("`r`n", "`n").Replace("`r", "`n")
}

function Read-Utf8Lf {
    param([string]$Path)
    return Normalize-Lf (
        [IO.File]::ReadAllText(
            $Path,
            [Text.UTF8Encoding]::new($false)
        )
    )
}

function Write-Utf8Lf {
    param(
        [string]$Path,
        [string]$Content
    )
    [IO.File]::WriteAllText(
        $Path,
        (Normalize-Lf $Content),
        [Text.UTF8Encoding]::new($false)
    )
}

function Replace-ExactOnce {
    param(
        [string]$Content,
        [string]$Old,
        [string]$New,
        [string]$Label
    )

    $Old = Normalize-Lf $Old
    $New = Normalize-Lf $New

    $First = $Content.IndexOf($Old)
    if ($First -lt 0) {
        throw "$Label pattern was not found."
    }

    $Second = $Content.IndexOf($Old, $First + $Old.Length)
    if ($Second -ge 0) {
        throw "$Label pattern matched more than once."
    }

    return (
        $Content.Substring(0, $First) +
        $New +
        $Content.Substring($First + $Old.Length)
    )
}

function Replace-RegexOnce {
    param(
        [string]$Content,
        [string]$Pattern,
        [string]$Replacement,
        [string]$Label
    )

    $Regex = [regex]::new(
        $Pattern,
        [Text.RegularExpressions.RegexOptions]::Singleline
    )
    $Matches = $Regex.Matches($Content)

    if ($Matches.Count -ne 1) {
        throw (
            "$Label regex match count must be 1. " +
            "Actual: $($Matches.Count)"
        )
    }

    return $Regex.Replace(
        $Content,
        (Normalize-Lf $Replacement),
        1
    )
}

function Replace-AllExact {
    param(
        [string]$Content,
        [string]$Old,
        [string]$New,
        [int]$ExpectedCount,
        [string]$Label
    )

    $Old = Normalize-Lf $Old
    $New = Normalize-Lf $New
    $Count = ([regex]::Matches(
        $Content,
        [regex]::Escape($Old)
    )).Count

    if ($Count -ne $ExpectedCount) {
        throw (
            "$Label count must be $ExpectedCount. " +
            "Actual: $Count"
        )
    }

    return $Content.Replace($Old, $New)
}

$RepoPath = [IO.Path]::GetFullPath($RepoPath)

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
$GradlewPath = Join-Path $RepoPath "mobile\gradlew.bat"
$VerifyBuildPath = Join-Path $RepoPath "mobile\verify-build.bat"
$SmokePath = Join-Path $RepoPath "mobile\scripts\week4-mobile-smoke-test.ps1"

# ======================================================================
# 1. Reference dashboard: passive cards vs executable controls
# ======================================================================
$Reference = Read-Utf8Lf $ReferencePath

if (-not $Reference.Contains("import androidx.compose.foundation.LocalIndication")) {
    $Reference = Replace-ExactOnce `
        -Content $Reference `
        -Old @'
import androidx.compose.foundation.Image
'@ `
        -New @'
import androidx.compose.foundation.Image
import androidx.compose.foundation.LocalIndication
'@ `
        -Label "Reference LocalIndication import"
}

$Reference = Replace-AllExact `
    -Content $Reference `
    -Old 'indication = null,' `
    -New 'indication = LocalIndication.current,' `
    -ExpectedCount 4 `
    -Label "Reference press feedback"

$Reference = Replace-ExactOnce `
    -Content $Reference `
    -Old @'
data class ReferenceBottomItem(
    @DrawableRes val iconRes: Int,
    val label: String,
    val selected: Boolean = false,
    val onClick: () -> Unit = {},
)
'@ `
    -New @'
data class ReferenceBottomItem(
    @DrawableRes val iconRes: Int,
    val label: String,
    val selected: Boolean = false,
    val enabled: Boolean = true,
    val onClick: () -> Unit = {},
)
'@ `
    -Label "ReferenceBottomItem enabled state"

$Reference = Replace-ExactOnce `
    -Content $Reference `
    -Old @'
    onNotification: () -> Unit = {},
    onSupport: () -> Unit = {},
    content: @Composable ColumnScope.() -> Unit,
'@ `
    -New @'
    onNotification: () -> Unit = {},
    onSupport: () -> Unit = {},
    notificationEnabled: Boolean = false,
    supportEnabled: Boolean = false,
    content: @Composable ColumnScope.() -> Unit,
'@ `
    -Label "Dashboard header enabled parameters"

$Reference = Replace-ExactOnce `
    -Content $Reference `
    -Old @'
                    onNotification = onNotification,
                    onSupport = onSupport,
                )
'@ `
    -New @'
                    onNotification = onNotification,
                    onSupport = onSupport,
                    notificationEnabled = notificationEnabled,
                    supportEnabled = supportEnabled,
                )
'@ `
    -Label "Dashboard header enabled forwarding"

$Reference = Replace-ExactOnce `
    -Content $Reference `
    -Old @'
    onNotification: () -> Unit = {},
    onSupport: () -> Unit = {},
) {
'@ `
    -New @'
    onNotification: () -> Unit = {},
    onSupport: () -> Unit = {},
    notificationEnabled: Boolean = false,
    supportEnabled: Boolean = false,
) {
'@ `
    -Label "ReferenceDashboardHeader enabled parameters"

$Reference = Replace-ExactOnce `
    -Content $Reference `
    -Old @'
                icon = ReferenceHeaderIcon.Notification,
                palette = palette,
                onClick = onNotification,
            )
'@ `
    -New @'
                icon = ReferenceHeaderIcon.Notification,
                palette = palette,
                onClick = onNotification,
                enabled = notificationEnabled,
            )
'@ `
    -Label "Notification button enabled state"

$Reference = Replace-ExactOnce `
    -Content $Reference `
    -Old @'
                icon = ReferenceHeaderIcon.Support,
                palette = palette,
                onClick = onSupport,
            )
'@ `
    -New @'
                icon = ReferenceHeaderIcon.Support,
                palette = palette,
                onClick = onSupport,
                enabled = supportEnabled,
            )
'@ `
    -Label "Support button enabled state"

$Reference = Replace-ExactOnce `
    -Content $Reference `
    -Old @'
    secondaryActionLabel: String,
    onPrimaryAction: () -> Unit,
    onSecondaryAction: () -> Unit,
    timeline: List<String> = emptyList(),
'@ `
    -New @'
    secondaryActionLabel: String,
    onPrimaryAction: () -> Unit,
    onSecondaryAction: () -> Unit,
    primaryActionEnabled: Boolean = true,
    secondaryActionEnabled: Boolean = true,
    timeline: List<String> = emptyList(),
'@ `
    -Label "ReferenceDetailCard enabled parameters"

$Reference = Replace-ExactOnce `
    -Content $Reference `
    -Old @'
                accent = true,
                onClick = onPrimaryAction,
                modifier = Modifier.weight(1f),
'@ `
    -New @'
                accent = true,
                onClick = onPrimaryAction,
                enabled = primaryActionEnabled,
                modifier = Modifier.weight(1f),
'@ `
    -Label "Detail primary enabled forwarding"

$Reference = Replace-ExactOnce `
    -Content $Reference `
    -Old @'
                palette = palette,
                onClick = onSecondaryAction,
                modifier = Modifier.weight(1f),
'@ `
    -New @'
                palette = palette,
                onClick = onSecondaryAction,
                enabled = secondaryActionEnabled,
                modifier = Modifier.weight(1f),
'@ `
    -Label "Detail secondary enabled forwarding"

$Reference = Replace-ExactOnce `
    -Content $Reference `
    -Old @'
                        .clip(RoundedCornerShape(17.dp))
                        .clickable(
                            role = Role.Button,
'@ `
    -New @'
                        .clip(RoundedCornerShape(17.dp))
                        .graphicsLayer {
                            alpha = if (item.enabled) 1f else 0.38f
                        }
                        .clickable(
                            enabled = item.enabled,
                            role = Role.Button,
'@ `
    -Label "Bottom navigation disabled state"

$Reference = Replace-ExactOnce `
    -Content $Reference `
    -Old '            .heightIn(min = if (compact) 40.dp else 50.dp)' `
    -New '            .heightIn(min = if (compact) 44.dp else 56.dp)' `
    -Label "Reference button touch target"

$Reference = Replace-ExactOnce `
    -Content $Reference `
    -Old @'
        Text(
            text,
            color = when {
'@ `
    -New @'
        Text(
            text = if (enabled) "$text  ›" else text,
            color = when {
'@ `
    -Label "Reference button affordance arrow"

$Reference = Replace-RegexOnce `
    -Content $Reference `
    -Pattern (
        '(private fun ReferenceSquareIconButton\(\s*' +
        'icon: ReferenceHeaderIcon,\s*' +
        'palette: ReferenceDashboardPalette,\s*' +
        'onClick: \(\) -> Unit,\s*)\)'
    ) `
    -Replacement '${1}enabled: Boolean = true,
)' `
    -Label "Square icon enabled parameter"

$Reference = Replace-ExactOnce `
    -Content $Reference `
    -Old @'
            .clip(shape)
            .clickable(
                role = Role.Button,
'@ `
    -New @'
            .clip(shape)
            .graphicsLayer {
                alpha = if (enabled) 1f else 0.38f
            }
            .clickable(
                enabled = enabled,
                role = Role.Button,
'@ `
    -Label "Square icon disabled state"

$Reference = Replace-RegexOnce `
    -Content $Reference `
    -Pattern (
        '(private fun ReferenceActionTile\(.*?' +
        '\.then\(tagModifier\)\s*)' +
        '\.height\(118\.dp\)'
    ) `
    -Replacement '${1}.height(132.dp)' `
    -Label "Action tile height"

$Reference = Replace-RegexOnce `
    -Content $Reference `
    -Pattern (
        '(private fun ReferenceActionTile\(.*?' +
        'Text\(\s*)item\.label,(\s*modifier = Modifier\.padding\(top = 3\.dp\),)'
    ) `
    -Replacement '${1}text = if (item.enabled) {
                "${item.label}  ›"
            } else {
                item.label
            },${2}' `
    -Label "Action tile label affordance"

$Reference = Replace-RegexOnce `
    -Content $Reference `
    -Pattern (
        '(private fun ReferenceActionTile\(.*?' +
        'if \(item\.subtitle\.isNotBlank\(\)\) \{\s*' +
        'Text\(\s*)item\.subtitle,'
    ) `
    -Replacement '${1}text = if (item.enabled) {
                    item.subtitle
                } else {
                    "준비 중"
                },' `
    -Label "Action tile disabled hint"

Write-Utf8Lf -Path $ReferencePath -Content $Reference

# ======================================================================
# 2. Shared Liquid Glass: action feedback and affordance
# ======================================================================
$Liquid = Read-Utf8Lf $LiquidPath

if (-not $Liquid.Contains("import androidx.compose.foundation.LocalIndication")) {
    $Liquid = Replace-ExactOnce `
        -Content $Liquid `
        -Old @'
import androidx.compose.foundation.BorderStroke
'@ `
        -New @'
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.LocalIndication
'@ `
        -Label "Liquid LocalIndication import"
}

$Liquid = Replace-AllExact `
    -Content $Liquid `
    -Old 'indication = null,' `
    -New 'indication = LocalIndication.current,' `
    -ExpectedCount 2 `
    -Label "Liquid press feedback"

$Liquid = Replace-ExactOnce `
    -Content $Liquid `
    -Old '            .heightIn(min = if (compact) 40.dp else 54.dp)' `
    -New '            .heightIn(min = if (compact) 44.dp else 56.dp)' `
    -Label "Liquid button touch target"

$Liquid = Replace-ExactOnce `
    -Content $Liquid `
    -Old @'
        Text(
            text,
            color = when {
'@ `
    -New @'
        Text(
            text = if (enabled) "$text  ›" else text,
            color = when {
'@ `
    -Label "Liquid button affordance arrow"

$Liquid = Replace-RegexOnce `
    -Content $Liquid `
    -Pattern (
        '(fun LiquidGlassActionCard\(.*?' +
        'Text\(\s*)title,(\s*color = if \(enabled\) palette\.accent else Ink400,)'
    ) `
    -Replacement '${1}text = if (enabled) "$title  ›" else title,${2}' `
    -Label "Liquid action card affordance arrow"

Write-Utf8Lf -Path $LiquidPath -Content $Liquid

# ======================================================================
# 3. Customer home: no-op controls must not look executable
# ======================================================================
$HomeContent = Read-Utf8Lf $HomePath

foreach ($Label in @("제품", "관리", "알림", "마이")) {
    $Pattern = (
        '(ReferenceBottomItem\(\s*' +
        'iconRes = R\.drawable\.[^,]+,\s*' +
        'label = "' + [regex]::Escape($Label) + '",)' +
        '(?!\s*enabled = false,)'
    )
    $HomeContent = Replace-RegexOnce `
        -Content $HomeContent `
        -Pattern $Pattern `
        -Replacement '${1}
                enabled = false,' `
        -Label "Disable bottom navigation $Label"
}

$HomeContent = Replace-ExactOnce `
    -Content $HomeContent `
    -Old @'
                        label = "안심 케어",
                        subtitle = "안전 안내",
'@ `
    -New @'
                        label = "안내 미리보기",
                        subtitle = "Fixture 안내",
'@ `
    -Label "Fixture guidance wording"

$HomeContent = Replace-ExactOnce `
    -Content $HomeContent `
    -Old @'
                        label = "제품 정보",
                        subtitle = home.product.modelCode,
                        onClick = {},
'@ `
    -New @'
                        label = "제품 정보",
                        subtitle = "준비 중",
                        enabled = false,
                        onClick = {},
'@ `
    -Label "Disable product info action"

$HomeContent = Replace-ExactOnce `
    -Content $HomeContent `
    -Old @'
                primaryActionLabel = "제품 상세",
                secondaryActionLabel = "관리 가이드",
                onPrimaryAction = {},
                onSecondaryAction = {},
'@ `
    -New @'
                primaryActionLabel = "제품 상세 · 준비 중",
                secondaryActionLabel = "관리 가이드 · 준비 중",
                onPrimaryAction = {},
                onSecondaryAction = {},
                primaryActionEnabled = false,
                secondaryActionEnabled = false,
'@ `
    -Label "Disable detail no-op buttons"

foreach ($Item in @(
    @("고객센터", "1:1 문의"),
    @("자가 점검", "정수기 체크"),
    @("보증/혜택", "내 혜택"),
    @("이벤트", "진행 중")
)) {
    $Label = $Item[0]
    $Subtitle = $Item[1]
    $Old = @"
                        label = "$Label",
                        subtitle = "$Subtitle",
                        onClick = {},
"@
    $New = @"
                        label = "$Label",
                        subtitle = "준비 중",
                        enabled = false,
                        onClick = {},
"@
    $HomeContent = Replace-ExactOnce `
        -Content $HomeContent `
        -Old $Old `
        -New $New `
        -Label "Disable no-op action $Label"
}

$HomeContent = Replace-ExactOnce `
    -Content $HomeContent `
    -Old @'
                        text = "안내 다시 보기",
                        palette = palette,
'@ `
    -New @'
                        text = "안내 미리보기",
                        palette = palette,
                        accent = true,
'@ `
    -Label "Active inquiry guidance wording"

Write-Utf8Lf -Path $HomePath -Content $HomeContent

# ======================================================================
# 4. Guidance: contract allows consultation, but Mobile route does not
# ======================================================================
$Guidance = Read-Utf8Lf $GuidancePath

$Guidance = Replace-ExactOnce `
    -Content $Guidance `
    -Old @'
    if (consultationAction != null) {
        WorkflowActionButton(
            action = consultationAction,
            onClick = onRequestConsultation,
        )
    } else if (dangerous) {
'@ `
    -New @'
    if (consultationAction != null) {
        LiquidGlassButton(
            text = "상담 요청 · API 준비 중",
            onClick = {},
            enabled = false,
            modifier = Modifier
                .fillMaxWidth()
                .testTag("consultationUnavailable"),
        )
    } else if (dangerous) {
'@ `
    -Label "Disable unsupported consultation route"

Write-Utf8Lf -Path $GuidancePath -Content $Guidance

# ======================================================================
# 5. No-evidence fixture must never suggest guessed self action
# ======================================================================
$CareRepo = Read-Utf8Lf $CareRepoPath

$CareRepo = Replace-ExactOnce `
    -Content $CareRepo `
    -Old '        safeActions = listOf("임의 추정 안내"),' `
    -New '        safeActions = emptyList(),' `
    -Label "No-evidence safe action"

$CareRepo = Replace-RegexOnce `
    -Content $CareRepo `
    -Pattern (
        '(private fun noEvidenceGuidance\(inquiryId: String\).*?' +
        'nextAction = "상담 확인",\s*)' +
        'requiresConsultation = false,'
    ) `
    -Replacement '${1}requiresConsultation = true,' `
    -Label "No-evidence consultation requirement"

Write-Utf8Lf -Path $CareRepoPath -Content $CareRepo

# ======================================================================
# 6. Technician visit card: information card + explicit CTA button
# ======================================================================
$Technician = Read-Utf8Lf $TechnicianPath

$Technician = Replace-ExactOnce `
    -Content $Technician `
    -Old @'
    LiquidGlassPanel(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        danger = visit.risk ==
            TechnicianVisitRisk.DANGER,
'@ `
    -New @'
    LiquidGlassPanel(
        modifier = Modifier.fillMaxWidth(),
        danger = visit.risk ==
            TechnicianVisitRisk.DANGER,
'@ `
    -Label "Visit card passive container"

$Technician = Replace-ExactOnce `
    -Content $Technician `
    -Old @'
        Text(
            "${visit.visitCode} · ${visit.scenarioId} · 합성 Fixture",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
'@ `
    -New @'
        Text(
            "${visit.visitCode} · ${visit.scenarioId} · 합성 Fixture",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        LiquidGlassButton(
            text = "방문 상세 보기",
            onClick = onClick,
            accent = true,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}
'@ `
    -Label "Visit card explicit CTA"

Write-Utf8Lf -Path $TechnicianPath -Content $Technician

# ======================================================================
# 7. Gradle wrapper must propagate Java/Gradle failure exit code
# ======================================================================
$Gradlew = @'
@echo off
setlocal
set APP_HOME=%~dp0
set JAR=%APP_HOME%gradle\wrapper\gradle-wrapper.jar
if not exist "%JAR%" (
  echo gradle-wrapper.jar is missing. Run bootstrap-wrapper.bat first.
  endlocal & exit /b 1
)
if defined JAVA_HOME (
  set JAVA_EXE=%JAVA_HOME%\bin\java.exe
) else (
  set JAVA_EXE=java.exe
)
"%JAVA_EXE%" -classpath "%JAR%" org.gradle.wrapper.GradleWrapperMain %*
set EXIT_CODE=%ERRORLEVEL%
endlocal & exit /b %EXIT_CODE%
'@
Write-Utf8Lf -Path $GradlewPath -Content $Gradlew

# ======================================================================
# 8. Build verifier: unit tests + both APKs + actual artifact existence
# ======================================================================
$VerifyBuild = @'
@echo off
setlocal
cd /d "%~dp0"

call gradlew.bat :core:test :customer-app:testDebugUnitTest :technician-app:testDebugUnitTest :customer-app:assembleDebug :technician-app:assembleDebug --no-daemon
if errorlevel 1 (
  echo.
  echo [FAIL] Gradle test or APK build failed.
  endlocal & exit /b 1
)

set CUSTOMER_APK=%CD%\customer-app\build\outputs\apk\debug\customer-app-debug.apk
set TECHNICIAN_APK=%CD%\technician-app\build\outputs\apk\debug\technician-app-debug.apk

if not exist "%CUSTOMER_APK%" (
  echo [FAIL] Customer APK not found: %CUSTOMER_APK%
  endlocal & exit /b 1
)

if not exist "%TECHNICIAN_APK%" (
  echo [FAIL] Technician APK not found: %TECHNICIAN_APK%
  endlocal & exit /b 1
)

echo.
echo [PASS] Core tests
echo [PASS] Customer unit tests
echo [PASS] Technician unit tests
echo [PASS] Customer Debug APK
echo [PASS] Technician Debug APK
echo WaterCare mobile verification completed.
endlocal & exit /b 0
'@
Write-Utf8Lf -Path $VerifyBuildPath -Content $VerifyBuild

# ======================================================================
# 9. Smoke script: branch/commit configurable + technician verification
# ======================================================================
$Smoke = Read-Utf8Lf $SmokePath

$Smoke = Replace-ExactOnce `
    -Content $Smoke `
    -Old @'
    [switch]$RunConnectedTest,
    [string]$DeviceSerial = ""
)
'@ `
    -New @'
    [switch]$RunConnectedTest,
    [string]$DeviceSerial = "",
    [string]$ExpectedBranch = "jeonghyun",
    [string]$ExpectedCommit = ""
)
'@ `
    -Label "Smoke branch and commit parameters"

$Smoke = Replace-ExactOnce `
    -Content $Smoke `
    -Old @'
$ApkPath = Join-Path $MobilePath "customer-app\build\outputs\apk\debug\customer-app-debug.apk"
$ReportPath = Join-Path $MobilePath "build\reports\week4-mobile-smoke-test.txt"
'@ `
    -New @'
$ApkPath = Join-Path $MobilePath "customer-app\build\outputs\apk\debug\customer-app-debug.apk"
$TechnicianApkPath = Join-Path $MobilePath "technician-app\build\outputs\apk\debug\technician-app-debug.apk"
$ReportPath = Join-Path $MobilePath "build\reports\week4-mobile-smoke-test.txt"
'@ `
    -Label "Technician APK smoke path"

$Smoke = Replace-ExactOnce `
    -Content $Smoke `
    -Old @'
if ($branch -ne "jeonghyun") {
    Stop-WithError "현재 브랜치가 jeonghyun이 아닙니다: $branch"
}
Write-Ok "jeonghyun 브랜치 확인"
'@ `
    -New @'
if (
    -not [string]::IsNullOrWhiteSpace($ExpectedBranch) -and
    $branch -ne $ExpectedBranch
) {
    Stop-WithError "현재 브랜치가 예상 브랜치와 다릅니다. expected=$ExpectedBranch actual=$branch"
}

$fullCommit = (& git -C $RepoPath rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) {
    Stop-WithError "현재 Commit을 확인하지 못했습니다."
}

if (
    -not [string]::IsNullOrWhiteSpace($ExpectedCommit) -and
    -not $fullCommit.StartsWith($ExpectedCommit)
) {
    Stop-WithError "현재 Commit이 예상 Commit과 다릅니다. expected=$ExpectedCommit actual=$fullCommit"
}

Write-Ok "브랜치 확인: $branch"
Write-Ok "Commit 확인: $fullCommit"
'@ `
    -Label "Smoke dynamic branch validation"

$Smoke = Replace-ExactOnce `
    -Content $Smoke `
    -Old @'
        ":core:test",
        ":customer-app:testDebugUnitTest",
        ":customer-app:assembleDebug"
'@ `
    -New @'
        ":core:test",
        ":customer-app:testDebugUnitTest",
        ":technician-app:testDebugUnitTest",
        ":customer-app:assembleDebug",
        ":technician-app:assembleDebug"
'@ `
    -Label "Smoke technician tasks"

$Smoke = Replace-ExactOnce `
    -Content $Smoke `
    -Old @'
if (-not (Test-Path $ApkPath)) {
    Stop-WithError "Debug APK가 생성되지 않았습니다: $ApkPath"
}
$apkHash = (Get-FileHash -LiteralPath $ApkPath -Algorithm SHA256).Hash
Write-Ok "Debug APK 생성: $ApkPath"
Write-Ok "APK SHA-256: $apkHash"
'@ `
    -New @'
if (-not (Test-Path $ApkPath)) {
    Stop-WithError "고객 Debug APK가 생성되지 않았습니다: $ApkPath"
}
if (-not (Test-Path $TechnicianApkPath)) {
    Stop-WithError "방문기사 Debug APK가 생성되지 않았습니다: $TechnicianApkPath"
}

$apkHash = (Get-FileHash -LiteralPath $ApkPath -Algorithm SHA256).Hash
$technicianApkHash = (
    Get-FileHash -LiteralPath $TechnicianApkPath -Algorithm SHA256
).Hash

Write-Ok "고객 Debug APK 생성: $ApkPath"
Write-Ok "고객 APK SHA-256: $apkHash"
Write-Ok "방문기사 Debug APK 생성: $TechnicianApkPath"
Write-Ok "방문기사 APK SHA-256: $technicianApkHash"
'@ `
    -Label "Smoke both APK artifacts"

$Smoke = Replace-ExactOnce `
    -Content $Smoke `
    -Old @'
    "Core 단위 테스트: PASS",
    "고객 앱 단위 테스트: PASS",
    "고객 Debug APK: PASS",
    "APK SHA-256: $apkHash",
'@ `
    -New @'
    "Core 단위 테스트: PASS",
    "고객 앱 단위 테스트: PASS",
    "방문기사 앱 단위 테스트: PASS",
    "고객 Debug APK: PASS",
    "고객 APK SHA-256: $apkHash",
    "방문기사 Debug APK: PASS",
    "방문기사 APK SHA-256: $technicianApkHash",
'@ `
    -Label "Smoke report technician evidence"

Write-Utf8Lf -Path $SmokePath -Content $Smoke

Write-Host "T056_TRANSFORM_PASS" -ForegroundColor Green
