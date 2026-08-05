param(
    [string]$RepoPath = "C:\skn29\WaterCare",
    [string]$DeviceSerial = "",
    [string]$AdbPath = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section {
    param([Parameter(Mandatory)][string]$Text)

    Write-Host ""
    Write-Host "== $Text ==" -ForegroundColor Cyan
}

function Require-LastExitCode {
    param([Parameter(Mandatory)][string]$Operation)

    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE"
    }
}

$RepoPath = [IO.Path]::GetFullPath($RepoPath)
$MobilePath = Join-Path $RepoPath "mobile"
$Gradle = Join-Path $MobilePath "gradlew.bat"
$Apk = Join-Path $MobilePath `
    "technician-app\build\outputs\apk\debug\technician-app-debug.apk"
$PackageName = "com.skn29.watercare.technician"
$ActivityName = "$PackageName/.MainActivity"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ReportDir = Join-Path $MobilePath `
    "build\reports\technician-t042-smoke\$Timestamp"
$LogPath = Join-Path $ReportDir "technician-logcat.txt"
$ScreenshotPath = Join-Path $ReportDir "technician-startup.png"
$ReportPath = Join-Path $ReportDir "smoke-report.txt"
$RemoteScreenshot = "/sdcard/watercare_t042_smoke.png"

Write-Section "Repository verification"

if (-not (Test-Path -LiteralPath (Join-Path $RepoPath ".git"))) {
    throw "Git repository not found: $RepoPath"
}
if (-not (Test-Path -LiteralPath $Gradle)) {
    throw "Gradle wrapper not found: $Gradle"
}
if (-not (Test-Path -LiteralPath $AdbPath)) {
    throw "adb not found: $AdbPath"
}

$Branch = (& git -C $RepoPath branch --show-current).Trim()
if ($Branch -ne "jeonghyun") {
    throw "Current branch must be jeonghyun. Current: $Branch"
}

$Commit = (& git -C $RepoPath rev-parse --short HEAD).Trim()
New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null

Write-Section "Backend health"

$Health = Invoke-WebRequest `
    -Uri "http://127.0.0.1:8000/health" `
    -UseBasicParsing `
    -TimeoutSec 5

if ($Health.StatusCode -ne 200) {
    throw "Backend health failed: HTTP $($Health.StatusCode)"
}

Write-Host "Backend /health: HTTP 200" -ForegroundColor Green

Write-Section "Technician tests and APK build"

Push-Location $MobilePath
try {
    & $Gradle `
        ":technician-app:testDebugUnitTest" `
        ":technician-app:assembleDebug" `
        "--no-daemon"

    Require-LastExitCode "Technician test/build"
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $Apk)) {
    throw "Technician APK not found: $Apk"
}

$ApkHash = (
    Get-FileHash `
        -Algorithm SHA256 `
        -LiteralPath $Apk
).Hash

Write-Section "ADB device selection"

$DeviceLines = @(
    & $AdbPath devices |
        Select-Object -Skip 1 |
        Where-Object {
            $_ -match "^\S+\s+device(?:\s|$)"
        }
)

if ([string]::IsNullOrWhiteSpace($DeviceSerial)) {
    if ($DeviceLines.Count -ne 1) {
        throw "Exactly one authorized Android device is required. Found: $($DeviceLines.Count)"
    }

    $DeviceSerial = ($DeviceLines[0] -split "\s+")[0]
}
else {
    $MatchedDevice = @(
        $DeviceLines |
            Where-Object {
                $_ -match "^$([regex]::Escape($DeviceSerial))\s+device(?:\s|$)"
            }
    )

    if ($MatchedDevice.Count -ne 1) {
        throw "Device is not in adb device state: $DeviceSerial"
    }
}

Write-Host "Device: $DeviceSerial" -ForegroundColor Green

Write-Section "ADB reverse"

& $AdbPath -s $DeviceSerial reverse --remove tcp:8000 2>$null |
    Out-Null

& $AdbPath -s $DeviceSerial reverse tcp:8000 tcp:8000 |
    Out-Null

Require-LastExitCode "adb reverse"

