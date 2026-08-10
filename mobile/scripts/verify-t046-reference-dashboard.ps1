param(
    [string]$RepoPath = "C:\skn29\WaterCare"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoPath = [IO.Path]::GetFullPath($RepoPath)
$MobilePath = Join-Path $RepoPath "mobile"

$GradleCommand = @(
    "call"
    "gradlew.bat"
    ":core:test"
    ":customer-app:testDebugUnitTest"
    ":customer-app:assembleDebug"
    ":technician-app:testDebugUnitTest"
    ":technician-app:assembleDebug"
    "--no-daemon"
) -join " "

$Process = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList @(
        "/d"
        "/s"
        "/c"
        $GradleCommand
    ) `
    -WorkingDirectory $MobilePath `
    -NoNewWindow `
    -Wait `
    -PassThru

if ($Process.ExitCode -ne 0) {
    throw "T-046 Gradle verification failed with exit code $($Process.ExitCode)"
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
Write-Host "T046_REFERENCE_DASHBOARD_BUILD_PASS" `
    -ForegroundColor Green
Write-Host "Customer APK: $CustomerApk"
Write-Host "Technician APK: $TechnicianApk"
