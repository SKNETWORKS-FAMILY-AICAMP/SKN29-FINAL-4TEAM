param(
    [string]$RepoPath = "",
    [string]$DeviceSerial = "",
    [switch]$ResetAppData,
    [switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Write-Step([string]$Message) {
    Write-Host "`n== $Message ==" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "[PASS] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Stop-WithError([string]$Message) {
    Write-Host "[FAIL] $Message" -ForegroundColor Red
    exit 1
}

function Read-LocalProperties([string]$Path) {
    $result = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $result
    }

    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }

        $parts = $trimmed.Split(@("="), 2, [System.StringSplitOptions]::None)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Replace("\:", ":").Replace("\\", "\")
        $result[$key] = $value
    }
    return $result
}

function Get-PropertyValue(
    [hashtable]$Properties,
    [string]$Name,
    [string]$DefaultValue
) {
    if ($Properties.ContainsKey($Name)) {
        return [string]$Properties[$Name]
    }
    return $DefaultValue
}

function Find-Adb([hashtable]$Properties) {
    $command = Get-Command adb.exe -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }

    $sdkDir = Get-PropertyValue $Properties "sdk.dir" ""
    if ($sdkDir.Length -gt 0) {
        $candidate = Join-Path $sdkDir "platform-tools\adb.exe"
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    if ($env:LOCALAPPDATA) {
        $candidate = Join-Path $env:LOCALAPPDATA "Android\Sdk\platform-tools\adb.exe"
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    return $null
}

function Get-ConnectedDevices([string]$AdbPath) {
    $devices = @()
    foreach ($line in & $AdbPath devices) {
        if ($line -match '^\s*(\S+)\s+device\s*$') {
            $devices += $Matches[1]
        }
    }
    return $devices
}

function Invoke-Adb(
    [string]$AdbPath,
    [string]$Serial,
    [string[]]$Arguments,
    [switch]$AllowFailure
) {
    & $AdbPath -s $Serial @Arguments
    $exitCode = $LASTEXITCODE
    if (-not $AllowFailure -and $exitCode -ne 0) {
        Stop-WithError "ADB 명령 실패: $($Arguments -join ' ')"
    }
    return $exitCode
}

function Capture-Screenshot(
    [string]$AdbPath,
    [string]$Serial,
    [string]$OutputDirectory,
    [string]$FileName
) {
    $devicePath = "/sdcard/watercare_$FileName"
    Invoke-Adb $AdbPath $Serial @("shell", "screencap", "-p", $devicePath) | Out-Null
    Invoke-Adb $AdbPath $Serial @("pull", $devicePath, (Join-Path $OutputDirectory $FileName)) | Out-Null
    Invoke-Adb $AdbPath $Serial @("shell", "rm", $devicePath) -AllowFailure | Out-Null

    $localPath = Join-Path $OutputDirectory $FileName
    if (-not (Test-Path -LiteralPath $localPath)) {
        Stop-WithError "화면 캡처 파일을 만들지 못했습니다: $localPath"
    }
    Write-Ok "화면 캡처: $localPath"
}

function Read-StepResult([string]$DefaultValue = "PASS") {
    $inputValue = (Read-Host "결과 입력 [PASS/FAIL/SKIP] (기본 $DefaultValue)").Trim().ToUpperInvariant()
    if ([string]::IsNullOrWhiteSpace($inputValue)) {
        return $DefaultValue
    }
    if ($inputValue -notin @("PASS", "FAIL", "SKIP")) {
        Write-Warn "지원하지 않는 값이므로 FAIL로 기록합니다: $inputValue"
        return "FAIL"
    }
    return $inputValue
}

if ([string]::IsNullOrWhiteSpace($RepoPath)) {
    $RepoPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
} else {
    $RepoPath = [System.IO.Path]::GetFullPath($RepoPath)
}

$MobilePath = Join-Path $RepoPath "mobile"
$LocalPropertiesPath = Join-Path $MobilePath "local.properties"
$GradlePath = Join-Path $MobilePath "gradlew.bat"
$ApkPath = Join-Path $MobilePath "customer-app\build\outputs\apk\debug\customer-app-debug.apk"
$PackageName = "com.skn29.watercare.customer"
$LaunchActivity = "$PackageName/.MainActivity"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$EvidenceRoot = Join-Path $MobilePath "build\reports\week4-manual-flow-evidence\$timestamp"
$ScreenshotDirectory = Join-Path $EvidenceRoot "screenshots"
$LogDirectory = Join-Path $EvidenceRoot "logs"
$ResultMarkdown = Join-Path $EvidenceRoot "2026-08-04_고객_실연동_수동검증_결과.md"

Write-Step "저장소와 브랜치 확인"
if (-not (Test-Path -LiteralPath (Join-Path $RepoPath ".git"))) {
    Stop-WithError "Git 저장소를 찾을 수 없습니다: $RepoPath"
}
$branch = (& git -C $RepoPath branch --show-current).Trim()
if ($branch -ne "jeonghyun") {
    Stop-WithError "현재 브랜치가 jeonghyun이 아닙니다: $branch"
}
Write-Ok "jeonghyun 브랜치 확인"

Write-Step "Runtime 설정 확인"
if (-not (Test-Path -LiteralPath $LocalPropertiesPath)) {
    Stop-WithError "mobile/local.properties가 없습니다."
}
$properties = Read-LocalProperties $LocalPropertiesPath
$baseUrl = Get-PropertyValue $properties "BACKEND_BASE_URL" "http://127.0.0.1:8000/"
$careMode = (Get-PropertyValue $properties "CUSTOMER_CARE_MODE" "REMOTE").Trim().ToUpperInvariant()
$demoSubscriptionId = (Get-PropertyValue $properties "DEMO_SUBSCRIPTION_ID" "").Trim()
$showDeveloperTools = (Get-PropertyValue $properties "SHOW_DEVELOPER_TOOLS" "false").Trim().ToLowerInvariant()

if ($careMode -ne "REMOTE") {
    Stop-WithError "실연동 수동 검증은 CUSTOMER_CARE_MODE=REMOTE에서만 진행합니다: $careMode"
}
if ($showDeveloperTools -eq "true") {
    Stop-WithError "발표 검증에서는 SHOW_DEVELOPER_TOOLS=false여야 합니다."
}
$parsedGuid = [Guid]::Empty
if (-not [Guid]::TryParse($demoSubscriptionId, [ref]$parsedGuid)) {
    Stop-WithError "유효한 DEMO_SUBSCRIPTION_ID가 필요합니다."
}
try {
    $baseUri = [Uri]$baseUrl
} catch {
    Stop-WithError "BACKEND_BASE_URL 형식이 올바르지 않습니다: $baseUrl"
}
Write-Ok "데이터 모드: REMOTE"
Write-Ok "Backend URL: $baseUrl"
Write-Ok "Demo 구독 UUID 형식 확인"

Write-Step "Backend Health 확인"
$healthBuilder = [UriBuilder]$baseUri
if ($healthBuilder.Host -eq "10.0.2.2") {
    $healthBuilder.Host = "127.0.0.1"
}
$healthBuilder.Path = "/health"
$healthBuilder.Query = ""
$healthUrl = $healthBuilder.Uri.AbsoluteUri
try {
    $healthResponse = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5
    Write-Ok "GET $healthUrl -> $($healthResponse.StatusCode)"
} catch {
    Stop-WithError "Backend Health 확인 실패: $healthUrl"
}

Write-Step "APK 빌드"
if (-not $SkipBuild) {
    if (-not (Test-Path -LiteralPath $GradlePath)) {
        Stop-WithError "Gradle Wrapper를 찾을 수 없습니다: $GradlePath"
    }
    Push-Location $MobilePath
    try {
        & $GradlePath :core:test :customer-app:testDebugUnitTest :customer-app:assembleDebug --no-daemon
        if ($LASTEXITCODE -ne 0) {
            Stop-WithError "Gradle 검증이 실패했습니다."
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Warn "SkipBuild가 지정되어 기존 APK를 사용합니다."
}
if (-not (Test-Path -LiteralPath $ApkPath)) {
    Stop-WithError "Debug APK가 없습니다: $ApkPath"
}
$apkHash = (Get-FileHash -LiteralPath $ApkPath -Algorithm SHA256).Hash
Write-Ok "APK SHA-256: $apkHash"

Write-Step "ADB 기기 준비"
$adbPath = Find-Adb $properties
if ($null -eq $adbPath) {
    Stop-WithError "adb.exe를 찾지 못했습니다."
}
$devices = @(Get-ConnectedDevices $adbPath)
if ($DeviceSerial.Length -gt 0) {
    if ($DeviceSerial -notin $devices) {
        Stop-WithError "지정한 기기가 연결되어 있지 않습니다: $DeviceSerial"
    }
    $selectedDevice = $DeviceSerial
} elseif ($devices.Count -eq 1) {
    $selectedDevice = $devices[0]
} elseif ($devices.Count -eq 0) {
    Stop-WithError "연결된 Android 기기가 없습니다."
} else {
    Stop-WithError "Android 기기가 여러 대입니다. -DeviceSerial 값을 지정하세요."
}
Write-Ok "선택 기기: $selectedDevice"

if ($baseUri.Host -in @("127.0.0.1", "localhost")) {
    Invoke-Adb $adbPath $selectedDevice @("reverse", "tcp:8000", "tcp:8000") | Out-Null
    Write-Ok "adb reverse tcp:8000 tcp:8000 적용"
}

# 설치 후 초기화 순서로 실행하여, 앱이 없는 단말에서 pm clear가 실패하는 문제를 방지한다.
Invoke-Adb $adbPath $selectedDevice @("install", "-r", $ApkPath) | Out-Null
Write-Ok "고객 앱 APK 설치"

if ($ResetAppData) {
    $packagePathOutput = & $adbPath -s $selectedDevice shell pm path $PackageName 2>$null
    if ($LASTEXITCODE -eq 0 -and ($packagePathOutput -join "`n") -match "package:") {
        Invoke-Adb $adbPath $selectedDevice @("shell", "pm", "clear", $PackageName) | Out-Null
        Write-Ok "고객 앱 데이터 초기화"
    } else {
        Write-Warn "앱 설치 여부를 확인하지 못해 데이터 초기화를 건너뜁니다."
    }
}

New-Item -ItemType Directory -Path $ScreenshotDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null

Invoke-Adb $adbPath $selectedDevice @("logcat", "-c") | Out-Null
Invoke-Adb $adbPath $selectedDevice @("shell", "am", "force-stop", $PackageName) -AllowFailure | Out-Null
Invoke-Adb $adbPath $selectedDevice @("shell", "am", "start", "-W", "-n", $LaunchActivity) | Out-Null
Write-Ok "고객 앱 실행"

$steps = @(
    [PSCustomObject]@{
        Number = 1
        Code = "demo_login"
        Title = "Demo 로그인"
        Instruction = "휴대전화에서 Demo 로그인을 실행하고 고객 화면으로 진입하세요. 로그인 실패 문구가 없어야 합니다."
    },
    [PSCustomObject]@{
        Number = 2
        Code = "customer_home"
        Title = "고객 홈 확인"
        Instruction = "고객 홈에서 Backend 연결 상태, REMOTE 데이터 출처, 개발자 도구 숨김을 확인하세요."
    },
    [PSCustomObject]@{
        Number = 3
        Code = "intake_input"
        Title = "증상 입력"
        Instruction = "문진을 시작하고 증상을 선택하거나 직접 입력하세요. 입력 내용과 제출 버튼 상태를 확인하세요."
    },
    [PSCustomObject]@{
        Number = 4
        Code = "inquiry_submit"
        Title = "실제 문의 제출"
        Instruction = "문의 제출을 실행하세요. 네트워크 성공 시 실제 문의번호 또는 처리 상태가 표시되어야 합니다."
    },
    [PSCustomObject]@{
        Number = 5
        Code = "inquiry_result"
        Title = "문의 결과와 동작 확인"
        Instruction = "문의 상태와 화면에 제공되는 다음 행동을 확인하세요. 지원되지 않는 기능이 성공한 것처럼 보이면 안 됩니다."
    },
    [PSCustomObject]@{
        Number = 6
        Code = "relaunch"
        Title = "앱 재실행"
        Instruction = "앱을 최근 앱에서 닫은 뒤 다시 실행하세요. 로그인과 주요 상태가 예상대로 유지되는지 확인하세요."
    }
)

$results = @()
foreach ($step in $steps) {
    Write-Step "$($step.Number). $($step.Title)"
    Write-Host $step.Instruction -ForegroundColor White
    Read-Host "단계 수행 후 Enter" | Out-Null

    $fileName = ('{0:D2}_{1}.png' -f $step.Number, $step.Code)
    Capture-Screenshot $adbPath $selectedDevice $ScreenshotDirectory $fileName
    $result = Read-StepResult
    $note = (Read-Host "메모 입력 (없으면 Enter)").Trim()
    $results += [PSCustomObject]@{
        Number = $step.Number
        Code = $step.Code
        Title = $step.Title
        Result = $result
        Note = $note
        Screenshot = "screenshots/$fileName"
    }
}

Write-Step "앱 로그와 단말 정보 저장"
$pidOutput = @(& $adbPath -s $selectedDevice shell pidof $PackageName)
$pidValue = ($pidOutput -join "").Trim()
if (-not [string]::IsNullOrWhiteSpace($pidValue)) {
    & $adbPath -s $selectedDevice logcat -d --pid=$pidValue | Out-File -LiteralPath (Join-Path $LogDirectory "watercare-logcat.txt") -Encoding utf8
} else {
    & $adbPath -s $selectedDevice logcat -d | Select-String "com.skn29.watercare.customer|WaterCare|FATAL EXCEPTION" |
        Out-File -LiteralPath (Join-Path $LogDirectory "watercare-logcat.txt") -Encoding utf8
}
& $adbPath -s $selectedDevice shell dumpsys package $PackageName |
    Out-File -LiteralPath (Join-Path $LogDirectory "package-dumpsys.txt") -Encoding utf8
& $adbPath -s $selectedDevice reverse --list |
    Out-File -LiteralPath (Join-Path $LogDirectory "adb-reverse.txt") -Encoding utf8
Write-Ok "로그 저장: $LogDirectory"

Write-Step "검증 결과 문서 생성"
$commit = (& git -C $RepoPath rev-parse --short HEAD).Trim()
$executedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"
$passCount = @($results | Where-Object Result -eq "PASS").Count
$failCount = @($results | Where-Object Result -eq "FAIL").Count
$skipCount = @($results | Where-Object Result -eq "SKIP").Count
$overallResult = if ($failCount -eq 0) { "PASS" } else { "FAIL" }

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# 고객 앱 실연동 수동 검증 결과")
$lines.Add("")
$lines.Add("- 검증 시각: $executedAt")
$lines.Add("- 브랜치: $branch")
$lines.Add("- Commit: $commit")
$lines.Add("- 단말: $selectedDevice")
$lines.Add("- 데이터 모드: $careMode")
$lines.Add("- Backend URL: $baseUrl")
$lines.Add("- APK SHA-256: $apkHash")
$lines.Add("- 전체 결과: **$overallResult**")
$lines.Add("- 집계: PASS $passCount / FAIL $failCount / SKIP $skipCount")
$lines.Add("")
$lines.Add("## 단계별 결과")
$lines.Add("")
$lines.Add("| 단계 | 검증 항목 | 결과 | 메모 | 증거 화면 |")
$lines.Add("| --- | --- | --- | --- | --- |")
foreach ($item in $results) {
    $safeNote = if ([string]::IsNullOrWhiteSpace($item.Note)) { "-" } else { $item.Note.Replace("|", "\\|") }
    $lines.Add("| $($item.Number) | $($item.Title) | $($item.Result) | $safeNote | [$($item.Code)]($($item.Screenshot)) |")
}
$lines.Add("")
$lines.Add("## 저장된 로그")
$lines.Add("")
$lines.Add('- `logs/watercare-logcat.txt`')
$lines.Add('- `logs/package-dumpsys.txt`')
$lines.Add('- `logs/adb-reverse.txt`')
$lines.Add("")
$lines.Add("## 판정 기준")
$lines.Add("")
$lines.Add("- 실제 Backend 성공 결과와 Fake 성공 결과를 혼동하지 않는다.")
$lines.Add("- 미지원 기능은 준비 중 또는 비활성 상태로 표현한다.")
$lines.Add("- 문의번호, 처리 상태, 다음 행동이 Backend 계약과 일치하는지 확인한다.")
$lines.Add("- FAIL 항목은 발표 전 재현 조건과 원인을 기록하고 수정 또는 Fallback 계획을 마련한다.")

[System.IO.File]::WriteAllLines(
    $ResultMarkdown,
    $lines,
    [System.Text.UTF8Encoding]::new($false)
)
Write-Ok "결과 문서: $ResultMarkdown"
Write-Host "`n증거 폴더: $EvidenceRoot" -ForegroundColor Magenta

if ($failCount -gt 0) {
    Write-Warn "FAIL 항목이 $failCount건 있습니다. 결과 문서를 확인하세요."
    exit 2
}
Write-Ok "고객 실연동 수동 검증 완료"