$ReverseList = @(& $AdbPath -s $DeviceSerial reverse --list)
if (-not ($ReverseList -match "tcp:8000\s+tcp:8000")) {
    throw "tcp:8000 reverse mapping was not confirmed."
}

Write-Host "ADB reverse tcp:8000: PASS" -ForegroundColor Green

Write-Section "Install and launch technician app"

$InstallOutput = @(
    & $AdbPath -s $DeviceSerial install -r $Apk 2>&1
)
if ($LASTEXITCODE -ne 0 -or -not ($InstallOutput -match "^Success$")) {
    $InstallOutput | ForEach-Object { Write-Host $_ }
    throw "Technician APK install failed."
}

$ClearOutput = @(
    & $AdbPath -s $DeviceSerial shell pm clear $PackageName 2>&1
)
if ($LASTEXITCODE -ne 0 -or -not ($ClearOutput -match "^Success$")) {
    $ClearOutput | ForEach-Object { Write-Host $_ }
    throw "Technician app data clear failed."
}

& $AdbPath -s $DeviceSerial logcat -c
Require-LastExitCode "logcat clear"

$LaunchOutput = @(
    & $AdbPath -s $DeviceSerial shell am start -W `
        -n $ActivityName 2>&1
)
if ($LASTEXITCODE -ne 0 -or -not ($LaunchOutput -match "Status:\s+ok")) {
    $LaunchOutput | ForEach-Object { Write-Host $_ }
    throw "Technician app launch failed."
}

Start-Sleep -Seconds 4

Write-Section "Health request log verification"

$Logcat = @(& $AdbPath -s $DeviceSerial logcat -d)
$Logcat | Set-Content -LiteralPath $LogPath -Encoding UTF8

$RequestLine = $Logcat |
    Select-String `
        -Pattern "--> GET http://127\.0\.0\.1:8000/health" |
    Select-Object -First 1

$ResponseLine = $Logcat |
    Select-String `
        -Pattern "<-- 200 .*http://127\.0\.0\.1:8000/health" |
    Select-Object -First 1

if (-not $RequestLine) {
    throw "Technician app health request was not found in logcat."
}
if (-not $ResponseLine) {
    throw "Technician app HTTP 200 health response was not found in logcat."
}

Write-Host $RequestLine.Line
Write-Host $ResponseLine.Line
Write-Host "Technician Backend health smoke: PASS" -ForegroundColor Green

Write-Section "Startup screenshot"

& $AdbPath -s $DeviceSerial shell screencap -p $RemoteScreenshot |
    Out-Null
Require-LastExitCode "device screenshot"

& $AdbPath -s $DeviceSerial pull `
    $RemoteScreenshot `
    $ScreenshotPath |
    Out-Null
Require-LastExitCode "screenshot pull"

& $AdbPath -s $DeviceSerial shell rm -f $RemoteScreenshot |
    Out-Null

$Screenshot = Get-Item -LiteralPath $ScreenshotPath
if ($Screenshot.Length -le 0) {
    throw "Startup screenshot is empty."
}

$StatusLines = @(& git -C $RepoPath status --short)

@"
WaterCare Technician T-042 Smoke Verification

Verified at: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

[Git]
Branch: $Branch
Commit: $Commit
Worktree entries: $($StatusLines.Count)

[Backend]
GET /health: HTTP 200

[Build]
Technician unit tests: PASS
Technician debug APK: PASS
APK: $Apk
APK SHA-256: $ApkHash

[Device]
Serial: $DeviceSerial
ADB reverse tcp:8000: PASS
APK install: PASS
App data clear: PASS
Activity launch: PASS

[Runtime]
Health request log: PASS
Health HTTP 200 log: PASS
Logcat: $LogPath
Startup screenshot: $ScreenshotPath

[Result]
TECHNICIAN_T042_SMOKE_PASS
"@ | Set-Content `
    -LiteralPath $ReportPath `
    -Encoding UTF8

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "TECHNICIAN_T042_SMOKE_PASS" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Report: $ReportPath"
Write-Host "APK SHA-256: $ApkHash"
