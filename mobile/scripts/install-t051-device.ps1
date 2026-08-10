param(
    [string]$RepoPath = "C:\skn29\WaterCare",
    [string]$AdbPath = "C:\Users\Playdata\AppData\Local\Android\Sdk\platform-tools\adb.exe",
    [string]$Serial = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $AdbPath)) {
    throw "ADB not found: $AdbPath"
}

$CustomerApk = Join-Path $RepoPath `
    "mobile\customer-app\build\outputs\apk\debug\customer-app-debug.apk"
$TechnicianApk = Join-Path $RepoPath `
    "mobile\technician-app\build\outputs\apk\debug\technician-app-debug.apk"

foreach ($Apk in @($CustomerApk, $TechnicianApk)) {
    if (-not (Test-Path -LiteralPath $Apk)) {
        throw "APK not found: $Apk"
    }
}

& $AdbPath start-server
if ($LASTEXITCODE -ne 0) {
    throw "adb start-server failed."
}

$Devices = @(
    & $AdbPath devices |
        Select-Object -Skip 1 |
        Where-Object { $_ -match "\sdevice$" }
)

if ($Devices.Count -eq 0) {
    throw "No authorized Android device found. Check USB debugging."
}

if ([string]::IsNullOrWhiteSpace($Serial)) {
    $Serial = ($Devices[0] -split "\s+")[0]
}

function Invoke-Adb {
    param([string[]]$Arguments)

    & $AdbPath -s $Serial @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "ADB failed: $($Arguments -join ' ')"
    }
}

Invoke-Adb @("install", "-r", $CustomerApk)
Invoke-Adb @("install", "-r", $TechnicianApk)

Invoke-Adb @(
    "shell"
    "am"
    "force-stop"
    "com.skn29.watercare.customer"
)
Invoke-Adb @(
    "shell"
    "am"
    "start"
    "-n"
    "com.skn29.watercare.customer/.MainActivity"
)

Start-Sleep -Seconds 3

Invoke-Adb @(
    "shell"
    "am"
    "force-stop"
    "com.skn29.watercare.technician"
)
Invoke-Adb @(
    "shell"
    "am"
    "start"
    "-n"
    "com.skn29.watercare.technician/.MainActivity"
)

Write-Host ""
Write-Host "T051_DEVICE_INSTALL_COMPLETE" -ForegroundColor Green
Write-Host "Device: $Serial"
