param(
    [string]$RepoPath = "C:\skn29\WaterCare",
    [string]$AdbPath = "C:\Users\Playdata\AppData\Local\Android\Sdk\platform-tools\adb.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Adb {
    param([string[]]$Arguments)

    & $AdbPath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "ADB failed: $($Arguments -join ' ')"
    }
}

function Capture-App {
    param(
        [string]$Label,
        [string]$PackageName,
        [string]$OutputPath
    )

    Invoke-Adb @("shell", "am", "force-stop", $PackageName)
    Invoke-Adb @(
        "shell",
        "am",
        "start",
        "-n",
        "$PackageName/.MainActivity"
    )

    Start-Sleep -Seconds 3
    Write-Host ""
    Write-Host "$Label 대시보드를 준비하세요." -ForegroundColor Yellow
    Write-Host "로그인 화면이면 오프라인 대시보드 미리보기를 누르세요." `
        -ForegroundColor Yellow
    [void](Read-Host "준비되면 Enter")

    $RemotePath = "/sdcard/$([IO.Path]::GetFileName($OutputPath))"
    Invoke-Adb @("shell", "screencap", "-p", $RemotePath)
    Invoke-Adb @("pull", $RemotePath, $OutputPath)
    Invoke-Adb @("shell", "rm", "-f", $RemotePath)

    if (-not (Test-Path -LiteralPath $OutputPath)) {
        throw "$Label screenshot was not created."
    }
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutputDirectory = Join-Path $RepoPath `
    "mobile\build\reports\t047-device-captures\$Timestamp"

New-Item `
    -ItemType Directory `
    -Path $OutputDirectory `
    -Force |
    Out-Null

Capture-App `
    -Label "고객용" `
    -PackageName "com.skn29.watercare.customer" `
    -OutputPath (Join-Path $OutputDirectory "customer-dashboard.png")

Capture-App `
    -Label "방문기사용" `
    -PackageName "com.skn29.watercare.technician" `
    -OutputPath (Join-Path $OutputDirectory "technician-dashboard.png")

Write-Host ""
Write-Host "T047_DEVICE_CAPTURE_COMPLETE" -ForegroundColor Green
Write-Host "Folder: $OutputDirectory"
Start-Process explorer.exe $OutputDirectory
