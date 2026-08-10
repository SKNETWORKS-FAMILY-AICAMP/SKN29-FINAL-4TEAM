param(
    [string]$RepoPath = "C:\skn29\WaterCare",
    [string]$DeviceSerial = "R3CT8076D7B",
    [string]$AdbPath = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section {
    param([Parameter(Mandatory)][string]$Text)

    Write-Host ""
    Write-Host "== $Text ==" -ForegroundColor Cyan
}

function Require-ExitCode {
    param(
        [Parameter(Mandatory)][string]$Operation,
        [Parameter(Mandatory)][int]$ExitCode
    )

    if ($ExitCode -ne 0) {
        throw "$Operation failed with exit code $ExitCode"
    }
}

function Invoke-Adb {
    param(
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$Operation
    )

    & $AdbPath -s $DeviceSerial @Arguments
    $ExitCode = $LASTEXITCODE

    Require-ExitCode -Operation $Operation -ExitCode $ExitCode
}

function Invoke-GradleVerification {
    param([Parameter(Mandatory)][string]$MobilePath)

    $GradleArguments = @(
        "/d"
        "/c"
        "gradlew.bat"
        ":core:test"
        ":customer-app:testDebugUnitTest"
        ":customer-app:assembleDebug"
        ":technician-app:testDebugUnitTest"
        ":technician-app:assembleDebug"
        "--no-daemon"
    )

    Push-Location $MobilePath
    try {
        & cmd.exe @GradleArguments
        $ExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    Require-ExitCode `
        -Operation "Gradle test and APK verification" `
        -ExitCode $ExitCode
}

function Wake-And-Dismiss-Keyguard {
    & $AdbPath -s $DeviceSerial shell input keyevent 224 |
        Out-Null

    & $AdbPath -s $DeviceSerial shell wm dismiss-keyguard |
        Out-Null

    & $AdbPath -s $DeviceSerial shell input keyevent 82 |
        Out-Null

    Start-Sleep -Seconds 1
}

function Wait-ForFocusedPackage {
    param([Parameter(Mandatory)][string]$PackageName)

    $LastFocusLines = @()

    for ($Attempt = 1; $Attempt -le 20; $Attempt++) {
        $WindowOutput = @(
            & $AdbPath -s $DeviceSerial shell dumpsys window 2>&1
        )
        $WindowExit = $LASTEXITCODE

        Require-ExitCode `
            -Operation "Read current window for $PackageName" `
            -ExitCode $WindowExit

        $LastFocusLines = @(
            $WindowOutput |
                Select-String "mCurrentFocus"
        )

        $KeyguardLines = @(
            $WindowOutput |
                Select-String `
                    "mShowingLockscreen=true|isStatusBarKeyguard=true|mDreamingLockscreen=true"
        )

        if (
            ($LastFocusLines -match [regex]::Escape($PackageName)) -and
            $KeyguardLines.Count -eq 0
        ) {
            Write-Host "Focused package: $PackageName" -ForegroundColor Green
            return
        }

        Start-Sleep -Milliseconds 500
    }

    $LastFocusLines |
        ForEach-Object { Write-Host $_ }

    throw "The target package did not become the unlocked current focus: $PackageName"
}

function Get-DisplayCandidates {
    $Candidates = New-Object System.Collections.Generic.List[string]
    $Candidates.Add("default")

    $DisplayOutput = @(
        & $AdbPath -s $DeviceSerial shell `
            dumpsys SurfaceFlinger --display-id 2>&1
    )
    $DisplayExit = $LASTEXITCODE

    Require-ExitCode `
        -Operation "Read SurfaceFlinger display IDs" `
        -ExitCode $DisplayExit

    foreach ($Line in $DisplayOutput) {
        $MatchesFound = [regex]::Matches(
            [string]$Line,
            "(?<![0-9])([0-9]{10,})(?![0-9])"
        )

        foreach ($Match in $MatchesFound) {
            $DisplayId = $Match.Groups[1].Value

            if (-not $Candidates.Contains($DisplayId)) {
                $Candidates.Add($DisplayId)
            }
        }
    }

    return $Candidates.ToArray()
}

function Capture-DisplayCandidates {
    param(
        [Parameter(Mandatory)][string]$PackageName,
        [Parameter(Mandatory)][string]$ExpectedText,
        [Parameter(Mandatory)][string]$SourcePath,
        [Parameter(Mandatory)][string]$ApkPath,
        [Parameter(Mandatory)][string]$HierarchyPath,
        [Parameter(Mandatory)][string]$RemotePrefix,
        [Parameter(Mandatory)][string[]]$OtherPackages,
        [Parameter(Mandatory)][string[]]$DisplayCandidates,
        [Parameter(Mandatory)][string]$CandidateDirectory
    )

    foreach ($OtherPackage in $OtherPackages) {
        Invoke-Adb `
            -Arguments @(
                "shell"
                "am"
                "force-stop"
                $OtherPackage
            ) `
            -Operation "Force-stop $OtherPackage"
    }

    Invoke-Adb `
        -Arguments @(
            "install"
            "-r"
            $ApkPath
        ) `
        -Operation "Install $PackageName"

    Invoke-Adb `
        -Arguments @(
            "shell"
            "pm"
            "clear"
            $PackageName
        ) `
        -Operation "Clear $PackageName data"

    Wake-And-Dismiss-Keyguard

    $LaunchOutput = @(
        & $AdbPath -s $DeviceSerial shell am start -S -W `
            -n "$PackageName/.MainActivity" 2>&1
    )
    $LaunchExit = $LASTEXITCODE

    Require-ExitCode `
        -Operation "Launch $PackageName" `
        -ExitCode $LaunchExit

    if (-not ($LaunchOutput -match "Status:\s+ok")) {
        $LaunchOutput |
            ForEach-Object { Write-Host $_ }

        throw "Activity launch status was not ok: $PackageName"
    }

    Wait-ForFocusedPackage -PackageName $PackageName
    Start-Sleep -Seconds 3

    $RemoteXml = "$RemotePrefix.xml"

    Invoke-Adb `
        -Arguments @(
            "shell"
            "uiautomator"
            "dump"
            "--compressed"
            $RemoteXml
        ) `
        -Operation "Dump UI hierarchy for $PackageName"

    Invoke-Adb `
        -Arguments @(
            "pull"
            $RemoteXml
            $HierarchyPath
        ) `
        -Operation "Pull UI hierarchy for $PackageName"

    $HierarchyFile = Get-Item -LiteralPath $HierarchyPath
    if ($HierarchyFile.Length -le 0) {
        throw "UI hierarchy is empty: $HierarchyPath"
    }

    if (-not (Test-Path -LiteralPath $SourcePath)) {
        throw "UI source file not found: $SourcePath"
    }

    $SourceContent = Get-Content `
        -LiteralPath $SourcePath `
        -Raw `
        -Encoding UTF8

    if ($SourceContent -notmatch [regex]::Escape($ExpectedText)) {
        throw "Expected source marker was not found for ${PackageName}: $ExpectedText"
    }

    Write-Host "Source marker and UI hierarchy evidence: PASS" `
        -ForegroundColor Green

    New-Item `
        -ItemType Directory `
        -Path $CandidateDirectory `
        -Force |
        Out-Null

    foreach ($Candidate in $DisplayCandidates) {
        $SafeCandidate = $Candidate -replace "[^0-9A-Za-z_-]", "_"
        $RemotePng = "${RemotePrefix}_${SafeCandidate}.png"
        $LocalPng = Join-Path $CandidateDirectory `
            "${SafeCandidate}.png"

        if ($Candidate -eq "default") {
            & $AdbPath -s $DeviceSerial shell screencap -p `
                $RemotePng
        }
        else {
            & $AdbPath -s $DeviceSerial shell screencap `
                -d $Candidate `
                -p $RemotePng
        }

        $CaptureExit = $LASTEXITCODE

        if ($CaptureExit -ne 0) {
            Write-Host "Display capture skipped: $Candidate" `
                -ForegroundColor Yellow
            continue
        }

        & $AdbPath -s $DeviceSerial pull `
            $RemotePng `
            $LocalPng

        $PullExit = $LASTEXITCODE

        if ($PullExit -ne 0) {
            Write-Host "Display pull skipped: $Candidate" `
                -ForegroundColor Yellow
            continue
        }

        & $AdbPath -s $DeviceSerial shell rm -f `
            $RemotePng |
            Out-Null

        if (
            (Test-Path -LiteralPath $LocalPng) -and
            (Get-Item -LiteralPath $LocalPng).Length -gt 0
        ) {
            Write-Host "Captured display candidate: $Candidate"
        }
    }

    Invoke-Adb `
        -Arguments @(
            "shell"
            "rm"
            "-f"
            $RemoteXml
        ) `
        -Operation "Remove temporary hierarchy for $PackageName"
}

function Select-DistinctDisplayEvidence {
    param(
        [Parameter(Mandatory)][string[]]$DisplayCandidates,
        [Parameter(Mandatory)][string]$CustomerCandidateDirectory,
        [Parameter(Mandatory)][string]$TechnicianCandidateDirectory,
        [Parameter(Mandatory)][string]$CustomerScreenshot,
        [Parameter(Mandatory)][string]$TechnicianScreenshot,
        [Parameter(Mandatory)][string]$HashReportPath
    )

    $HashLines = New-Object System.Collections.Generic.List[string]

    foreach ($Candidate in $DisplayCandidates) {
        $SafeCandidate = $Candidate -replace "[^0-9A-Za-z_-]", "_"

        $CustomerCandidate = Join-Path `
            $CustomerCandidateDirectory `
            "${SafeCandidate}.png"

        $TechnicianCandidate = Join-Path `
            $TechnicianCandidateDirectory `
            "${SafeCandidate}.png"

        if (
            -not (Test-Path -LiteralPath $CustomerCandidate) -or
            -not (Test-Path -LiteralPath $TechnicianCandidate)
        ) {
            continue
        }

        $CustomerHash = (
            Get-FileHash `
                -LiteralPath $CustomerCandidate `
                -Algorithm SHA256
        ).Hash

        $TechnicianHash = (
            Get-FileHash `
                -LiteralPath $TechnicianCandidate `
                -Algorithm SHA256
        ).Hash

        $HashLines.Add(
            "$Candidate customer=$CustomerHash technician=$TechnicianHash"
        )

        if ($CustomerHash -ne $TechnicianHash) {
            Copy-Item `
                -LiteralPath $CustomerCandidate `
                -Destination $CustomerScreenshot `
                -Force

            Copy-Item `
                -LiteralPath $TechnicianCandidate `
                -Destination $TechnicianScreenshot `
                -Force

            $HashLines |
                Set-Content `
                    -LiteralPath $HashReportPath `
                    -Encoding UTF8

            return $Candidate
        }
    }

    $HashLines |
        Set-Content `
            -LiteralPath $HashReportPath `
            -Encoding UTF8

    throw "No display candidate produced distinct customer and technician screenshots."
}

$RepoPath = [IO.Path]::GetFullPath($RepoPath)
$MobilePath = Join-Path $RepoPath "mobile"
$CustomerPackage = "com.skn29.watercare.customer"
$TechnicianPackage = "com.skn29.watercare.technician"

$CustomerExpectedText = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String(
        "6rOg6rCdIERlbW8g66Gc6re47J24"
    )
)

$TechnicianExpectedText = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String(
        "67Cp66y46riw7IKsIERlbW8g66Gc6re47J24"
    )
)

$CustomerApk = Join-Path $MobilePath `
    "customer-app\build\outputs\apk\debug\customer-app-debug.apk"
$TechnicianApk = Join-Path $MobilePath `
    "technician-app\build\outputs\apk\debug\technician-app-debug.apk"

$CustomerLoginSource = Join-Path $MobilePath `
    "customer-app\src\main\java\com\skn29\watercare\customer\feature\auth\LoginScreen.kt"
$TechnicianAppSource = Join-Path $MobilePath `
    "technician-app\src\main\java\com\skn29\watercare\technician\TechnicianApp.kt"

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$EvidenceDir = Join-Path $MobilePath `
    "build\reports\t044-mobile-liquid-glass-final\$Timestamp"

$CustomerScreenshot = Join-Path $EvidenceDir `
    "01_customer_login_liquid_glass.png"
$TechnicianScreenshot = Join-Path $EvidenceDir `
    "02_technician_login_liquid_glass.png"
$CustomerHierarchy = Join-Path $EvidenceDir `
    "01_customer_ui.xml"
$TechnicianHierarchy = Join-Path $EvidenceDir `
    "02_technician_ui.xml"
$CustomerCandidateDirectory = Join-Path $EvidenceDir `
    "customer-display-candidates"
$TechnicianCandidateDirectory = Join-Path $EvidenceDir `
    "technician-display-candidates"
$HashReportPath = Join-Path $EvidenceDir `
    "display-candidate-hashes.txt"
$ReportPath = Join-Path $EvidenceDir `
    "2026-08-05_T044_Liquid_Glass_Final_Verification.txt"

Write-Section "Repository verification"

if (-not (Test-Path -LiteralPath (Join-Path $RepoPath ".git"))) {
    throw "Git repository not found: $RepoPath"
}

if (-not (Test-Path -LiteralPath $AdbPath)) {
    throw "adb not found: $AdbPath"
}

$Branch = (& git -C $RepoPath branch --show-current).Trim()
if ($Branch -ne "jeonghyun") {
    throw "Current branch must be jeonghyun. Current: $Branch"
}

$ExpectedDirtyPaths = @(
    "mobile/core/src/test/java/com/skn29/watercare/core/ui/theme/WaterCareDesignTokenTest.kt"
    "mobile/scripts/verify-t044-mobile-liquid-glass.ps1"
    "mobile/docs/week4-post-presentation/2026-08-05_t044_liquid_glass_verification_fix.md"
)

$Status = @(
    & git -C $RepoPath status `
        --porcelain=v1 `
        --untracked-files=all
)

$UnexpectedStatus = @(
    $Status |
        Where-Object {
            $Line = $_

            -not (
                $ExpectedDirtyPaths |
                    Where-Object {
                        $Line.EndsWith($_) -or
                        $Line.EndsWith(($_ -replace "/", "\"))
                    }
            )
        }
)

if ($UnexpectedStatus.Count -gt 0) {
    $Status |
        ForEach-Object { Write-Host $_ }

    throw "Unrelated worktree changes were found."
}

Write-Host "Only approved verification changes are present: PASS" `
    -ForegroundColor Green

New-Item `
    -ItemType Directory `
    -Path $EvidenceDir `
    -Force |
    Out-Null

Write-Section "Strict Gradle verification"

Invoke-GradleVerification -MobilePath $MobilePath

Write-Host "All tests and APK builds: PASS" -ForegroundColor Green

if (-not (Test-Path -LiteralPath $CustomerApk)) {
    throw "Customer APK not found: $CustomerApk"
}

if (-not (Test-Path -LiteralPath $TechnicianApk)) {
    throw "Technician APK not found: $TechnicianApk"
}

Write-Section "Backend and ADB verification"

$Health = Invoke-WebRequest `
    -Uri "http://127.0.0.1:8000/health" `
    -UseBasicParsing `
    -TimeoutSec 5

if ($Health.StatusCode -ne 200) {
    throw "Backend /health failed: HTTP $($Health.StatusCode)"
}

$DeviceLines = @(
    & $AdbPath devices |
        Select-Object -Skip 1 |
        Where-Object {
            $_ -match "^$([regex]::Escape($DeviceSerial))\s+device(?:\s|$)"
        }
)

if ($DeviceLines.Count -ne 1) {
    throw "ADB device is not available: $DeviceSerial"
}

Invoke-Adb `
    -Arguments @(
        "reverse"
        "--remove-all"
    ) `
    -Operation "Remove previous adb reverse mappings"

Invoke-Adb `
    -Arguments @(
        "reverse"
        "tcp:8000"
        "tcp:8000"
    ) `
    -Operation "Create adb reverse tcp:8000"

Invoke-Adb `
    -Arguments @(
        "logcat"
        "-c"
    ) `
    -Operation "Clear logcat"

$DisplayCandidates = @(Get-DisplayCandidates)

Write-Host (
    "Display candidates: " +
    ($DisplayCandidates -join ", ")
) -ForegroundColor Green

$AppPackages = @(
    $CustomerPackage
    $TechnicianPackage
)

$CustomerEvidenceArguments = @{
    PackageName = $CustomerPackage
    ExpectedText = $CustomerExpectedText
    SourcePath = $CustomerLoginSource
    ApkPath = $CustomerApk
    HierarchyPath = $CustomerHierarchy
    RemotePrefix = "/sdcard/watercare_t044_customer_final"
    OtherPackages = $AppPackages
    DisplayCandidates = $DisplayCandidates
    CandidateDirectory = $CustomerCandidateDirectory
}

$TechnicianEvidenceArguments = @{
    PackageName = $TechnicianPackage
    ExpectedText = $TechnicianExpectedText
    SourcePath = $TechnicianAppSource
    ApkPath = $TechnicianApk
    HierarchyPath = $TechnicianHierarchy
    RemotePrefix = "/sdcard/watercare_t044_technician_final"
    OtherPackages = $AppPackages
    DisplayCandidates = $DisplayCandidates
    CandidateDirectory = $TechnicianCandidateDirectory
}

Write-Section "Customer design evidence"

Capture-DisplayCandidates @CustomerEvidenceArguments

Write-Section "Technician design evidence"

Capture-DisplayCandidates @TechnicianEvidenceArguments

Write-Section "Select active display evidence"

$SelectedDisplay = Select-DistinctDisplayEvidence `
    -DisplayCandidates $DisplayCandidates `
    -CustomerCandidateDirectory $CustomerCandidateDirectory `
    -TechnicianCandidateDirectory $TechnicianCandidateDirectory `
    -CustomerScreenshot $CustomerScreenshot `
    -TechnicianScreenshot $TechnicianScreenshot `
    -HashReportPath $HashReportPath

Write-Host "Selected display candidate: $SelectedDisplay" `
    -ForegroundColor Green

$CustomerHash = (
    Get-FileHash `
        -LiteralPath $CustomerScreenshot `
        -Algorithm SHA256
).Hash

$TechnicianHash = (
    Get-FileHash `
        -LiteralPath $TechnicianScreenshot `
        -Algorithm SHA256
).Hash

$FatalLogs = @(
    & $AdbPath -s $DeviceSerial logcat -d |
        Select-String "FATAL EXCEPTION|AndroidRuntime: FATAL"
)

if ($FatalLogs.Count -gt 0) {
    $FatalPath = Join-Path $EvidenceDir "fatal-logcat.txt"

    $FatalLogs |
        Set-Content `
            -LiteralPath $FatalPath `
            -Encoding UTF8

    throw "FATAL EXCEPTION was found. See: $FatalPath"
}

$Commit = (& git -C $RepoPath rev-parse --short HEAD).Trim()
$CustomerFile = Get-Item -LiteralPath $CustomerScreenshot
$TechnicianFile = Get-Item -LiteralPath $TechnicianScreenshot

@"
WaterCare T-044 Mobile Liquid Glass Final Verification

Verified at: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

[Git]
Branch: $Branch
Commit: $Commit
Only approved verification changes: PASS

[Design token]
Water50 #F2F9FB: PASS
Water100 #DCEEF3: PASS
Water500 #2E8BA3: PASS
Water700 #1B5A6B: PASS
Ink900 #12262B: PASS
GlassFill rendered alpha 0x8C: PASS
GlassFillStrong rendered alpha 0xB8: PASS
GlassBorder rendered alpha 0xA6: PASS
RadiusCard 24dp: PASS
RadiusControl 16dp: PASS
Caution #C08A2E: PASS
Danger #C0392B: PASS

[Build]
Core tests: PASS
Customer tests: PASS
Customer APK: PASS
Technician tests: PASS
Technician APK: PASS

[Device]
Backend /health HTTP 200: PASS
Selected display candidate: $SelectedDisplay
Customer focused package: PASS
Customer source marker: PASS
Customer UI hierarchy captured: PASS
Customer screenshot bytes: $($CustomerFile.Length)
Customer screenshot SHA-256: $CustomerHash

Technician focused package: PASS
Technician source marker: PASS
Technician UI hierarchy captured: PASS
Technician screenshot bytes: $($TechnicianFile.Length)
Technician screenshot SHA-256: $TechnicianHash

Distinct screenshots: PASS
FATAL EXCEPTION: NONE

[Result]
T044_MOBILE_LIQUID_GLASS_PASS
"@ | Set-Content `
    -LiteralPath $ReportPath `
    -Encoding UTF8

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "T044_MOBILE_LIQUID_GLASS_PASS" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Evidence: $EvidenceDir"
Write-Host "Report: $ReportPath"
Write-Host "Selected display: $SelectedDisplay"
Write-Host "Customer SHA-256: $CustomerHash"
Write-Host "Technician SHA-256: $TechnicianHash"
