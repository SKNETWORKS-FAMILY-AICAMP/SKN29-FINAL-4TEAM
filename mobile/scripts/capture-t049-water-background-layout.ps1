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
    Write-Host "$Label 화면을 준비하세요." -ForegroundColor Yellow
    Write-Host "로그인 화면이면 오프라인 미리보기로 이동하세요." `
        -ForegroundColor Yellow
    [void](Read-Host "준비되면 Enter")

    $Remote = "/sdcard/$([IO.Path]::GetFileName($OutputPath))"
    Invoke-Adb @("shell", "screencap", "-p", $Remote)
    Invoke-Adb @("pull", $Remote, $OutputPath)
    Invoke-Adb @("shell", "rm", "-f", $Remote)
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutputDirectory = Join-Path $RepoPath `
    "mobile\build\reports\t049-device-captures\$Timestamp"

New-Item `
    -ItemType Directory `
    -Path $OutputDirectory `
    -Force |
    Out-Null

Capture-App `
    -Label "고객용" `
    -PackageName "com.skn29.watercare.customer" `
    -OutputPath (Join-Path $OutputDirectory "customer-t049.png")

Capture-App `
    -Label "방문기사용" `
    -PackageName "com.skn29.watercare.technician" `
    -OutputPath (Join-Path $OutputDirectory "technician-t049.png")

Write-Host ""
Write-Host "T049_DEVICE_CAPTURE_COMPLETE" -ForegroundColor Green
Write-Host "Folder: $OutputDirectory"
Start-Process explorer.exe $OutputDirectory
