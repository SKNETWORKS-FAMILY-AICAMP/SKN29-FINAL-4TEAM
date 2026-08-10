param(
    [string]$RepoPath = "",
    [switch]$BuildOnly,
    [switch]$Install,
    [switch]$ResetAppData,
    [switch]$RunConnectedTest,
    [string]$DeviceSerial = "",
    [string]$ExpectedBranch = "jeonghyun",
    [string]$ExpectedCommit = ""
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
    if (-not (Test-Path $Path)) {
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

function Test-Uuid([string]$Value) {
    $parsed = [Guid]::Empty
    return [Guid]::TryParse($Value, [ref]$parsed)
}

function Find-Adb([hashtable]$Properties) {
    $command = Get-Command adb.exe -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }

    $sdkDir = Get-PropertyValue $Properties "sdk.dir" ""
    if ($sdkDir.Length -gt 0) {
        $candidate = Join-Path $sdkDir "platform-tools\adb.exe"
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    if ($env:LOCALAPPDATA) {
        $candidate = Join-Path $env:LOCALAPPDATA "Android\Sdk\platform-tools\adb.exe"
        if (Test-Path $candidate) {
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

function Mask-Value([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return "미설정"
    }
    if ($Value.Length -le 8) {
        return "********"
    }
    return $Value.Substring(0, 8) + "-****-****-****-************"
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
$TechnicianApkPath = Join-Path $MobilePath "technician-app\build\outputs\apk\debug\technician-app-debug.apk"
$ReportPath = Join-Path $MobilePath "build\reports\week4-mobile-smoke-test.txt"
$PackageName = "com.skn29.watercare.customer"
$LaunchActivity = "$PackageName/.MainActivity"

Write-Step "저장소 및 브랜치 확인"
if (-not (Test-Path (Join-Path $RepoPath ".git"))) {
    Stop-WithError "Git 저장소를 찾을 수 없습니다: $RepoPath"
}
if (-not (Test-Path $GradlePath)) {
    Stop-WithError "Gradle Wrapper를 찾을 수 없습니다: $GradlePath"
}

$branch = (& git -C $RepoPath branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) {
    Stop-WithError "현재 브랜치를 확인하지 못했습니다."
}
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

Write-Step "Runtime 설정 확인"
if (-not (Test-Path $LocalPropertiesPath)) {
    Stop-WithError "mobile/local.properties가 없습니다. local.properties.example을 복사한 뒤 설정하세요."
}

$properties = Read-LocalProperties $LocalPropertiesPath
$baseUrl = Get-PropertyValue $properties "BACKEND_BASE_URL" "http://127.0.0.1:8000/"
$careMode = (Get-PropertyValue $properties "CUSTOMER_CARE_MODE" "REMOTE").Trim().ToUpperInvariant()
$demoSubscriptionId = (Get-PropertyValue $properties "DEMO_SUBSCRIPTION_ID" "").Trim()
$showDeveloperTools = (Get-PropertyValue $properties "SHOW_DEVELOPER_TOOLS" "false").Trim().ToLowerInvariant()

if ($careMode -notin @("REMOTE", "FAKE")) {
    Stop-WithError "CUSTOMER_CARE_MODE는 REMOTE 또는 FAKE여야 합니다: $careMode"
}
if (-not $baseUrl.EndsWith("/")) {
    Stop-WithError "BACKEND_BASE_URL은 /로 끝나야 합니다: $baseUrl"
}
try {
    $baseUri = [Uri]$baseUrl
} catch {
    Stop-WithError "BACKEND_BASE_URL 형식이 올바르지 않습니다: $baseUrl"
}

if (-not $BuildOnly -and $careMode -eq "REMOTE" -and -not (Test-Uuid $demoSubscriptionId)) {
    Stop-WithError "REMOTE 발표 검증에는 유효한 DEMO_SUBSCRIPTION_ID가 필요합니다."
}
if (-not $BuildOnly -and $showDeveloperTools -eq "true") {
    Stop-WithError "발표 검증에서는 SHOW_DEVELOPER_TOOLS=false로 설정해야 합니다."
}

Write-Ok "데이터 모드: $careMode"
Write-Ok "Backend URL: $baseUrl"
Write-Ok "Demo 구독 ID: $(Mask-Value $demoSubscriptionId)"
if ($BuildOnly) {
    Write-Warn "BuildOnly 모드이므로 실제 Demo 구독 UUID 필수 검사는 생략합니다."
}

Write-Step "Core·고객 앱 테스트 및 Debug APK 빌드"
Push-Location $MobilePath
try {
    $tasks = @(
        ":core:test",
        ":customer-app:testDebugUnitTest",
        ":technician-app:testDebugUnitTest",
        ":customer-app:assembleDebug",
        ":technician-app:assembleDebug"
    )
    if ($RunConnectedTest) {
        $tasks += ":customer-app:connectedDebugAndroidTest"
    }

    & $GradlePath @tasks "--no-daemon"
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "Gradle 검증이 실패했습니다."
    }
} finally {
    Pop-Location
}

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

$healthResult = "미실행"
if (-not $BuildOnly) {
    Write-Step "Backend Health 확인"
    $healthBuilder = [UriBuilder]$baseUri
    if ($healthBuilder.Host -eq "10.0.2.2") {
        $healthBuilder.Host = "127.0.0.1"
    }
    $healthBuilder.Path = "/health"
    $healthBuilder.Query = ""
    $healthUrl = $healthBuilder.Uri.AbsoluteUri

    try {
        $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5
        $healthResult = "PASS ($($response.StatusCode))"
        Write-Ok "GET $healthUrl -> $($response.StatusCode)"
    } catch {
        $healthResult = "FAIL"
        Stop-WithError "Backend Health 확인 실패: $healthUrl"
    }
}

$adbResult = "미실행"
if ($Install) {
    Write-Step "ADB 설치 및 앱 실행"
    $adbPath = Find-Adb $properties
    if ($null -eq $adbPath) {
        Stop-WithError "adb.exe를 찾지 못했습니다. Android SDK platform-tools 경로를 확인하세요."
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

    $adbArgs = @("-s", $selectedDevice)
    if ($baseUri.Host -in @("127.0.0.1", "localhost")) {
        & $adbPath @adbArgs reverse tcp:8000 tcp:8000
        if ($LASTEXITCODE -ne 0) {
            Stop-WithError "adb reverse 설정에 실패했습니다."
        }
        Write-Ok "adb reverse tcp:8000 tcp:8000 적용"
    }

    if ($ResetAppData) {
        & $adbPath @adbArgs shell pm clear $PackageName | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Stop-WithError "앱 데이터 초기화에 실패했습니다."
        }
        Write-Ok "앱 데이터 초기화"
    }

    & $adbPath @adbArgs install -r $ApkPath
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "APK 설치에 실패했습니다."
    }

    & $adbPath @adbArgs shell am start -W -n $LaunchActivity
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "고객 앱 실행에 실패했습니다."
    }
    $adbResult = "PASS"
    Write-Ok "고객 앱 설치 및 실행"
}

Write-Step "검증 결과 저장"
$reportDirectory = Split-Path -Parent $ReportPath
New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null
$commit = (& git -C $RepoPath rev-parse --short HEAD).Trim()
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"
$report = @(
    "4주차 모바일 Smoke Test 결과",
    "검증 시각: $timestamp",
    "브랜치: $branch",
    "Commit: $commit",
    "고객 데이터 모드: $careMode",
    "Backend URL: $baseUrl",
    "Demo 구독 ID: $(Mask-Value $demoSubscriptionId)",
    "Core 단위 테스트: PASS",
    "고객 앱 단위 테스트: PASS",
    "방문기사 앱 단위 테스트: PASS",
    "고객 Debug APK: PASS",
    "고객 APK SHA-256: $apkHash",
    "방문기사 Debug APK: PASS",
    "방문기사 APK SHA-256: $technicianApkHash",
    "Backend Health: $healthResult",
    "ADB 설치·실행: $adbResult",
    "결과: PASS"
)
[System.IO.File]::WriteAllLines(
    $ReportPath,
    $report,
    [System.Text.UTF8Encoding]::new($false)
)
Write-Ok "결과 파일: $ReportPath"

Write-Host "`n다음 수동 확인:" -ForegroundColor Magenta
Write-Host "1. Demo 로그인"
Write-Host "2. 고객 홈에서 데이터 출처와 Backend 상태 확인"
Write-Host "3. 문진 시작 후 증상 입력 및 실제 문의 제출"
Write-Host "4. 네트워크 실패 시 Fake 성공 결과로 바뀌지 않는지 확인"
Write-Host "5. 앱 재실행 후 로그인·주요 상태 확인"
